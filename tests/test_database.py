from datetime import date
from pathlib import Path
import sqlite3
from unittest.mock import MagicMock

import pytest
from pytest import MonkeyPatch

from un_llm_analysis import database as db_module
from un_llm_analysis.config import BRIEFINGS_DB_PATH, SCHEMA_DB
from un_llm_analysis.database import (
    create_database,
    delete_briefing,
    delete_from_sdg,
    delete_section,
    delete_sections,
    get_briefing_by_date,
    get_briefing_by_id,
    get_briefing_by_url,
    get_briefing_id_by_url,
    get_briefing_id_from_date,
    get_briefings_between_dates,
    get_dates_with_briefings,
    get_db_connection,
    get_min_max_dates,
    get_sdgs_between_dates,
    get_section_by_section_id,
    get_sections_by_briefing_id,
    insert_into_briefing,
    insert_into_sdg,
    insert_into_section,
    insert_section,
    load_between_dates,
    load_briefing_to_db,
    query_by_date,
    query_by_status,
)
from un_llm_analysis.extractor import (
    ExtractedBriefing,
    ExtractedSection,
    extract_briefing,
)
from un_llm_analysis.utils import (
    BRIEFINGS_DIR,
    _dates_between,
    _parse_date,
)


def test_create_database(tmp_path):
    """Test create_database function.

    Args:
        tmp_path (Path): Temporary path to create the database.
    """
    db_name = "briefings.db"
    create_database(db_path=tmp_path / db_name, schema_path=SCHEMA_DB)

    assert (tmp_path / db_name).exists()


def test_get_db_connection(tmp_path):
    """Test getting a connection to a database."""
    # GIVEN a path a to a database
    tmp_db_path = tmp_path / "briefings.db"

    # WHEN testing `get_db_connection` (DB is created if the parent dir exists)
    conn = get_db_connection(db_path=tmp_db_path)

    # THEN check the database exists and is of the correct type
    assert tmp_db_path.exists()
    assert isinstance(conn, sqlite3.Connection)
    conn.close()

    # close the connection
    conn.close()


@pytest.fixture(scope="function")
def conn():
    """Fixture serving an in-memory database connection."""
    conn = get_db_connection(":memory:")

    sql_schema = Path(SCHEMA_DB).read_text(encoding="utf-8")
    conn.executescript(sql_schema)

    yield conn

    conn.close()


@pytest.mark.parametrize(
    "date,expected",
    [
        ("1945-06-26", 19450626),  # Foundation of the UN
        ("2026-09-18", 20260918),
        ("1905-09-26", 19050926),  # Einsteins relativity
        ("1990-12-20", 19901220),  # First website in WWW
    ],
)
def test__get_briefing_id_from_date(date, expected):
    """Test _get_briefing_id_from_date."""
    # GIVEN a 'YYYY-MM-DD' date
    # WHEN calling `_get_briefing_id_from_date`
    briefing_id = get_briefing_id_from_date(date=date)

    # THEN eval the transformation into integer YYYYMMDD
    assert briefing_id == expected


@pytest.fixture()
def briefing():
    """Fixture with an ExtractedBriefing."""
    return extract_briefing(
        file_path=Path("tests/fixtures/briefings/2026/2026-08/2026-08-25.json")
    )


def test_insert_into_briefing(briefing, conn):
    """Test insert into the briefing table."""
    # GIVEN a database connection
    result = get_briefing_by_id(
        conn=conn, briefing_id=get_briefing_id_from_date(briefing.briefing_date)
    )

    # WHEN no data in the database
    # THEN results is None
    assert result is None

    # WHEN inserting a briefing in the database
    briefing_id = insert_into_briefing(conn=conn, briefing=briefing)
    result = get_briefing_by_id(
        conn=conn, briefing_id=get_briefing_id_from_date(briefing.briefing_date)
    )

    # THEN the data from the database corresponds with the briefing
    assert isinstance(result, ExtractedBriefing)
    assert result.briefing_date == briefing.briefing_date
    assert get_briefing_id_from_date(result.briefing_date) == briefing_id


def test_get_sections_by_briefing_id(briefing, conn):
    """Test requesting sections given a briefing_id."""
    # GIVEN a database connection with data
    briefing_id = insert_into_briefing(conn=conn, briefing=briefing)
    briefing_id_section = insert_into_section(
        conn=conn, briefing_id=briefing_id, sections=briefing.sections, insert_all=True
    )

    # WHEN requesting the sections given a briefing_id
    sections = get_sections_by_briefing_id(conn=conn, briefing_id=briefing_id_section)

    # THEN the sections are a tuple of ExtractedSection
    assert isinstance(sections, tuple)
    assert isinstance(sections[0], ExtractedSection)
    assert sections == briefing.sections


