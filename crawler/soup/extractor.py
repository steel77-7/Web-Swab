from datetime import datetime
from typing import List

import requests
from bs4 import BeautifulSoup
from models.models import Content, Links, Metadata, Tbs


class Extractor(BeautifulSoup):
    def __init__(self, url):
        self.url = url

        response = requests.get(url)
        # print("Url to be processed", response.text)
        self.fetched = True
        if response.status_code > 400:
            # something is wrong
            print("error code:", response.status_code)
            self.fetched = False
        if self.fetched:
            self.url_res = response
            self.site_metadata = Metadata(
                contentLength=int(response.headers["Content-Length"]),
                contentType=response.headers["Content-Type"],
                httpStatusCode=response.status_code,
            )

            self.site_raw_text = self.url_res.text
            self.soup = BeautifulSoup(self.site_raw_text, "html.parser")
            self.content = Content(url=url)
            self.links = List[Links()]

    def check_if_js(self):
        # check for js rendered sites
        print("check js func")

    def extract_links(
        self,
    ):  # will be sent to the broker later .....but what about the db then ??
        res = []
        for link in self.soup.find_all("a"):
            l = Links()
            targeturl = link.get("href")
            if not targeturl:
                return

            anchortext = link.get_text(strip=True)
            l.linkType = ""
            if "/" in targeturl or ":" not in targeturl:
                l.linkType = "relative"
            else:
                l.linkType = "absolute"
            l.targetUrl = str(targeturl)
            l.sourceUrl = self.url
            l.anchorText = anchortext
            # print("link found: ", l.model_dump())
            res.append(l)
        self.links = res
        # getting multiple links for the target urls
        # they will be sent to the broker again

    def extract_html(self):
        return self.site_raw_text

    def parse_html(self):
        self.content.title = self.soup.title.string if self.soup.title else "No Title"
        self.content.htmlSource = self.site_raw_text
        meta_desc = self.soup.find("meta", attrs={"name": "description"})

        if meta_desc:
            # self.content.metadata_str = # Force conversion to string to satisfy the type checker
            self.content.metadata_str = (
                str(meta_desc.get("content", "")) if meta_desc else None
            )
        else:
            self.content.metadata_str = None
        for element in self.soup(
            ["script", "style", "header", "footer", "nav", "aside"]
        ):
            element.extract()

        main_text = self.soup.get_text(separator="\n", strip=True)
        self.content.textContent = main_text

    def complete(self):

        self.extract_links()
        self.parse_html()

        return_dict = {
            # "url" :self.url,
            "new_urls": self.links,
            "content": self.content,
            "req_metadata": self.site_metadata,
        }
        return return_dict
