from app.db import database_url


def test_pytest_uses_a_dedicated_sqlite_database() -> None:
    assert database_url() == "sqlite:///./atlasiq-test.db"
