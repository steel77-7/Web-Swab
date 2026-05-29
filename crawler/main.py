from models.models import Url

from crawler.crawler import Crawler


def jobhandler(job):
    print("Started........")
    print(job)
    crawler = Crawler(job)
    crawler.add()
