from conf.conf import conf
from sqlalchemy import create_engine


def runDB():
    global engine
    # engine = create_engine(conf.db_uri)
    return create_engine(
        "postgresql://postgres:postgres@localhost/crawler?sslmode=disable"
    )


engine = runDB()
