from enum import Enum
from typing import List, Optional

from pydantic import BaseModel
from sqlmodel import Field, Relationship, SQLModel


class Url(SQLModel, table=True):
    __tablename__ = "url"

    id: Optional[int] = Field(default=None, primary_key=True)

    srcUrl: Optional[str] = None

    # canonical identifier
    targetUrl: str = Field(unique=True, index=True)

    depth: int

    tbs: Optional["Tbs"] = Relationship(back_populates="url_rel")


class Content(SQLModel, table=True):
    __tablename__ = "content"

    id: Optional[int] = Field(default=None, primary_key=True)

    title: Optional[str] = None
    textContent: Optional[str] = None
    metadata_str: Optional[str] = None

    htmlSource: Optional[str] = None

    # relation through URL string
    url: Optional[str] = Field(foreign_key="url.targetUrl", index=True)

    tbs: Optional["Tbs"] = Relationship(back_populates="content")


class Metadata(SQLModel, table=True):
    __tablename__ = "metadata"

    id: Optional[int] = Field(default=None, primary_key=True)

    # relation through URL string
    url: str = Field(foreign_key="url.targetUrl", index=True)

    contentLength: int
    contentType: str
    httpStatusCode: int

    tbs: Optional["Tbs"] = Relationship(back_populates="metadata_rel")


class Links(SQLModel, table=True):
    __tablename__ = "links"

    id: Optional[int] = Field(default=None, primary_key=True)

    sourceUrl: Optional[str]
    targetUrl: Optional[str]
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
    url: Optional[str] = Field(foreign_key="url.targetUrl", unique=True, index=True)

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


class JobStatus(str, Enum):
    PENDING = "pending"
    PROCESSING = "processing"
    DONE = "done"
    FAILED = "failed"


class Job(BaseModel):
    ID: str
    Status: JobStatus
    Depth: int
    SrcUrl: str
    TargetUrl: str


class JobMeta(BaseModel):
    ID: str
    Url: str
    State: bool


class JobTbs(BaseModel):
    Data: List[Job]
    MetaData: JobMeta
