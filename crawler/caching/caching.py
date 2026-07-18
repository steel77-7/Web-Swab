import json
import time
from datetime import datetime, timedelta

import redis


class Caching:
    def __init__(self):
        self.r = redis.Redis(host="localhost", port=6379, db=0)

    def check_if_present(self, id):  # data.payload will already be a dict
        if self.r.exists(id):
            # self.r.hset(data.key, map
            # ping=data)
            return True
        return False

    def add_entry(self, data):
        if data is None:
            print("data to be entered in redis is None")
            return
        json_data = json.dumps(data)
        print(json_data)
        self.r.set(data["url"], json_data)

    def remove(self, key):
        self.r.delete(key)

    def add_robot(self, data, domain):
        self.r.hset("robot:" + domain, data)
        self.r.expire("robot:" + domain, 3600)

    def check_robot(self, domain):
        if self.r.exists("robot:" + domain):
            return True
        return False

    def crawl_ready(self, domain):
        res = self.r.hgetall(f"robot:{domain}")
        now = datetime.now()
        if datetime.strptime(res["nextcrawl"], "%Y-%m-%d %H:%M:%S") > now:
            return False
        return True

    def update_next_time(self, domain):
        res = self.r.hgetall(f"robot:{domain}")
        res["nextcrawl"] = datetime.now() + timedelta(seconds=int(res["deplay"]))
        self.add_robot(res, domain)
