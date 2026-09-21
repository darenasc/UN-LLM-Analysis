from pathlib import Path
import sqlite3

import pytest

from un_llm_analysis.config import SCHEMA_DB
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
    get_section,
    get_sections_by_briefing_id,
    insert_into_briefing,
    insert_into_sdg,
    insert_into_section,
    insert_section,
)
from un_llm_analysis.extractor import (
    ExtractedBriefing,
    ExtractedSection,
    extract_briefing,
)


def test_create_database(tmp_path):
    """Test create_database function.

    Args:
        tmp_path (Path): Temporary path to create the database.
    """
    db_name = "briefings.db"
    create_database(db_path=tmp_path / db_name, schema_path=SCHEMA_DB)

    assert (tmp_path / db_name).exists()


@pytest.fixture(scope="function")
def conn(tmp_path):
    """Fixture serving a database connection."""
    db_name = "briefings.db"
    create_database(db_path=tmp_path / db_name, schema_path=SCHEMA_DB)

    yield get_db_connection(db_path=tmp_path / db_name)

    (tmp_path / db_name).unlink()


def test_get_db_connection(tmp_path):
    """Test getting a connection to a database."""
    # GIVEN a path a to a database
    db_name = "briefings.db"

    # WHEN testing `create_database`
    create_database(db_path=tmp_path / db_name, schema_path=SCHEMA_DB)
    conn = get_db_connection(db_path=tmp_path / db_name)

    # THEN check the database exists and is of the correct type
    assert (tmp_path / db_name).exists()
    assert isinstance(conn, sqlite3.Connection)

    # delete database from disk
    (tmp_path / db_name).unlink()


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
    return extract_briefing(file_path=Path("tests/fixtures/briefing_2026-08-25.json"))


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


def test_get_section(briefing, conn):
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
        result = get_section(conn=conn, section_id=section_id)

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


def test_get_min_max_dates(briefing, conn):
    """Test retrieving min and max dates from the briefing table."""
    # GIVEN a database connection with data
    _ = insert_into_briefing(conn=conn, briefing=briefing)

    # WHEN requesting max an min dates of briefings
    result_min, result_max = get_min_max_dates(conn=conn)

    # THEN the dates are equal to the inserted record
    assert result_min == briefing.briefing_date
    assert result_max == briefing.briefing_date


def test_get_dates_with_briefings(briefing, conn):
    """Test"""
    # GIVEN a database connection with data
    _ = insert_into_briefing(conn=conn, briefing=briefing)

    # WHEN requesting a briefing
    result = get_dates_with_briefings(conn=conn)

    # THEN the result is a list and the date inserted is in the results
    assert isinstance(result, list)
    assert briefing.briefing_date in result