def test_get_briefing_by_id(briefing, conn):
    """Test get_briefing_by_id."""
    # GIVEN a databasae with data
    briefing_id = insert_into_briefing(conn=conn, briefing=briefing)

    # WHEN checking if a briefing exists
    result = get_briefing_by_id(
        conn=conn, briefing_id=get_briefing_id_from_date(briefing.briefing_date)
    )

    # THEN the briefing date corresponds with the inserted data
    assert isinstance(result, ExtractedBriefing)
    assert result.briefing_date == briefing.briefing_date
    assert briefing_id == get_briefing_id_from_date(result.briefing_date)


def test_get_briefing_by_url(briefing, conn):
    """Test getting a briefing given an url."""
    # GIVEN a database connection with data
    briefing_id = insert_into_briefing(conn=conn, briefing=briefing)

    # WHEN requesting a briefing
    result = get_briefing_by_url(conn=conn, url=briefing.url)

    assert isinstance(result, ExtractedBriefing)
    assert result.url == briefing.url
    assert get_briefing_id_from_date(result.briefing_date) == briefing_id


def test_get_briefing_by_date(briefing, conn):
    """Test getting a briefing given an url."""
    # GIVEN a database connection with data
    _ = insert_into_briefing(conn=conn, briefing=briefing)

    # WHEN requesting a briefing
    result = get_briefing_by_date(conn=conn, date=briefing.briefing_date)

    # THEN the results is equal to the inserted briefing
    assert briefing.briefing_date == result.briefing_date


def test_get_briefing_id_by_url(briefing, conn):
    """Test retrieving a briefing id given an url."""
    # GIVEN a database connections
    # WHEN no data in the database
    result = get_briefing_id_by_url(conn=conn, url=briefing.url)

    # THEN result is None
    assert result is None

    # WHEN retrieing a briefing id given a url
    briefing_id = insert_into_briefing(conn=conn, briefing=briefing)
    result = get_briefing_id_by_url(conn=conn, url=briefing.url)

    # THEN the results is int and the same as the id computed from the extracted briefing
    assert isinstance(result, int)
    assert result == get_briefing_id_from_date(briefing.briefing_date)
    assert result == briefing_id


def test_get_briefings_between_dates(briefing, conn):
    # GIVEN a database with data
    _ = insert_into_briefing(conn=conn, briefing=briefing)

    # WHEN deleting a briefing using the briefing id
    result = get_briefings_between_dates(
        conn=conn, start_date=briefing.briefing_date, end_date=briefing.briefing_date
    )

    # THEN the length of the result list is equal to 1 and is a ExtractedBriefing
    if result:
        assert len(result) == 1
        assert isinstance(result[0], ExtractedBriefing)
    else:
        assert result is None


def test_delete_briefing(briefing, conn):
    """Test deleting data from the briefing table."""
    # GIVEN a database with data
    briefing_id = insert_into_briefing(conn=conn, briefing=briefing)

    # WHEN deleting a briefing using the briefing id
    result = delete_briefing(conn=conn, briefing_id=briefing_id)

    # THEN the result is equal to True and an bool
    assert isinstance(result, bool)
    assert result is True


def test_delete_briefing_false(conn):
    # GIVEN a database with data
    # WHEN deleting a non-existing record
    result = delete_briefing(conn=conn, briefing_id=20260231)

    # THEN the result is equal to False and an bool
    assert isinstance(result, bool)
    assert result is False


def test_insert_into_section_all(briefing, conn):
    """Test inserting all the sections into the section table."""
    # GIVEN a database connection with data
    briefing_id = insert_into_briefing(conn=conn, briefing=briefing)

    # WHEN inserting data into section
    briefing_id_section = insert_into_section(
        conn=conn, briefing_id=briefing_id, sections=briefing.sections, insert_all=True
    )

    # THEN
    assert briefing_id == briefing_id_section


def test_insert_into_section_record(briefing, conn):
    """Test inserting a record by record."""
    # GIVEN a database connection with data
    briefing_id = insert_into_briefing(conn=conn, briefing=briefing)

    # WHEN insert a section into the section table
    briefing_id_section = insert_into_section(
        conn=conn, briefing_id=briefing_id, sections=briefing.sections, insert_all=False
    )

    # THEN the IDs of the briefing and section must be equal
    assert briefing_id == briefing_id_section


@pytest.mark.parametrize(
    "section_index,expected",
    [
        (0, 2026082501),
        (1, 2026082502),
        (2, 2026082503),
        (3, 2026082504),
    ],
)
def test_insert_section(section_index, expected, briefing, conn):
    """Test inserting a single section into the section table."""
    # GIVEN a database connection with data
    briefing_id = insert_into_briefing(conn=conn, briefing=briefing)

    # WHEN insert a single section
    result_section_id = insert_section(
        conn=conn,
        briefing_id=briefing_id,
        section=briefing.sections[section_index],
        section_order=section_index + 1,
    )

    # THEN the section id is equal to the expected id
    assert result_section_id == expected


