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
        try:
            with self.engine.connect() as conn:
                print(id)
                result = conn.execute(
                    text("SELECT  * FROM job WHERE job_id = :id"), {"id": id}
                )
                row = result.first()
                if row is None:
                    print("newJob")
                    return False
                return True
        except Exception as e:
            print("Exception in the Check job in the job repo: ", e)
            return None

    def check_url(self, job):
        # return something with the new and to be searched depth
        # return the data if there is any to be fetched
        try:
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
                text(
                    "SELECT id, MAX(depth) , job_id ,url_id  FROM link_log WHERE url_id = :id GROUP BY id"
                ),
                {"id": row_dict["id"]},
            )
            row1 = res1.first()
            if row1 is None:
                return True, row_dict, dif

            job_log_mapping = row1._mapping
            dif = job_log_mapping["depth"] - job.Depth

            if dif == 0:
                print("all the data already available")

                conn.execute(
                    text(
                        """
                        WITH inserted_job AS (
                            INSERT INTO job (job_id,url_id, depth)
                            VALUES (job_id,:url_id, :depth)
                            RETURNING job_id
                        )
                        INSERT INTO link_log(job_id,depth, url_id)
                        SELECT  inserted_job.id , depth, url_id  FROM link_log WHERE id = :id
                        SELECT pg_notify('job_completed' , job_id::text)
                        FROM inserted_log;
                        """
                    ),
                    {
                        "id": job_log_mapping["id"],
                        "job_id": job.Id,
                        "url_id": row_dict["id"],
                        "depth": job.Depth,
                    },
                )
            elif dif > 0:
                print("There is already enough data available")
                conn.execute(
                    text(
                        """
                        WITH inserted_job AS (
                            INSERT INTO job (job_id, url_id, depth)
                            VALUES (:job_id,:url_id, :depth)
                            RETURNING jod_id
                        )
                        INSERT INTO link_log( depth,job_id, url_id)
                        SELECT depth, inserted_job.id , url_id  FROM link_log WHERE id = :id AND depth<= :depth
                        SELECT pg_notify('job_completed' , job_id::text)
                        FROM inserted_log;
                        """
                    ),
                    {
                        "id": job_log_mapping["id"],
                        "job_id": job.Id,
                        "url_id": row_dict["id"],
                        "depth": job.Depth,
                    },
                )
            else:
                print("the logic for calculating how many pages it must fetch now")
                conn.execute(
                    text(
                        """
                        WITH inserted_job AS (
                            INSERT INTO job (job_id,url_id, depth)
                            VALUES (:job_id,:url_id, :depth)
                            RETURNING job_id
                        )
                        INSERT INTO link_log(depth, job_id ,url_id )
                        SELECT  depth,inserted_job.id  , url_id  FROM link_log WHERE id = :id AND depth<= :depth ;
                        """
                    ),
                    {
                        "id": job_log_mapping["id"],
                        "job_id": job.Id,
                        "url_id": row_dict["id"],
                        "depth": job.Depth,
                    },
                )
                links = conn.execute(
                    text(
                        """
                        WITH target_job AS (
                            -- Step 1: Find the database integer ID using the string request ID
                            SELECT id
                            FROM job
                            WHERE job_id = :request_job_id
                            LIMIT 1
                        ),
                        job_log AS (
                            -- Step 2: Use that integer ID to filter link_log
                            SELECT MIN(depth) AS min_depth, url_id
                            FROM link_log
                            WHERE job_id = (SELECT id FROM target_job)
                            GROUP BY url_id
                        )
                        SELECT l.* FROM links l
                        JOIN job_log j ON l."srcUrl" = j.url_id;
                        """
                    ),
                    {"request_job_id": job.Id},
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
        except Exception as e:
            print("Exception in the check url:", e)
            return False, None, None

    def insert_tbs(self, data):
        with Session(self.engine) as session:
            try:
                session.add(data["url"])
                session.commit()
                if data["job"] is not None:
                    data["job"].url_id = data["url"].id
                    print("THE DATA of job", data["job"])
                    session.add(data["job"])
                    session.commit()
                    session.add(data["job_log"])

                session.add(data["metadata"])
                session.add(data["content"])
                session.add_all(data["links"])
                session.commit()
            except Exception as e:
                print("Error in the insert tbs in job repository :", e)
                return
