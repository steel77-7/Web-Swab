import asyncio

# from conf.conf import conf, load_config
from db.db import runDB
from dotenv import load_dotenv
from socket_client.server import BrokerClient

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

    # runDB()
    client = BrokerClient()
    asyncio.run(client.connect())


main()
