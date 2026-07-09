import asyncio
from socketserver.server import BrokerClient

from conf.conf import load_config
from db.db import runDB
from dotenv import load_dotenv

# def main(job):
#     print("Started........")
#     print(job)
#     crawler = Crawler(job)
#     crawler.add()


# main(
#     Job(
#         Id="alsaadgkgsj",
#         Status=JobStatus.DONE,
#         Depth=3,
#         Url="https://books.toscrape.com/catalogue/category/books_1/index.html",
#     )
# )


def main():
    load_dotenv()
    load_config()
    runDB()
    client = BrokerClient()
    asyncio.run(client.connect())
