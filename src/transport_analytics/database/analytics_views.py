import logging
from pathlib import Path

from psycopg import Connection

from transport_analytics.database.connection import get_database_connection

ANALYTICS_VIEWS_SQL_PATH = Path("sql/create_analytics_views.sql")

LOGGER = logging.getLogger(__name__)


def create_analytics_views(
    connection: Connection,
    sql_path: Path = ANALYTICS_VIEWS_SQL_PATH,
) -> None:
    """Create or replace the warehouse's analytical views."""
    if not sql_path.exists():
        raise FileNotFoundError(f"Analytics view SQL file not found: {sql_path}")

    with connection.cursor() as cursor:
        cursor.execute(sql_path.read_text(encoding="utf-8"))


def run_analytics_view_creation() -> None:
    """Create analytical views using the configured PostgreSQL database."""
    LOGGER.info("Creating analytical views from %s", ANALYTICS_VIEWS_SQL_PATH)
    with get_database_connection() as connection:
        create_analytics_views(connection)
    LOGGER.info("Analytical views created successfully")
