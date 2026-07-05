from typing import List
from urllib.parse import urljoin

from caching.caching import Caching
from db.db import engine
from models.models import Job, JobStatus
from sqlalchemy import text
from sqlmodel import Session


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

    def depth_handler(self, job):
        try:
            with self.engine.connect() as conn:
                print("depth handler")
                # i will create if it does not exist
                #
                res = conn.execute(
                    text("""
                    WITH job_data AS (
                        INSERT INTO job (job_id, url_id, depth)
                        SELECT :job_id, u.id, :depth
                        FROM url u
                        WHERE u.url = :url
                        ON CONFLICT (job_id) DO NOTHING
                        RETURNING id, depth
                    ),
                    existing_job AS (
                        SELECT id, depth
                        FROM job
                        WHERE job_id = :job_id
                    ),
                    final_job AS (
                        SELECT * FROM job_data
                        UNION ALL
                        SELECT * FROM existing_job
                        LIMIT 1
                    ),
                    url_data AS (
                        SELECT id
                        FROM url
                        WHERE url = :url
                    )
                    INSERT INTO link_log (job_id, root_depth, url_id, depth)
                    SELECT
                        fj.id,
                        fj.depth,
                        u.id,
                        :depth
                    FROM final_job fj
                    JOIN url_data u ON TRUE
                    ON CONFLICT (url_id, job_id, depth) DO NOTHING
                    RETURNING *;
                    """),
                    {
                        "url": job.Url,
                        "job_id": job.ID,
                        "depth": job.Depth,
                    },
                ).fetchall()
                if len(res) == 0:
                    return None

                links = conn.execute(
                    text("""
                SELECT * FROM links WHERE "sourceUrl_id" =:url_id
                """),
                    {"url_id": res[0]["url_id"]},
                ).fetchall()
                jobs = []
                for l in links:
                    base = l.sourceUrl
                    relative = l.targetUrl
                    absolute = urljoin(base, relative)
                    job = Job(
                        Id=job.Id,
                        Status=JobStatus.PENDING,
                        Depth=job.Depth - 1,
                        Url=absolute,
                    )
                    jobs.append(job)
                return jobs
                # now there is no need for refecthing the data

        except Exception as e:
            print(e)

    def check_job(self, id):
        try:
            with self.engine.connect() as conn:
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
                        """SELECT
                            id,
                            MAX(root_depth) AS root_depth,
                            job_id,
                            url_id,
                            depth
                        FROM link_log
                        WHERE url_id = :id
                        GROUP BY id, job_id, url_id;"""
                    ),
                    {"id": row_dict["id"]},
                )
                res2 = conn.execute(
                    text(
                        """SELECT
                            MAX(depth) as depth
                        FROM job
                        WHERE url_id = :id
                        GROUP BY id, url_id;"""
                    ),
                    {"id": row_dict["id"]},
                )
                row1 = res1.first()
                if row1 is None:
                    return True, row_dict, dif
                row2 = res2.first()
                if row2 is None:
                    return True, row_dict, dif
                job_log_mapping = row1._mapping
                print(job_log_mapping)
                job_mapping = row2._mapping
                dif = job_mapping["depth"] - job.Depth
                print("diff :", dif)
                max_depth = job_mapping["depth"] + job.Depth
                if dif == 0:
                    print("all the data already available")
                    hey = conn.execute(
                        text(
                            """
                            WITH inserted_job AS (
                                       INSERT INTO job (job_id, url_id, depth)
                                       VALUES (:job_id, :url_id, :depth)
                                       RETURNING id ,depth
                                   )
                                   INSERT INTO link_log (job_id, root_depth,depth, url_id)
                                   SELECT ij.id,ij.depth, ll.depth, ll.url_id
                                   FROM link_log ll
                                   CROSS JOIN inserted_job ij
                                   WHERE ll.job_id = :id
                                   RETURNING *;
                            """
                        ),
                        {
                            "id": job_log_mapping["job_id"],
                            "job_id": job.Id,
                            "url_id": row_dict["id"],
                            "depth": job.Depth,
                        },
                    )
                    print("res")

                    print(hey.fetchall())
                    conn.execute(
                        text(
                            "SELECT pg_notify('job_completed', CAST(:job_id AS TEXT));"
                        ),
                        {"job_id": job.Id},
                    )
                    conn.commit()
                    rows = conn.execute(
                        text("""
                            SELECT
                                ll.id,
                                ll.job_id,
                                ll.depth,
                                ll.url_id
                            FROM link_log ll
                            WHERE ll.job_id = :job_id
                        """),
                        {
                            "job_id": job_log_mapping["job_id"],
                        },
                    ).fetchall()

                    print("Rows found:", len(rows))

                    for row in rows:
                        print(dict(row._mapping))
                elif dif > 0:
                    print("There is already enough data available")
                    conn.execute(
                        text(
                            """
                            WITH inserted_job AS (
                                INSERT INTO job (job_id, url_id, depth)
                                VALUES (:job_id, :url_id, :depth)
                                RETURNING id,depth
                            )
                            INSERT INTO link_log (depth,root_depth, job_id, url_id)
                            SELECT ll.depth,ij.depth, ij.id, ll.url_id
                            FROM link_log ll
                            CROSS JOIN inserted_job ij
                            WHERE ll.job_id = :id AND ll.depth < ij.depth AND ll.depth >= :first_log_depth
                            RETURNING *;
                            """
                        ),
                        {
                            "id": job_log_mapping["job_id"],
                            "job_id": job.Id,
                            "url_id": row_dict["id"],
                            "depth": job.Depth,
                            "root_depth": job_mapping["depth"],
                            "dif": dif,
                            "first_log_depth": job_log_mapping["depth"],
                        },
                    )
                    conn.execute(
                        text(
                            "SELECT pg_notify('job_completed', CAST(:job_id AS TEXT));"
                        ),
                        {"job_id": job.Id},
                    )
                    conn.commit()
                    rows = conn.execute(
                        text("""
                            SELECT
                                ll.id,
                                ll.job_id,
                                ll.depth,
                                ll.url_id
                            FROM link_log ll
                            WHERE ll.job_id = :job_id
                        """),
                        {
                            "job_id": job_log_mapping["job_id"],
                        },
                    ).fetchall()

                    print("Rows found:", len(rows))

                    for row in rows:
                        print(dict(row._mapping))
                elif dif < 0:
                    print("Means more pages need to be fetched")
                    hey = conn.execute(
                        text(
                            """
                            WITH inserted_job AS (
                                INSERT INTO job (job_id, url_id, depth)
                                VALUES (:job_id, :url_id, :depth)
                                RETURNING id, depth
                            )
                            INSERT INTO link_log (root_depth, depth, job_id, url_id)
                            SELECT
                                ij.depth,
                                ll.depth,
                                ij.id,
                                ll.url_id
                            FROM link_log ll
                            CROSS JOIN inserted_job ij
                            WHERE ll.job_id = :id AND ll.depth <  ij.depth-1
                            RETURNING *;
                            """
                        ),
                        {
                            "id": job_log_mapping["job_id"],
                            "job_id": job.Id,
                            "url_id": row_dict["id"],
                            "depth": job.Depth,
                            "job_log_depth": job_log_mapping["depth"],
                        },
                    )
                    print("res: ", hey.fetchall())
                    conn.commit()

                    links = conn.execute(
                        text(
                            """
                            WITH target_job AS (
                                SELECT id
                                FROM job
                                WHERE job_id = :request_job_id
                                LIMIT 1
                            ),
                            job_log AS (
                                SELECT MIN(depth) AS min_depth, url_id
                                FROM link_log
                                WHERE job_id = (SELECT id FROM target_job)  -- Perfectly matches integer types
                                GROUP BY url_id
                            )
                            SELECT l.* FROM links l
                            JOIN job_log j ON l."sourceUrl_id" = j.url_id;
                            """
                        ),
                        {"request_job_id": job.Id},
                    )
                    conn.commit()

                    # this will retur n a l;ot of rows
                    tbr = []
                    for l in links:
                        base = l.sourceUrl
                        relative = l.targetUrl
                        absolute = urljoin(base, relative)
                        job = Job(
                            Id=job.Id,
                            Status=JobStatus.PENDING,
                            Depth=job.Depth - 1,
                            Url=absolute,
                        )
                        tbr.append(job)
                    print("THE LENGHT OF LINKS", len(tbr))
                    return True, tbr, dif
                return True, row_dict, dif
        except Exception as e:
            print("Exception in the check url:", e)
            raise Exception("in check url :", e)

    def insert_tbs(self, data):
        with Session(self.engine) as session:
            try:
                session.add(data["url"])
                session.commit()
                if data["job"] is not None:
                    data["job"].url_id = data["url"].id
                    session.add(data["job"])
                    session.commit()
                    data["job_log"].job_id = data["job"].id
                    data["job_log"].root_depth = data["job"].depth
                    data["job_log"].depth = data["job"].depth - data["job_log"].depth

                else:
                    res = session.execute(
                        text("SELECT * FROM job WHERE job_id = :id"),
                        {"id": data["job_log"].job_id},
                    )
                    row = res.first()
                    data["job_log"].job_id = row.id
                    data["job_log"].root_depth = row.depth
                    data["job_log"].depth = row.depth - data["job_log"].depth

                data["job_log"].url_id = data["url"].id
                data["metadata"].url_id = data["url"].id
                data["content"].url_id = data["url"].id
                session.add(data["job_log"])
                session.add(data["metadata"])
                session.add(data["content"])
                session.add_all(data["links"])
                session.commit()
            except Exception as e:
                print("Error in the insert tbs in job repository :", e)
                return