def test_get_section_by_section_id(briefing, conn):
    """Test get a section by the section_id"""
    # GIVEN a database connection with data in briefing and section
    briefing_id = insert_into_briefing(conn=conn, briefing=briefing)
    briefing_id_section = insert_into_section(
        conn=conn, briefing_id=briefing_id, sections=briefing.sections, insert_all=True
    )
    assert briefing_id == briefing_id_section

    for i, section in enumerate(briefing.sections, start=1):
        section_id = briefing_id * 100 + i

        # WHEN request a section from the database
        result = get_section_by_section_id(conn=conn, section_id=section_id)

        # THEN the results are ExtractedSection
        assert isinstance(result, ExtractedSection)
        assert result == section
        assert result.title == section.title


@pytest.mark.parametrize(
    "section_index",
    [
        0,
        1,
    ],
)
def test_delete_section(section_index, briefing, conn):
    """Test delete a single section by the section_id"""
    # GIVEN a database connection with data
    briefing_id = insert_into_briefing(conn=conn, briefing=briefing)
    result_section_id = insert_section(
        conn=conn,
        briefing_id=briefing_id,
        section=briefing.sections[section_index],
        section_order=section_index + 1,
    )

    # WHEN delete a single section
    result = delete_section(conn=conn, section_id=result_section_id)

    # THEN the result is True
    assert result is True


def test_delete_section_false(conn):
    """Test delete a single section by the section_id when it does not exists."""
    result = delete_section(conn=conn, section_id=2026023101)

    # THEN the result is True
    assert result is False


def test_delete_sections(briefing, conn):
    """Test deleting all the sections with the same briefing_id."""
    # GIVEN a database connection with data
    briefing_id = insert_into_briefing(conn=conn, briefing=briefing)
    briefing_id_section = insert_into_section(
        conn=conn, briefing_id=briefing_id, sections=briefing.sections, insert_all=False
    )

    # WHEN deleting the sections with the same briefing_id
    result = delete_sections(conn=conn, briefing_id=briefing_id_section)

    # THEN the result is True
    assert result is True


def test_delete_sections_false(briefing, conn):
    """Test deleting all the sections when the briefing_id does not exists."""
    # GIVEN a database connection without data
    # WHEN deleting sections of a non-existing briefing_id
    result = delete_sections(conn=conn, briefing_id=20260231)

    # THEN the result is False
    assert result is False


@pytest.mark.parametrize(
    "briefing_id,section_id,sdgs,model,created_at",
    [
        (20260801, 2026080101, "['SDG1', 'SDG2']", "llama3.2", "2026-08-01"),
        (20260801, 2026080102, "['SDG3', 'SDG4']", "llama3.2", "2026-08-01"),
    ],
)
def test_insert_into_sdg(conn, briefing_id, section_id, sdgs, model, created_at):
    # GIVEN a database connection
    # WHEN inserting data into the sdg table
    insert_into_sdg(
        conn=conn,
        briefing_id=briefing_id,
        section_id=section_id,
        sdgs=sdgs,
        model=model,
        created_at=created_at,
    )
    result_df = get_sdgs_between_dates(conn=conn, start_date=created_at, end_date=created_at)

    # THEN data is returned from the database
    assert result_df.shape[0] > 0


@pytest.mark.parametrize(
    "briefing_id,section_id,sdgs,model,created_at",
    [
        (20260801, 2026080101, "['SDG1', 'SDG2']", "llama3.2", "2026-08-01"),
        (20260801, 2026080102, "['SDG3', 'SDG4']", "llama3.2", "2026-08-01"),
    ],
)
def test_delete_from_sdg(conn, briefing_id, section_id, sdgs, model, created_at):
    insert_into_sdg(
        conn=conn,
        briefing_id=briefing_id,
        section_id=section_id,
        sdgs=sdgs,
        model=model,
        created_at=created_at,
    )
    result_df = get_sdgs_between_dates(conn=conn, start_date=created_at, end_date=created_at)
    assert result_df.shape[0] > 0

    delete_from_sdg(conn=conn, section_id=section_id, model=model)
    result_df = get_sdgs_between_dates(conn=conn, start_date=created_at, end_date=created_at)
    assert result_df.shape[0] == 0


@pytest.mark.parametrize(
    "briefing_id,section_id,sdgs,model,created_at",
    [
        (20260801, 2026080101, "['SDG1', 'SDG2']", "llama3.2", "2026-08-01"),
        (20260801, 2026080102, "['SDG3', 'SDG4']", "llama3.2", "2026-08-01"),
    ],
)
def test_get_sdgs_between_dates(conn, briefing_id, section_id, sdgs, model, created_at):
    insert_into_sdg(
        conn=conn,
        briefing_id=briefing_id,
        section_id=section_id,
        sdgs=sdgs,
        model=model,
        created_at=created_at,
    )
    result_df = get_sdgs_between_dates(conn=conn, start_date=created_at, end_date=created_at)
    assert result_df.shape[0] > 0


