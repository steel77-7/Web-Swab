from conf.conf import conf
from sqlalchemy import create_engine

engine = None


def runDB():
    global engine
    engine = create_engine(conf.db_uri)
