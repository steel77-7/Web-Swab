import os
from dataclasses import dataclass

from dotenv import load_dotenv

load_dotenv()


@dataclass
class Config:
    broker_url: str
    broker_http_port: int
    broker_tcp_port: int
    broker_secret: str
    db_uri: str


def load_config():
    load_dotenv()

    return Config(
        broker_url=os.getenv("BROKER_URL", "127.0.0.1"),
        broker_http_port=int(os.getenv("BROKER_HTTP_PORT", "8000")),
        broker_tcp_port=int(os.getenv("BROKER_TCP_PORT", "8000")),
        broker_secret=os.getenv("BROKER_SECRET", "secret"),
        db_uri=os.getenv(
            "DB_URI", "postgresql://postgres:postgres@localhost/crawler?sslmode=disable"
        ),
    )
    print("conf: ", conf)


conf = load_config()
