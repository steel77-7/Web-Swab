import json
import logging
from datetime import datetime, timedelta

import redis
from conf.conf import conf

logger = logging.getLogger(__name__)


class Caching:
    def __init__(self):
        self.r = redis.Redis(host=conf.redis_url, port=conf.redis_port, db=0)

    def check_if_present(self, id):
        if self.r.exists(id):
            return True
        return False

    def add_entry(self, data):
        if data is None:
            logger.warning("add_entry called with None data, skipping")
            return
        json_data = json.dumps(data)
        self.r.set(data["url"], json_data)

    def remove(self, key):
        self.r.delete(key)

    def add_robot(self, data, domain):
        self.r.hset("robot:" + domain, mapping=data)
        self.r.expire("robot:" + domain, 3600)

    def check_robot(self, domain):
        if self.r.exists("robot:" + domain):
            return True
        return False

    def crawl_ready(self, domain):
        res = self.r.hgetall(f"robot:{domain}")
        if not res:
            return True
        nextcrawl_raw = res.get(b"nextcrawl") or res.get("nextcrawl")
        if nextcrawl_raw is None:
            return True
        if isinstance(nextcrawl_raw, bytes):
            nextcrawl_raw = nextcrawl_raw.decode()
        try:
            nextcrawl = datetime.strptime(str(nextcrawl_raw), "%Y-%m-%d %H:%M:%S")
        except (ValueError, TypeError):
            logger.warning(f"unparseable nextcrawl value: {nextcrawl_raw}")
            return True
        if nextcrawl > datetime.now():
            return False
        return True

    def update_next_time(self, domain):
        res = self.r.hgetall(f"robot:{domain}")
        if not res:
            return
        delay_raw = res.get(b"delay") or res.get("delay")
        if delay_raw is None:
            return
        if isinstance(delay_raw, bytes):
            delay_raw = delay_raw.decode()
        try:
            delay_seconds = int(delay_raw)
        except (ValueError, TypeError):
            logger.warning(f"unparseable delay value: {delay_raw}")
            return
        nextcrawl = datetime.now() + timedelta(seconds=delay_seconds)
        self.add_robot(
            {"delay": str(delay_seconds), "nextcrawl": nextcrawl.strftime("%Y-%m-%d %H:%M:%S")},
            domain,
        )

    def publish_log(self, job_id, level, message):
        try:
            payload = json.dumps(
                {
                    "job_id": job_id,
                    "level": level,
                    "message": message,
                    "timestamp": datetime.now().isoformat(),
                }
            )
            self.r.publish(f"crawl:logs:{job_id}", payload)
        except redis.RedisError as e:
            logger.warning(f"failed to publish log for job {job_id}: {e}")

    def init_job_count(self, job_id: str):
        try:
            self.r.hsetnx(f"job:{job_id}", "count", 1)
        except redis.RedisError as e:
            logger.warning(f"failed to init job count for {job_id}: {e}")

    def inc_job_count(self, job_id: str, amount: int):
        if amount <= 0:
            return
        try:
            new_val = self.r.hincrby(f"job:{job_id}", "count", amount)
            logger.debug(f"inc_job_count for {job_id} by {amount} -> current count: {new_val}")
        except redis.RedisError as e:
            logger.warning(f"failed to inc job count for {job_id}: {e}")

    def dec_job_count_and_check(self, job_id: str) -> int:
        try:
            val = self.r.hincrby(f"job:{job_id}", "count", -1)
            logger.debug(f"dec_job_count for {job_id} -> current count: {val}")
            if val <= 0:
                self.publish_log(
                    job_id,
                    "info",
                    f"Crawl job {job_id} completed successfully!",
                )
                self.r.delete(f"job:{job_id}")
            return val
        except redis.RedisError as e:
            logger.warning(f"failed to dec job count for {job_id}: {e}")
            return -1
