import os

from dotenv import load_dotenv
from psycopg import Connection, connect


def required_environment_value(name: str) -> str:
    """Return a required environment value or raise a clear error."""
    value = os.getenv(name)

    if not value:
        raise ValueError(f"Required environment variable is missing: {name}")

    return value


def get_database_connection() -> Connection:
    """Create a PostgreSQL connection from local environment settings."""
    load_dotenv()

    connection_parameters = {
        "dbname": required_environment_value("POSTGRES_DB"),
        "user": required_environment_value("POSTGRES_USER"),
        "host": os.getenv("POSTGRES_HOST", "localhost"),
        "port": int(os.getenv("POSTGRES_PORT", "5432")),
    }

    password = os.getenv("POSTGRES_PASSWORD")
    if password:
        connection_parameters["password"] = password

    return connect(**connection_parameters)


def main() -> None:
    """Verify the configured PostgreSQL connection."""
    with get_database_connection() as connection, connection.cursor() as cursor:
        cursor.execute("SELECT current_database(), current_user;")
        database_name, database_user = cursor.fetchone()

    print(f"Connected to database '{database_name}' as user '{database_user}'")


if __name__ == "__main__":
    main()