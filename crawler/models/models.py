from enum import Enum
from typing import List, Optional

from pydantic import BaseModel
from sqlmodel import Field, Relationship, SQLModel


class Url(SQLModel, table=True):
    __tablename__ = "url"

    id: Optional[int] = Field(default=None, primary_key=True)

    # srcUrl: Optional[str] = None

    # canonical identifier
    url: str = Field(unique=True, index=True)

    depth: int

    tbs: Optional["Tbs"] = Relationship(back_populates="url_rel")
    # job: Optional["Job"] = Relationship(back_populates="url_id")


class Content(SQLModel, table=True):
    __tablename__ = "content"

    id: Optional[int] = Field(default=None, primary_key=True)

    title: Optional[str] = None
    textContent: Optional[str] = None
    metadata_str: Optional[str] = None

    htmlSource: Optional[str] = None

    # relation through URL string
    url_id: Optional[int] = Field(foreign_key="url.id", index=True)

    tbs: Optional["Tbs"] = Relationship(back_populates="content")


class Metadata(SQLModel, table=True):
    __tablename__ = "metadata"

    id: Optional[int] = Field(default=None, primary_key=True)

    # relation through URL string
    url_id: str = Field(foreign_key="url.id", index=True)

    contentLength: int
    contentType: str
    httpStatusCode: int

    tbs: Optional["Tbs"] = Relationship(back_populates="metadata_rel")


class Links(SQLModel, table=True):
    __tablename__ = "links"

    id: Optional[int] = Field(default=None, primary_key=True)

    sourceUrl: Optional[str]
    targetUrl: Optional[str]
    sourceUrl_id: Optional[int] = Field(foreign_key="url.id", index=True)
    targetUrl_id: Optional[int] = Field(foreign_key="url.id", index=True)
    anchorText: Optional[str]
    linkType: Optional[str]

    tbs_url: Optional[str] = Field(
        default=None, foreign_key="tbs_entries.url", index=True
    )

    tbs: Optional["Tbs"] = Relationship(back_populates="links")


class Tbs(SQLModel, table=True):
    __tablename__ = "tbs_entries"

    id: Optional[int] = Field(default=None, primary_key=True)

    # canonical URL relation
    url: Optional[str] = Field(foreign_key="url.url", unique=True, index=True)

    content_id: Optional[int] = Field(
        default=None, foreign_key="content.id", unique=True
    )

    metadata_id: Optional[int] = Field(
        default=None, foreign_key="metadata.id", unique=True
    )

    url_rel: Optional[Url] = Relationship(
        back_populates="tbs", sa_relationship_kwargs={"uselist": False}
    )

    content: Optional[Content] = Relationship(
        back_populates="tbs", sa_relationship_kwargs={"uselist": False}
    )

    metadata_rel: Optional[Metadata] = Relationship(
        back_populates="tbs", sa_relationship_kwargs={"uselist": False}
    )

    links: List[Links] = Relationship(back_populates="tbs")


class Job_db(SQLModel, table=True):
    __tablename__ = "job"

    id: Optional[int] = Field(default=None, primary_key=True)
    job_id: Optional[str]
    url_id: Optional[int] = Field(default=None, foreign_key="url.id")
    depth: int


class Link_log(SQLModel, table=True):
    __tablename__ = "link_log"
    id: Optional[int] = Field(default=None, primary_key=True)

    job_id: Optional[int] = Field(default=None, foreign_key="job.id")
    depth: Optional[int]
    url_id: Optional[int] = Field(default=None, foreign_key="url.id")
    root_depth: Optional[int]


class JobStatus(str, Enum):
    PENDING = "pending"
    PROCESSING = "processing"
    DONE = "done"
    FAILED = "failed"


class Job(BaseModel):
    id: str
    status: JobStatus
    depth: int
    url: str


class JobMeta(BaseModel):
    id: str
    url: str
    state: bool


class JobTbs(BaseModel):
    data: Job
    metadata: JobMeta
