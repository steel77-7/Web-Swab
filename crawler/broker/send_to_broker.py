# sending to the broker
# handling the sending errors
import requests
from models.models import JobMeta, JobTbs


class Broker:
    def __init__(self, broker_uri):
        # fecthing all the info to connect to the broker
        self.locator_uri = broker_uri

    def send_to_broker(self, data, id):
        try:
            final = []
            print("sending to the broker")
            for d in data:
                url = ""
                state = True
                job_metadata = JobMeta(id=id, state=state, url=url)
                payload = JobTbs(metadata=job_metadata, data=d)
                final.append(payload.model_dump())
            response = requests.post("http://127.0.0.1:8000/ingest", json=final)
            if response.status_code > 400:
                raise Exception(f"FAILURE...........Returned ${response.status_code}")

        except Exception as e:
            print(e)
