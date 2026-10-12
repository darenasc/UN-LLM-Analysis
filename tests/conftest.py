from pathlib import Path
import sqlite3

import pytest

from un_llm_analysis.config import SCHEMA_DB
from un_llm_analysis.database import get_db_connection
from un_llm_analysis.extractor import extract_briefing


@pytest.fixture(scope="function")
def conn():
    """Fixture serving an in-memory database connection."""
    # TODO change test_database to use this fixture instead of conn
    conn_fixture = get_db_connection(":memory:")
    conn_fixture.execute("PRAGMA foreign_keys = ON")
    conn_fixture.row_factory = sqlite3.Row

    sql_schema = Path(SCHEMA_DB).read_text(encoding="utf-8")
    conn_fixture.executescript(sql_schema)

    yield conn_fixture

    conn_fixture.close()


@pytest.fixture()
def briefing():
    """Fixture with an ExtractedBriefing."""
    return extract_briefing(
        file_path=Path("tests/fixtures/briefings/2026/2026-08/2026-08-25.json")
    )
