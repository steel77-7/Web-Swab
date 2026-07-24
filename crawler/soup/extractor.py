import logging
from typing import List
from urllib.parse import urlparse
from urllib.robotparser import RobotFileParser

import requests
from bs4 import BeautifulSoup
from models.models import Content, Links, Metadata, Tbs

logger = logging.getLogger(__name__)


class Extractor(BeautifulSoup):
    def __init__(self, url):
        self.url = url
        self.fetched = False

        headers = {"User-Agent": ("SteelCrawler/1.0 (+https://github.com/steel77-7/)")}
        try:
            response = requests.get(url, headers=headers, timeout=15)
        except requests.RequestException as e:
            logger.error(f"failed to fetch {url}: {e}")
            return

        if response.status_code >= 400:
            logger.warning(f"HTTP {response.status_code} for {url}")
            return

        self.fetched = True
        self.url_res = response

        content_length = response.headers.get("Content-Length", "0")
        try:
            content_length = int(content_length)
        except (ValueError, TypeError):
            content_length = len(response.content)

        self.site_metadata = Metadata(
            contentLength=content_length,
            contentType=response.headers.get("Content-Type", "unknown"),
            httpStatusCode=response.status_code,
        )

        self.site_raw_text = self.url_res.text
        self.soup = BeautifulSoup(self.site_raw_text, "html.parser")
        self.content = Content(url=url)
        self.links = []

    def check_if_js(self):
        # check for js rendered sites
        pass

    def extract_links(
        self,
    ):  # will be sent to the broker later .....but what about the db then ??
        if not self.fetched:
            self.links = []
            return

        res = []
        for link in self.soup.find_all("a"):
            l = Links()
            targeturl = link.get("href")
            if not targeturl:
                continue  # skip this link, don't abort the whole loop

            anchortext = link.get_text(strip=True)
            l.linkType = ""
            if "/" in targeturl or ":" not in targeturl:
                l.linkType = "relative"
            else:
                l.linkType = "absolute"
            l.targetUrl = str(targeturl)
            l.sourceUrl = self.url
            l.anchorText = anchortext
            res.append(l)
        self.links = res

    def extract_html(self):
        if not self.fetched:
            return ""
        return self.site_raw_text

    def parse_html(self):
        if not self.fetched:
            return

        self.content.title = self.soup.title.string if self.soup.title else "No Title"
        self.content.htmlSource = self.site_raw_text
        meta_desc = self.soup.find("meta", attrs={"name": "description"})

        if meta_desc:
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
        if not self.fetched:
            return {
                "new_urls": [],
                "content": Content(url=self.url),
                "req_metadata": Metadata(
                    contentLength=0, contentType="unknown", httpStatusCode=0
                ),
            }

        self.extract_links()
        self.parse_html()

        return_dict = {
            "new_urls": self.links,
            "content": self.content,
            "req_metadata": self.site_metadata,
        }
        return return_dict
