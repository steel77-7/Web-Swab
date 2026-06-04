from urllib.parse import urljoin

import requests
from broker.send_to_broker import Broker
from caching.caching import Caching
from db.jobrepository import JobRepository
from models.models import Job, Job_db, JobMeta, JobStatus, JobTbs, Link_log, Tbs, Url
from soup.extractor import Extractor


class Crawler:
    def __init__(self, job: Job):
        self.id = ""
        self.extractor = Extractor(job.Url)
        self.caching = Caching()
        self.jobRepo = JobRepository()
        self.tbs = Tbs()

        self.job = job
        self.tbs_job = Job_db()
        self.broker = Broker("")
        # print("JOB", self.tbs.url.model_dump())

    def add(self):
        in_redis = self.caching.check_if_present(self.job.Id)
        job_in_db = self.jobRepo.check_job(self.job.Id)
        url_in_db, tbr, depth = self.jobRepo.check_url(self.job.Url)
        if job_in_db and not in_redis:
            # the current job is part of a previos job
            # no new job
            # new job log
            self.caching.add_entry(self.job.model_dump())
            site_data = self.extractor.complete()
            job_log = Link_log(depth=self.job.Depth, job_id=self.job.Id)
            data = {
                "job_log": job_log,
                "content": site_data["content"],
                "metadata": site_data["metadata"],
                "links": site_data["new_urls"],
                "job": None,
            }
            self.jobRepo.insert_tbs(data)
            self.caching.remove(self.job.Url)  #:problem

            # to the broker
            structured_data = []
            for l in site_data["new_urls"]:
                base = l.srcUrl
                relative = l.targetUrl
                absolute = urljoin(base, relative)
                job = Job(
                    Id=self.id,
                    Status=JobStatus.PENDING,
                    Depth=self.job.Depth - 1,
                    Url=absolute,
                )

                structured_data.append(job)
                # self.broker.send_to_broker(structured_data)

        elif not job_in_db and not in_redis:
            if not url_in_db:
                self.caching.add_entry(self.job.model_dump())
                site_data = self.extractor.complete()
                job_tbs = Job_db(job_id=self.job.Id, depth=self.job.Depth)
                job_log = Link_log(depth=self.job.Depth)
                data = {
                    "job_log": job_log,
                    "content": site_data["content"],
                    "metadata": site_data["metadata"],
                    "links": site_data["new_urls"],
                    "job": job_tbs,
                }
                self.jobRepo.insert_tbs(data)
                self.caching.remove(self.job.Url)
                structured_data = []
                for l in site_data["new_urls"]:
                    base = l.srcUrl
                    relative = l.targetUrl
                    absolute = urljoin(base, relative)
                    job = Job(
                        Id=self.id,
                        Status=JobStatus.PENDING,
                        Depth=self.job.Depth - 1,
                        Url=absolute,
                    )

                    structured_data.append(job)
                    # self.broker.send_to_broker(structured_data)
            else:
                # if found in the db

                # the place where the depth magic will takle place
                print("smae job but mid depth or new depth")
                # self.broker.send_to_broker(tbr)
                # only one condition for root and mid urls
                # a lot of db operations

        elif not job_in_db and in_redis and not url_in_db:
            print("being scraped for the first time ")
            return

    def send_to_broker(self, payload):
        requests.post("broker url", data=payload)
