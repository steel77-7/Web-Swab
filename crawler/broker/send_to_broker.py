import logging
from typing import List

import requests
from conf.conf import conf
from models.models import Job, JobMeta, JobTbs

logger = logging.getLogger(__name__)


class Broker:
    def __init__(self, broker_uri):
        self.locator_uri = broker_uri

    def send_to_broker(self, data: List[Job], id) -> bool:
        try:
            final = []
            for d in data:
                url = ""
                state = True
                job_metadata = JobMeta(id=id, state=state, url=url)
                payload = JobTbs(metadata=job_metadata, data=d)
                final.append(payload.model_dump())

            broker_ingest_url = f"http://{conf.broker_url}:{conf.broker_http_port}/ingest"
            response = requests.post(
                broker_ingest_url, json=final, timeout=10
            )
            if response.status_code >= 400:
                logger.error(
                    f"broker returned status {response.status_code} for job {id}"
                )
                return False
            return True

        except requests.ConnectionError as e:
            logger.error(f"broker connection failed for job {id}: {e}")
            return False
        except requests.Timeout as e:
            logger.error(f"broker request timed out for job {id}: {e}")
            return False
        except Exception as e:
            logger.error(f"unexpected error sending to broker for job {id}: {e}")
            return False
