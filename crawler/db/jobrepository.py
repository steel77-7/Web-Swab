from typing import List
from urllib.parse import urljoin

from caching.caching import Caching
from db.db import engine
from models.models import Job, JobStatus
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
                {"url": job.Url},
            )
            row = result.first()

            if row is None:
                print("Job not present in the db")
                return False, None, 0

            row_dict = dict(row._mapping)
            dif = 0
            res1 = conn.execute(
                "SELECT id, MAX(depth) , job_id ,url_id  FROM link_log WHERE url_id = :id",
                {"id": row_dict["id"]},
            )
            row1 = row.first()
            job_log_mapping = row1._mapping
            dif = job_log_mapping["depth"] - job.Depth

            if dif == 0:
                print("all the data already available")
                # fetch the related links
                # make the job entry
                # make new discovery data and give the new job id to those
                # + the url id
                # and then fetch the related urls and return them to the caller function
                # the caller function will feed them to the broker and thus the cycle continues
                conn.execute(
                    """
                    WITH inserted_job AS (
                            INSERT INTO job (url_id, depth)
                            VALUES (:url_id, :depth)
                            RETURNING jod_id -- Catches the newly generated ID
                        )
                    INSERT INTO link_log(id , job_id,depth, url_id)
                    SELECT  inserted_job.id , depth, url_id  FROM link_log WHERE id = :id ;
                    SELECT pg_notify('job_completed' , job_id::text)
                    FROM inserted_log;
                    """,
                    {
                        "id": job_log_mapping["id"],
                        # "job_id": job.Id,
                        "url_id": row_dict["id"],
                        "depth": job.Depth,
                    },
                )
            elif dif > 0:
                print("There is already enough data available")
                conn.execute(
                    """
                    WITH inserted_job AS (
                            INSERT INTO job (url_id, depth)
                            VALUES (:url_id, :depth)
                            RETURNING jod_id -- Catches the newly generated ID
                        )
                    INSERT INTO link_log( job_id,depth, url_id)
                    SELECT  inserted_job.id , depth, url_id  FROM link_log WHERE id = :id AND depth<= :depth ;
                    SELECT pg_notify('job_completed' , job_id::text)
                    FROM inserted_log;
                    """,
                    {
                        "id": job_log_mapping["id"],
                        # "job_id": job.Id,
                        "url_id": row_dict["id"],
                        "depth": job.Depth,
                    },
                )
            else:
                print("the logic for calculating how many pages it must fetch now")
                conn.execute(
                    """
                    WITH inserted_job AS (
                            INSERT INTO job (url_id, depth)
                            VALUES (:url_id, :depth)
                            RETURNING jod_id -- Catches the newly generated ID
                        )
                    INSERT INTO link_log(job_id, depth ,url_id )
                    SELECT  inserted_job.id , depth, url_id  FROM link_log WHERE id = :id AND depth<= :depth ;
                    """,
                    {
                        "id": job_log_mapping["id"],
                        # "job_id": job.Id,
                        "url_id": row_dict["id"],
                        "depth": job.Depth,
                    },
                )
                links = conn.execute(
                    """
                    WITH job_log AS (
                        SELECT MIN(depth) AS min_depth, url_id
                        FROM link_log
                        WHERE job_id = :id
                        GROUP BY url_id
                    )
                    SELECT l.* FROM links l
                    JOIN job_log j ON l."srcUrl" = j.url_id;
                    """,
                    {"id": job.Id},
                )
                # this will retur n a l;ot of rows
                tbr = []
                for l in links:
                    base = l.srcUrl
                    relative = l.targetUrl
                    absolute = urljoin(base, relative)
                    job = Job(
                        Id=job.Id,
                        Status=JobStatus.PENDING,
                        Depth=job.Depth - 1,
                        Url=absolute,
                    )
                    tbr.append(job)
                    return True, tbr, dif
            return True, row_dict, dif

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
