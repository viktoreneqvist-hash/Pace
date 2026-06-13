from running_agent.database import check_database_connection


def test_database_connection():
    database_name = check_database_connection()

    assert database_name == "running_agent" 