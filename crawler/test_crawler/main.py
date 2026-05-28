from crawler.crawler import Crawler
from models.models import Url

# from soup.extractor import Extractor


def main():
    print("Started.........")
    job = Url(
        srcUrl=None,
        targetUrl="https://books.toscrape.com/catalogue/category/books/classics_6/index.html",
        depth=3,
    )
    crawler = Crawler(job)
    crawler.add()


main()
