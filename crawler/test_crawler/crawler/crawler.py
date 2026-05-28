from urllib.parse import urljoin

import requests

from broker.send_to_broker import Broker
from caching.caching import Caching
from db.jobrepository import JobRepository
from models.models import Job, JobMeta, JobStatus, JobTbs, Tbs, Url
from soup.extractor import Extractor


class Crawler:
    def __init__(self, job):
        self.id = ""
        self.extractor = Extractor(job.targetUrl)
        self.caching = Caching()
        self.jobRepo = JobRepository()
        self.tbs = Tbs()
        self.tbs.url_rel = Url(
            targetUrl=job.targetUrl,
            depth=job.depth,
            # lastCrawled=None,
            srcUrl=job.srcUrl,
        )
        self.broker = Broker("")
        # print("JOB", self.tbs.url.model_dump())

    # self.tbs.url.lastCrawled = None

    #  self.tbs.url.depth = job.depth

    def add(self):
        print("startting of addng the data")
        if self.tbs.url_rel is None:
            return
        data = self.tbs.url_rel.model_dump()
        print(data)
        present_in_redis = self.caching.check_if_present(data)
        # if not present_in_redis:
        # if the data was already in the redis or not
        # now check the db
        check, row_data, val = self.jobRepo.check_if_visited(self.tbs.url_rel)
        if check and not present_in_redis:
            print("is present  in the db but the depth will eb checked first")
        elif not present_in_redis and not check:
            self.caching.add_entry(data)
            res = self.extractor.complete()
            data = {
                "tbs_entries": self.tbs,
                "content": res["content"],
                "url": self.tbs.url_rel,
                "metadata": res["req_metadata"],
                "links": res["new_urls"],
            }
            # now to store it in the db
            self.caching.remove(self.tbs.url_rel.targetUrl)
            self.jobRepo.insert_tbs(data)

            # sedning to the broker
            structured_data = []
            for l in res["new_urls"]:
                base = l.srcUrl
                relative = l.targetUrl
                absolute = urljoin(base, relative)
                job = Job(
                    ID=self.id,
                    Status=JobStatus.PENDING,
                    Depth=self.tbs.url_rel.depth - 1,
                    SrcUrl=base,
                    TargetUrl=absolute,
                )

                structured_data.append(job)

            # self.broker.send_to_broker(structured_data)
        elif present_in_redis and not check:
            print(
                "Not in the db but in redis .... means job is being processed for the first time"
            )
            # mnake the worker available for sopme antoher job
        # else:

    def send_to_broker(self, payload):
        requests.post("broker url", data=payload)