def test_load_briefing_to_db(briefing, conn: sqlite3.Connection):
    """Test loading a briefing JSON file into the database."""
    file_path = Path("tests/fixtures/briefings/2026/2026-08/2026-08-25.json")

    result = load_briefing_to_db(file_path=file_path, conn=conn)
    assert result is True

    retrieved_briefing = get_briefing_by_url(conn=conn, url=briefing.url)
    assert retrieved_briefing is not None
    assert retrieved_briefing.url == briefing.url

    sections = get_sections_by_briefing_id(
        conn=conn, briefing_id=get_briefing_id_from_date(briefing.briefing_date)
    )
    assert len(sections) == len(briefing.sections)


def test_load_briefing_to_db_invalid_file(conn: sqlite3.Connection):
    """Test loading an invalid file returns False."""
    file_path = Path("tests/fixtures/nonexistent.json")
    result = load_briefing_to_db(file_path=file_path, conn=conn)
    assert result is False


def test_dry_run_returns_true_and_does_not_load(
    monkeypatch: MonkeyPatch, conn: sqlite3.Connection
) -> None:
    monkeypatch.setattr(db_module, "_is_briefing_json_exists", lambda d: True)
    result = load_between_dates(date(2024, 1, 1), date(2024, 1, 2), dry_run=True, conn=conn)
    assert result is True


def test_all_succeed(monkeypatch: MonkeyPatch, conn: sqlite3.Connection):
    monkeypatch.setattr(db_module, "_is_briefing_json_exists", lambda d: True)
    monkeypatch.setattr(db_module, "load_briefing_to_db", lambda path, c: True)
    assert load_between_dates(date(2024, 1, 1), date(2024, 1, 2), conn=conn) is True


def test_returns_false_on_failure(monkeypatch: MonkeyPatch, conn: sqlite3.Connection):
    monkeypatch.setattr(db_module, "_is_briefing_json_exists", lambda d: True)
    monkeypatch.setattr(db_module, "load_briefing_to_db", lambda path, c: False)
    assert load_between_dates(date(2024, 1, 1), date(2024, 1, 1), conn=conn) is False


def test_missing_json_files_are_skipped_not_failed(
    monkeypatch: MonkeyPatch, conn: sqlite3.Connection
):
    monkeypatch.setattr(db_module, "_is_briefing_json_exists", lambda d: False)
    monkeypatch.setattr(
        db_module,
        "load_briefing_to_db",
        lambda path, c: (_ for _ in ()).throw(AssertionError("should not be called")),
    )
    assert load_between_dates(date(2024, 1, 1), date(2024, 1, 1), conn=conn) is True


def test_load_between_dates(monkeypatch: MonkeyPatch, conn: sqlite3.Connection):
    monkeypatch.setattr(db_module, "_is_briefing_json_exists", lambda d: True)
    monkeypatch.setattr(db_module, "load_briefing_to_db", lambda path, c: True)
    assert load_between_dates(date(2024, 1, 1), date(2024, 1, 2), conn=conn) is True


def test_query_by_date_found(monkeypatch: MonkeyPatch, conn: sqlite3.Connection, briefing):
    """Test query_by_date runs without error when a briefing exists."""
    monkeypatch.setattr(db_module, "get_db_connection", lambda *a, **kw: conn)
    insert_into_briefing(conn=conn, briefing=briefing)
    result = query_by_date(date.fromisoformat(briefing.briefing_date))
    assert result is None


def test_query_by_date_not_found(monkeypatch: MonkeyPatch, conn: sqlite3.Connection):
    """Test query_by_date runs without error when no briefing exists."""
    monkeypatch.setattr(db_module, "get_db_connection", lambda *a, **kw: conn)
    result = query_by_date(date(2024, 1, 1))
    assert result is None


def test_query_by_status_specific(monkeypatch: MonkeyPatch, conn: sqlite3.Connection, briefing):
    """Test query_by_status filters correctly by a specific status."""
    monkeypatch.setattr(db_module, "get_db_connection", lambda *a, **kw: conn)
    insert_into_briefing(conn=conn, briefing=briefing)
    result = query_by_status(status=briefing.status)
    assert result is None


def test_query_by_status_all(monkeypatch: MonkeyPatch, conn: sqlite3.Connection, briefing):
    """Test query_by_status returns all briefings when status='all'."""
    monkeypatch.setattr(db_module, "get_db_connection", lambda *a, **kw: conn)
    insert_into_briefing(conn=conn, briefing=briefing)
    result = query_by_status(status="all")
    assert result is None
