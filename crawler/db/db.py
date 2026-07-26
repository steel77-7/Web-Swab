from conf.conf import conf
from sqlalchemy import create_engine


def runDB():
    global engine
    return create_engine(conf.db_uri)


engine = runDB()
