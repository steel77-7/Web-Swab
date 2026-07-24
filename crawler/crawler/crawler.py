import copy
import logging
import time
from datetime import datetime, timedelta
from urllib.error import HTTPError, URLError
from urllib.parse import urljoin, urlparse
from urllib.robotparser import RobotFileParser

import requests
from broker.send_to_broker import Broker
from caching.caching import Caching
from conf.conf import conf
from db.jobrepository import JobRepository
from models.models import Job, Job_db, JobStatus, Link_log, Tbs, Url
from soup.extractor import Extractor
from url_normalize import url_normalize

logging.basicConfig(
    level=logging.DEBUG, format="%(asctime)s - %(levelname)s - %(message)s"
)


class Crawler:
    def __init__(self, job: Job):
        self.id = job.id
        job.url = url_normalize(job.url)
        parsed_url = urlparse(job.url)
        self.root_url = f"{parsed_url.scheme}://{parsed_url.netloc}/robots.txt"
        self.url = job.url
        # self.extractor = Extractor(job.url)
        self.caching = Caching()
        self.jobRepo = JobRepository()
        self.tbs = Tbs()

        self.job = job
        self.tbs_job = Job_db()
        self.broker = Broker(conf.broker_url)
        # print("JOB", self.tbs.url.model_dump())

    def add(self):
        self.caching.publish_log(self.id, "info", f"job started: {self.url} (depth {self.job.depth})")
        try:
            if not self.caching.check_robot(self.url):
                rp = RobotFileParser()
                rp.set_url(self.root_url + "/robots.txt")
                try:
                    rp.read()
                    delay = rp.crawl_delay(
                        "SteelCrawler/1.0 (+https://github.com/steel77-7/)"
                    )
                    if delay is not None:
                        self.caching.add_robot(
                            {
                                "delay": str(delay),
                                "nextcrawl": (datetime.now() + timedelta(seconds=int(delay))).strftime("%Y-%m-%d %H:%M:%S"),
                            },
                            self.url,
                        )
                except Exception as e:
                    self.caching.publish_log(self.id, "warn", f"no valid robots.txt/delay for {self.root_url}: {e}")
            if not self.caching.crawl_ready(self.url):
                return
            in_redis = self.caching.check_if_present(self.job.url)
            job_in_db, duplicate = self.jobRepo.check_job(self.job)
            if duplicate:
                return
            url_in_db, broker_links, done = self.jobRepo.check_url(self.job)
            if job_in_db and not in_redis:
                # either a depth continuation or duplicate job
                self.caching.publish_log(self.id, "info", f"crawling {self.url} (depth continuation)")
                self.extractor = Extractor(self.url)

                self.caching.update_next_time(self.root_url)
                self.caching.add_entry(self.job.model_dump())
                site_data = self.extractor.complete()
                links = copy.deepcopy(site_data["new_urls"])
                job_log = Link_log(depth=self.job.depth, job_id=self.job.id)
                data = {
                    "url": Url(url=self.job.url, depth=0),
                    "job_log": job_log,
                    "content": site_data["content"],
                    "metadata": site_data["req_metadata"],
                    "links": site_data["new_urls"],
                    "job": None,
                }

                self.jobRepo.insert_tbs(data)
                self.caching.remove(self.job.url)
                structured_data = []
                self.caching.publish_log(self.id, "info", f"extracted {len(links)} links from {self.url}")
                if self.job.depth > 1:
                    links = self.jobRepo.check_if_visited(links)
                    for l in links:
                        job = Job(
                            id=self.id,
                            status=JobStatus.PENDING,
                            depth=self.job.depth - 1,
                            url=l.targetUrl,
                        )

                        structured_data.append(job)
                    self.caching.publish_log(self.id, "info", f"sending {len(structured_data)} sub-jobs to broker")
                    self.broker.send_to_broker(structured_data, self.id)

            elif not job_in_db and not in_redis:
                if not url_in_db:
                    # totally new job
                    self.caching.publish_log(self.id, "info", f"crawling {self.url} (new job, depth {self.job.depth})")
                    self.extractor = Extractor(self.url)
                    self.caching.update_next_time(self.root_url)

                    self.caching.add_entry(self.job.model_dump())
                    site_data = self.extractor.complete()
                    job_tbs = Job_db(job_id=self.job.id, depth=self.job.depth)
                    job_log = Link_log(depth=self.job.depth)
                    links = copy.deepcopy(site_data["new_urls"])
                    data = {
                        "url": Url(url=self.job.url, depth=0),
                        "job_log": job_log,
                        "content": site_data["content"],
                        "metadata": site_data["req_metadata"],
                        "links": site_data["new_urls"],
                        "job": job_tbs,
                    }
                    self.jobRepo.insert_tbs(data)
                    self.caching.remove(self.job.url)
                    structured_data = []
                    self.caching.publish_log(self.id, "info", f"extracted {len(links)} links from {self.url}")
                    if self.job.depth > 1:
                        links = self.jobRepo.check_if_visited(links)
                        for l in links:
                            # base = l.sourceUrl
                            # relative = l.targetUrl
                            # absolute = urljoin(base, relative)
                            job = Job(
                                id=self.id,
                                status=JobStatus.PENDING,
                                depth=self.job.depth - 1,
                                url=l.targetUrl,
                            )

                            structured_data.append(job)
                        self.caching.publish_log(self.id, "info", f"sending {len(structured_data)} sub-jobs to broker")
                        self.broker.send_to_broker(structured_data, self.id)
                        # else:
                        #     self.jobRepo.complete(self.job.id)

                else:
                    self.caching.publish_log(self.id, "info", f"url already seen, handling depth continuation for {self.url}")

                    if broker_links is not None:
                        self.caching.publish_log(self.id, "info", f"re-sending {len(broker_links)} cached links to broker")
                        self.broker.send_to_broker(broker_links, self.id)
                        return
                    if done:
                        return
                    self.caching.publish_log(self.id, "info", f"depth handler for {self.url}")
                    self.job.id = self.id
                    # going with  simpler approach for now
                    jobs = self.jobRepo.depth_handler(self.job)
                    if jobs is None or len(jobs) == 0:
                        self.caching.publish_log(self.id, "warn", f"mid-depth handler returned no jobs for {self.url}")
                        return
                    self.broker.send_to_broker(jobs, self.id)

            elif not job_in_db and in_redis and not url_in_db:
                self.caching.publish_log(self.id, "info", f"{self.url} already being scraped, skipping")
                return
        except Exception as e:
            self.caching.publish_log(self.id, "error", f"crawl failed for {self.url}: {e}")
            logging.error(
                f"Exception in crawler.add() for {self.url}: {e}",
                exc_info=True,
            )
            return

    def send_to_broker(self, payload):
        requests.post("broker url", data=payload)
