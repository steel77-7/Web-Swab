from sqlalchemy import create_engine

engine = create_engine(
    "postgresql://postgres:postgres@localhost/crawler?sslmode=disable"
)  # input the uri later
