from models.models import Job, JobStatus

from crawler.crawler import Crawler


def jobhandler(job):
    print("Started........")
    print(job)
    crawler = Crawler(job)
    crawler.add()


def main(job):
    print("Started........")
    print(job)
    crawler = Crawler(job)
    crawler.add()


main(
    Job(
        Id="al;ksdghldj",
        Status=JobStatus.DONE,
        Depth=3,
        Url="https://books.toscrape.com/catalogue/category/books/historical-fiction_4/index.html",
    )
)
