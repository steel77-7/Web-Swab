from caching.caching import Caching
from db.db import engine
from models.models import Tbs
from sqlalchemy import text
from sqlmodel import Session, create_engine, text


class JobRepository:
    def __init__(self):
        self.engine = engine

    def insert_job(self, job):
        with self.engine.connect() as conn:
            conn.execute(
                text(
                    "INSERT INTO URLS(url, status , lastCrawled , depth) VALUES(:a,:b,NOW(),:d)"
                ),
                {
                    "a": job.url,
                    "b": job.status,
                    "d": job.depth,
                },
            )

    def check_job(self, id):
        with self.engine.connect() as conn:
            result = conn.execute(
                "SELECT  * FROM job WHERE job_id = :id", {"job_id": id}
            )
            row = result.first()
            if row is None:
                print("newJob")
                return False
            return True

    def check_url(self, job):
        # return something with the new and to be searched depth
        # return the data if there is any to be fetched
        with self.engine.connect() as conn:
            result = conn.execute(
                text("SELECT * FROM url WHERE url = :url"),
                {"url": job.targetUrl},
            )
            row = result.first()

            if row is None:
                print("Job not present in the db")
                return False, None, 0
            # if visited then what.....what about the depth.....
            row_dict = dict(row._mapping)
            dif = row_dict["depth"] - job.depth
            print(row_dict)
            # for row in result:
            #    dif = row.depth - job.depth

            if dif >= 0:
                print("all the data already available")
                # then proceed to retrieve the new job data using the links taboel that will be fetched recursively and then used for
                # conn.execute("")
            else:
                print("the logic for calculating how many pages it must fetch now")
            return True, row_dict, dif

    # def insert_tbs(self, data):
    #    with Session(self.engine) as session:
    #        for link in data["links"]:
    #            print(link.model_dump())
    #
    #        print("Link len :", len(data["links"]))
    #
    #        session.add(data["url"])
    #        session.commit()
    #
    #        session.add(data["metadata"])
    #        session.add(data["content"])
    #        session.add_all(data["links"])
    #        session.add(data["tbs_entries"])
    #        session.execute(
    #            text("SELECT pg_notify('tbs_updates', :payload)"),
    #            {"payload": str(data["url"].targetUrl)},
    #        )
    #        session.commit()

    def insert_tbs(self, data):
        with Session(self.engine) as session:
            session.add(data["url"])
            session.commit()
            if data["job"] is not None:
                session.add(data["job"])
                session.commit()
            session.add(data["job_log"])

            session.add(data["metadata"])
            session.add(data["content"])
            session.add_all(data["links"])
            session.commit()


# making a  redis map and then storgin the state in that map ...
# how willthat map look like ?
# every entry will be linked list ...... url being the key and the url data being the actual data
