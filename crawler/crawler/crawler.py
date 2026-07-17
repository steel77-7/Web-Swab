import copy
import logging
from urllib.parse import urljoin

import requests
from broker.send_to_broker import Broker
from caching.caching import Caching
from conf.conf import conf
from db.jobrepository import JobRepository
from models.models import Job, Job_db, JobStatus, Link_log, Tbs, Url
from soup.extractor import Extractor

logging.basicConfig(
    level=logging.DEBUG, format="%(asctime)s - %(levelname)s - %(message)s"
)


class Crawler:
    def __init__(self, job: Job):
        self.id = job.id
        print("1")

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
        try:
            in_redis = self.caching.check_if_present(self.job.url)
            job_in_db, duplicate = self.jobRepo.check_job(self.job)
            if duplicate:
                return
            url_in_db, broker_links, done = self.jobRepo.check_url(self.job)
            print(url_in_db, done)
            if job_in_db and not in_redis:
                # either a depth continuation or duplicate job
                self.extractor = Extractor(self.url)
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
                self.caching.remove(self.job.url)  #:problem

                # to the broker
                structured_data = []
                print("Links recovered :\t ", len(links))
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
                    self.broker.send_to_broker(structured_data, self.id)
                    # else:
                    #     self.jobRepo.complete(self.job.id)

            elif not job_in_db and not in_redis:
                if not url_in_db:
                    # totally new job
                    self.extractor = Extractor(self.url)
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
                    print("Links recovered :\t ", len(links))
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
                        self.broker.send_to_broker(structured_data, self.id)
                        # else:
                        #     self.jobRepo.complete(self.job.id)

                else:
                    print("same url but new depth or mid depth")

                    if broker_links is not None:
                        print("hunch!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!")
                        self.broker.send_to_broker(broker_links, self.id)
                        return
                    if done:
                        return
                    print("job", self.job)
                    self.job.id = self.id
                    jobs = self.jobRepo.depth_handler(self.job)
                    if jobs is None:
                        print("failed middepth")
                        return
                    self.broker.send_to_broker(jobs, self.id)

            elif not job_in_db and in_redis and not url_in_db:
                print("being scraped for the first time \n\n\n\n")
                return
        except Exception as e:
            logging.error(
                f"Excpetion occured in the add function in the add function ${e}",
                exc_info=True,
            )
            return

    def send_to_broker(self, payload):
        requests.post("broker url", data=payload)
