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
            url = ""
            state = True
            job_metadata = JobMeta(ID=id, State=state, Url=url)
            payload = JobTbs(MetaData=job_metadata, Data=data)

            response = requests.post(self.locator_uri, json=payload.model_dump())
            if response.status_code > 400:
                raise Exception(f"FAILURE...........Returned ${response.status_code}")

        except Exception as e:
            print(e)
