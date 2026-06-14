from sqlalchemy import create_engine, text

from running_agent.models.activity import Base

DATABASE_URL = "postgresql+psycopg://localhost/running_agent"

engine = create_engine(DATABASE_URL)

def check_database_connection() -> str:

    with engine.connect() as connection:

        result = connection.execute(text("SELECT current_database();"))

        return result.scalar_one()

def create_database_tables() -> None:

    Base.metadata.create_all(engine)