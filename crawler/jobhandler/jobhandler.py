from models.models import Job, JobStatus

from crawler.crawler import Crawler


def jobhandler(job):
    print("Started........")
    print(job)
    crawler = Crawler(job)
    crawler.add()
