import logging
from typing import List
from urllib.parse import urljoin

from caching.caching import Caching
from db.db import engine
from models.models import Job, JobStatus, Links, Url
from sqlalchemy import select, text
from sqlmodel import Session

logger = logging.getLogger(__name__)


class JobRepository:
    def __init__(self):
        self.engine = engine

    # url is in db ....
    # the data must be copied form the older link log to new one
    # then the dpeth must be reduced for that url

    def depth_handler(self, job):
        try:
            with Session(self.engine) as conn:
                query = """
            WITH url_data AS (
                SELECT id
                FROM url
                WHERE url = :url
            ),
            inserted_job AS (
                INSERT INTO job (job_id, url_id, depth)
                SELECT :job_id, id, :depth
                FROM url_data
                ON CONFLICT (job_id) DO NOTHING
                RETURNING id
            ),
            job_row AS (
                SELECT id
                FROM inserted_job

                UNION ALL

                SELECT id
                FROM job
                WHERE job_id = :job_id
                  AND NOT EXISTS (SELECT 1 FROM inserted_job)
            )
            SELECT
                l.*
            FROM links l
            JOIN url_data u
                ON l."sourceUrl_id" = u.id
            CROSS JOIN job_row;
            """
                stmt = select(Links).from_statement(text(query))

                links = conn.scalars(
                    stmt,
                    {
                        "job_id": job.id,
                        "url": job.url,
                        "depth": job.depth,
                    },
                ).all()
                conn.commit()
                jobs = []
                if job.depth > 1:
                    for l in links:
                        base = l.sourceUrl
                        relative = l.targetUrl
                        absolute = urljoin(base, relative)
                        jobb = Job(
                            id=job.id,
                            status=JobStatus.PENDING,
                            depth=job.depth - 1,
                            url=absolute,
                        )
                        jobs.append(jobb)
                return jobs
        except Exception as e:
            logger.error(f"depth_handler failed for job {job.id}: {e}", exc_info=True)
            return None

    def check_job(self, job):
        try:
            with self.engine.connect() as conn:
                result = conn.execute(
                    text("SELECT  * FROM job WHERE job_id = :id"), {"id": job.id}
                )
                row = result.fetchone()
                duplicate = False
                if row is None:
                    return False, duplicate
                if row.depth == job.depth:
                    duplicate = True
                return True, duplicate
        except Exception as e:
            logger.error(f"check_job failed for job {job.id}: {e}", exc_info=True)
            raise

    def check_url(self, job):
        try:
            with Session(self.engine) as conn:
                result = conn.execute(
                    text("SELECT * FROM url WHERE url = :url"),
                    {"url": job.url},
                )
                row = result.first()

                if row is None:
                    return False, None, False

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
                    return True, None, False
                row2 = res2.first()
                if row2 is None:
                    return True, None, False
                job_log_mapping = row1._mapping
                job_mapping = row2._mapping
                dif = job_mapping["depth"] - job.depth
                max_depth = job_mapping["depth"] + job.depth
                if dif == 0:
                    conn.execute(
                        text(
                            """
                            WITH inserted_job AS (
                                INSERT INTO job (job_id, url_id, depth)
                                VALUES (:job_id, :url_id, :depth)
                                ON CONFLICT (job_id) DO NOTHING
                                RETURNING id, depth
                            ),
                            job_row AS (
                                SELECT id, depth
                                FROM inserted_job

                                UNION ALL

                                SELECT id, depth
                                FROM job
                                WHERE job_id = :job_id
                                  AND NOT EXISTS (SELECT 1 FROM inserted_job)
                            )
                            INSERT INTO link_log (job_id, root_depth, depth, url_id)
                            SELECT
                                jr.id,
                                jr.depth,
                                ll.depth,
                                ll.url_id
                            FROM link_log ll
                            CROSS JOIN job_row jr
                            WHERE ll.job_id = :id
                            RETURNING *;
                            """
                        ),
                        {
                            "id": job_log_mapping["job_id"],
                            "job_id": job.id,
                            "url_id": row_dict["id"],
                            "depth": job.depth,
                        },
                    )
                    conn.execute(
                        text(
                            "SELECT pg_notify('job_completed', CAST(:job_id AS TEXT));"
                        ),
                        {"job_id": job.id},
                    )
                    conn.commit()

                elif dif > 0:
                    conn.execute(
                        text(
                            """
                            WITH inserted_job AS (
                                INSERT INTO job (job_id, url_id, depth)
                                VALUES (:job_id, :url_id, :depth)
                                ON CONFLICT (job_id) DO NOTHING
                                RETURNING id, depth
                            ),
                            job_row AS (
                                SELECT id, depth
                                FROM inserted_job

                                UNION ALL

                                SELECT id, depth
                                FROM job
                                WHERE url_id = :url_id
                                  AND NOT EXISTS (SELECT 1 FROM inserted_job)
                            )
                            INSERT INTO link_log (depth, root_depth, job_id, url_id)
                            SELECT
                                ll.depth,
                                jr.depth,
                                jr.id,
                                ll.url_id
                            FROM link_log ll
                            CROSS JOIN job_row jr
                            WHERE ll.job_id = :id
                              AND ll.depth < jr.depth
                              AND ll.depth >= :first_log_depth
                            RETURNING *;
                            """
                        ),
                        {
                            "id": job_log_mapping["job_id"],
                            "job_id": job.id,
                            "url_id": row_dict["id"],
                            "depth": job.depth,
                            "root_depth": job_mapping["depth"],
                            "dif": dif,
                            "first_log_depth": job_log_mapping["depth"],
                        },
                    )
                    conn.execute(
                        text(
                            "SELECT pg_notify('job_completed', CAST(:job_id AS TEXT));"
                        ),
                        {"job_id": job.id},
                    )
                    conn.commit()

                elif dif < 0:
                    conn.execute(
                        text(
                            """
                            WITH inserted_job AS (
                                INSERT INTO job (job_id, url_id, depth)
                                VALUES (:job_id, :url_id, :depth)
                                ON CONFLICT (job_id) DO NOTHING
                                RETURNING id, depth
                            ),
                            job_row AS (
                                SELECT id, depth
                                FROM inserted_job

                                UNION ALL

                                SELECT id, depth
                                FROM job
                                WHERE url_id = :url_id
                                  AND NOT EXISTS (SELECT 1 FROM inserted_job)
                            )
                            INSERT INTO link_log (root_depth, depth, job_id, url_id)
                            SELECT
                                jr.depth,
                                ll.depth,
                                jr.id,
                                ll.url_id
                            FROM link_log ll
                            CROSS JOIN job_row jr
                            WHERE ll.job_id = :id
                              AND ll.depth < jr.depth - 1
                            RETURNING *;
                            """
                        ),
                        {
                            "id": job_log_mapping["job_id"],
                            "job_id": job.id,
                            "url_id": row_dict["id"],
                            "depth": job.depth,
                            "job_log_depth": job_log_mapping["depth"],
                        },
                    )
                    conn.commit()

                    stmt = select(Links).from_statement(
                        text("""
                                WITH target_job AS (
                                    SELECT id
                                    FROM job
                                    WHERE job_id = :request_job_id
                                    LIMIT 1
                                ),
                                job_log AS (
                                    SELECT MAX(depth) AS max_depth, url_id
                                    FROM link_log
                                    WHERE job_id = (SELECT id FROM target_job)
                                    GROUP BY url_id
                                )
                                SELECT l.*
                                FROM links l
                                JOIN job_log j
                                    ON l."sourceUrl_id" = j.url_id
                            """)
                    )

                    links = conn.scalars(stmt, {"request_job_id": job.id}).all()
                    conn.commit()

                    tbr = []
                    links = self.check_if_visited(links)

                    if job.depth > 1:
                        for l in links:
                            jobb = Job(
                                id=job.id,
                                status=JobStatus.PENDING,
                                depth=abs(dif),
                                url=l.targetUrl,
                            )
                            tbr.append(jobb)
                    return True, tbr, True
                return True, None, True
        except Exception as e:
            logger.error(f"check_url failed for job {job.id}, url {job.url}: {e}", exc_info=True)
            raise

    def insert_tbs(self, data):
        with Session(self.engine) as session:
            try:
                # 1. Check if the URL already exists using its unique string attribute
                existing_url = session.scalars(
                    select(Url).filter_by(url=data["url"].url)
                ).first()

                if existing_url:
                    # Use the undisturbed, existing DB entry
                    data["url"] = existing_url
                else:
                    # Brand new URL, insert it safely
                    session.add(data["url"])
                    session.flush()

                # 2. Handle the job logic
                if data["job"] is not None:
                    data["job"].url_id = data["url"].id
                    session.add(data["job"])
                    session.flush()

                    data["job_log"].job_id = data["job"].id
                    data["job_log"].root_depth = data["job"].depth
                    data["job_log"].depth = data["job"].depth - data["job_log"].depth
                else:
                    res = session.execute(
                        text("SELECT * FROM job WHERE job_id = :id"),
                        {"id": data["job_log"].job_id},
                    )
                    row = res.first()

                    if row is None:
                        logger.error(f"insert_tbs: job not found for job_id={data['job_log'].job_id}")
                        session.rollback()
                        return

                    data["job_log"].job_id = row.id
                    data["job_log"].root_depth = row.depth
                    data["job_log"].depth = row.depth - data["job_log"].depth

                # 3. Attach the URL IDs to dependent models and save everything
                data["job_log"].url_id = data["url"].id
                data["metadata"].url_id = data["url"].id
                data["content"].url_id = data["url"].id

                session.add(data["job_log"])
                session.add(data["metadata"])
                session.add(data["content"])
                session.add_all(data["links"])

                session.commit()

            except Exception as e:
                session.rollback()
                logger.error(f"insert_tbs failed: {e}", exc_info=True)
                return

    def check_if_visited(self, links):
        try:
            with Session(self.engine) as session:
                # 1. Normalize all target URLs to absolute paths
                for link in links:
                    if link.sourceUrl and link.targetUrl:
                        link.targetUrl = urljoin(link.sourceUrl, link.targetUrl)

                # 2. Extract the resolved unique target strings for the DB query
                incoming_urls = {link.targetUrl for link in links if link.targetUrl}

                if not incoming_urls:
                    return []

                stmt = select(Url.url).where(Url.__table__.c.url.in_(incoming_urls))
                existing_urls = set(session.scalars(stmt).all())

                # 3. Filter out items in DB AND clear duplicates within the batch
                unvisited_objects = []
                seen_unvisited = set()

                for link in links:
                    url = link.targetUrl
                    if url and (url not in existing_urls) and (url not in seen_unvisited):
                        unvisited_objects.append(link)
                        seen_unvisited.add(url)

                return unvisited_objects
        except Exception as e:
            logger.error(f"check_if_visited failed: {e}", exc_info=True)
            return []

    def complete(self, id):
        try:
            with self.engine.connect() as conn:
                conn.execute(
                    text("""
                    UPDATE  job
                    SET status = 'done'
                    WHERE job_id =:job_id
                    """),
                    {"job_id": id},
                )
                conn.commit()
        except Exception as e:
            logger.error(f"complete failed for job {id}: {e}", exc_info=True)
