from sqlalchemy import create_engine, text


DATABASE_URL = "postgresql+psycopg://localhost/running_agent"


engine = create_engine(DATABASE_URL)


def check_database_connection() -> str:
    with engine.connect() as connection:
        result = connection.execute(text("SELECT current_database();"))
        return result.scalar_one()