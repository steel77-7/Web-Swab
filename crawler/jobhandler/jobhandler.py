import json
import logging

from models.models import Job, JobStatus

from crawler.crawler import Crawler

logger = logging.getLogger(__name__)


def jobhandler(job):
    """Parse a raw job payload and run the crawler on it."""
    try:
        if isinstance(job, str):
            job = json.loads(job)
        elif isinstance(job, bytes):
            job = json.loads(job.decode())

        tbp = Job(
            id=job["id"],
            status=job["status"],
            depth=job["depth"],
            url=job["url"],
        )
        crawler = Crawler(tbp)
        crawler.add()

    except (json.JSONDecodeError, KeyError) as e:
        logger.error(f"invalid job payload: {e}")
    except Exception as e:
        logger.error(f"jobhandler failed: {e}", exc_info=True)
