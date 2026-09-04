from transport_analytics.database.analytics_views import create_analytics_views


class FakeCursor:
    """Record SQL executed through a connection cursor."""

    def __init__(self) -> None:
        self.executed_sql = None

    def __enter__(self):
        return self

    def __exit__(self, *_args) -> None:
        pass

    def execute(self, sql) -> None:
        self.executed_sql = sql


class FakeConnection:
    """Provide a reusable fake psycopg connection cursor."""

    def __init__(self) -> None:
        self.fake_cursor = FakeCursor()

    def cursor(self) -> FakeCursor:
        return self.fake_cursor


def test_create_analytics_views_executes_sql_file(tmp_path) -> None:
    """Analytical view creation should execute the versioned SQL file."""
    sql_path = tmp_path / "views.sql"
    sql_path.write_text("CREATE VIEW test_view AS SELECT 1;", encoding="utf-8")
    connection = FakeConnection()

    create_analytics_views(connection, sql_path)

    assert connection.fake_cursor.executed_sql == (
        "CREATE VIEW test_view AS SELECT 1;"
    )
