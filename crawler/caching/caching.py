import json

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
