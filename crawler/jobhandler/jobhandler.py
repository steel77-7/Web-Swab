import json

from models.models import Job, JobStatus

from crawler.crawler import Crawler


def jobhandler(job):
    print("Started........")
    print(job)
    job = json.loads(job)
    tbp = Job(id=job["id"], status=job["status"], depth=job["depth"], url=job["url"])
    crawler = Crawler(tbp)
    crawler.add()
