from datetime import date
from pathlib import Path
import sqlite3

import pytest

from un_llm_analysis import database as db_module
from un_llm_analysis.config import SCHEMA_DB
from un_llm_analysis.database import (  # Briefing,
    Section,
    _check_country_section_exists,
    check_country_section_model_exists,
    count_successful_sections,
    create_database,
    delete_briefing,
    delete_from_issue,
    delete_from_sdg,
    delete_section,
    delete_sections,
    get_analysis_run,
    get_briefing_by_date,
    get_briefing_by_id,
    get_briefing_by_url,
    get_briefing_id_by_url,
    get_briefing_id_from_date,
    get_briefings_between_dates,
    get_completed_section_ids,
    get_countries_by_section_id,
    get_country_mentions_by_date,
    get_dates_with_briefings,
    get_db_connection,
    get_issues_between_dates,
    get_latest_analysis_run,
    get_min_max_dates,
    get_min_max_dates_with_table,
    get_models,
    get_sdg_by_section_id,
    get_sdgs_between_dates,
    get_section_by_id,
    get_sections_between_dates,
    get_sections_by_briefing_id,
    get_sections_for_sentiment_analysis,
    get_sentiment_distribution,
    get_sentiment_results,
    get_tone_distribution,
    insert_into_analysis_run,
    insert_into_briefing,
    insert_into_country,
    insert_into_issue,
    insert_into_sdg,
    insert_into_section,
    insert_section,
    insert_sentiment_analysis,
    load_briefing_to_db,
    load_briefings_between_dates,
    query_briefing_by_date,
    query_briefing_by_status,
    show_stats,
)
from un_llm_analysis.extractor import (
    ExtractedBriefing,
    ExtractedSection,
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
    conn_test = get_db_connection(db_path=tmp_db_path)

    # THEN check the database exists and is of the correct type
    assert tmp_db_path.exists()
    assert isinstance(conn_test, sqlite3.Connection)
    conn_test.close()

    # close the connection
    conn_test.close()


@pytest.mark.parametrize(
    "date,expected",
    [
        ("1945-06-26", 19450626),  # Foundation of the UN
        ("2026-09-18", 20260918),
        ("1905-09-26", 19050926),  # Einsteins relativity
        ("1990-12-20", 19901220),  # First website in WWW
    ],
)
def test_get_briefing_id_from_date(date, expected):
    """Test get_briefing_id_from_date."""
    # GIVEN a 'YYYY-MM-DD' date
    # WHEN calling `get_briefing_id_from_date`
    briefing_id = get_briefing_id_from_date(date=date)

    # THEN eval the transformation into integer YYYYMMDD
    assert briefing_id == expected


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
        conn=conn, briefing_id=briefing_id, sections=briefing.sections
    )

    # WHEN requesting the sections given a briefing_id
    sections = get_sections_by_briefing_id(conn=conn, briefing_id=briefing_id_section)

    # THEN the sections are a tuple of Section
    assert isinstance(sections, tuple)
    assert all(isinstance(section, Section) for section in sections)
    assert (
        tuple(ExtractedSection(title=section.title, text=section.text) for section in sections)
        == briefing.sections
    )

    assert all(section.briefing_id == briefing_id for section in sections)


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
    assert briefing.briefing_date == result.briefing_date  # type: ignore


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
    """Test retrieving briefings between dates."""
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
    """Test deleting a briefing that doesn't exists."""
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
        conn=conn, briefing_id=briefing_id, sections=briefing.sections
    )

    # THEN
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


def test_get_section_by_id(briefing, conn):
    """Test get a section by the section_id"""
    # GIVEN a database connection with data in briefing and section
    briefing_id = insert_into_briefing(conn=conn, briefing=briefing)
    briefing_id_section = insert_into_section(
        conn=conn, briefing_id=briefing_id, sections=briefing.sections
    )
    assert briefing_id == briefing_id_section

    for i, section in enumerate(briefing.sections, start=1):
        section_id = briefing_id * 100 + i

        # WHEN request a section from the database
        result = get_section_by_id(conn=conn, section_id=section_id)

        # THEN the result is the expected Section
        expected = Section(
            section_id=section_id,
            title=section.title,
            text=section.text,
            briefing_id=briefing_id,
            section_order=i,
        )

        assert isinstance(result, Section)
        assert result == expected


def test_get_sections_between_dates(conn, briefing):
    """Test retrieving sections between dates."""
    # GIVEN a database with data
    briefing_id = insert_into_briefing(conn=conn, briefing=briefing)
    _ = insert_into_section(conn, briefing_id, briefing.sections)

    # WHEN get_sections_between_dates is run
    result = get_sections_between_dates(
        conn=conn, start_date=briefing.briefing_date, end_date=briefing.briefing_date
    )

    # THEN the result contains the same number of Section's
    assert len(result) == len(briefing.sections)
    assert all(isinstance(x, Section) for x in result)


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
        conn=conn, briefing_id=briefing_id, sections=briefing.sections
    )

    # WHEN deleting the sections with the same briefing_id
    result = delete_sections(conn=conn, briefing_id=briefing_id_section)

    # THEN the result is True
    assert result is True


def test_delete_sections_false(conn):
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
    """Test insert data into the sdg table."""
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
    """Test deleting data from sdg."""
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
    """Test retrieving data from the sdg table."""
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


@pytest.mark.parametrize(
    "briefing_id,section_id,sdgs,model,created_at",
    [
        (20260801, 2026080101, "['SDG1', 'SDG2']", "llama3.2", "2026-08-01"),
        (20260801, 2026080102, "['SDG3', 'SDG4']", "llama3.2", "2026-08-01"),
    ],
)
def test_get_min_max_dates_with_table_sdg(conn, briefing_id, section_id, sdgs, model, created_at):
    """Test retrieving min and max dates with SDG mentions."""
    table = "sdg"
    insert_into_sdg(
        conn=conn,
        briefing_id=briefing_id,
        section_id=section_id,
        sdgs=sdgs,
        model=model,
        created_at=created_at,
    )
    min_sdg_date, max_sdg_date = get_min_max_dates_with_table(conn=conn, table=table)
    assert min_sdg_date == "2026-08-01"
    assert max_sdg_date == "2026-08-01"


@pytest.mark.parametrize(
    "briefing_id,section_id,country,iso_2,iso_3,model,created_at",
    [
        (20260801, 2026080101, "Chile", "CL", "CHL", "qwen3.5:4b", "2026-08-01"),
        (20260801, 2026080102, "Germany", "DE", "DEU", "qwen3.5:4b", "2026-08-01"),
    ],
)
def test_get_min_max_dates_with_table_country(
    conn, briefing_id, section_id, country, iso_2, iso_3, model, created_at
):
    """Test retrieving min and max dates with country mentions."""
    table = "country"
    insert_into_country(
        conn=conn,
        briefing_id=briefing_id,
        section_id=section_id,
        country=country,
        iso_2=iso_2,
        iso_3=iso_3,
        model=model,
        created_at=created_at,
    )
    min_sdg_date, max_sdg_date = get_min_max_dates_with_table(conn=conn, table=table)
    assert min_sdg_date == "2026-08-01"
    assert max_sdg_date == "2026-08-01"


@pytest.mark.parametrize(
    "briefing_id,section_id,sdgs,model,created_at, expected",
    [
        (20260801, 2026080101, ["SDG1", "SDG2"], "llama3.2", "2026-08-01", ["SDG1", "SDG2"]),
        (20260801, 2026080102, ["SDG3", "SDG4"], "llama3.2", "2026-08-01", ["SDG3", "SDG4"]),
        # (20260801, 2026080101, "['SDG1', 'SDG2']", "llama3.2", "2026-08-01", ["SDG1", "SDG2"]),
        # (20260801, 2026080102, "['SDG3', 'SDG4']", "llama3.2", "2026-08-01", ["SDG3", "SDG4"]),
    ],
)
def test_get_sdg_by_section_id(conn, briefing_id, section_id, sdgs, model, created_at, expected):
    """Test retrieving SDG list from sdg table."""
    insert_into_sdg(
        conn=conn,
        briefing_id=briefing_id,
        section_id=section_id,
        sdgs=sdgs,
        model=model,
        created_at=created_at,
    )
    result = get_sdg_by_section_id(conn=conn, section_id=section_id, model=model)
    assert result == expected


@pytest.mark.parametrize(
    "briefing_id,section_id,sdgs,model,created_at,expected",
    [
        (20260801, 2026080101, ["SDG1", "SDG2"], "llama3.2", "2026-08-01", "llama3.2"),
        (20260801, 2026080102, ["SDG3", "SDG4"], "mistral", "2026-08-01", "mistral"),
    ],
)
def test_get_models_for_sdg(conn, briefing_id, section_id, sdgs, model, created_at, expected):
    """Test retrieving a list of LLM models from the sdg table."""
    insert_into_sdg(
        conn=conn,
        briefing_id=briefing_id,
        section_id=section_id,
        sdgs=sdgs,
        model=model,
        created_at=created_at,
    )
    result = get_models(conn=conn, table="sdg")
    assert isinstance(result, list)
    assert expected in result


@pytest.mark.parametrize(
    "briefing_id,section_id,issues,model,created_at",
    [
        (20260801, 2026080101, "['ISSUE-1', 'ISSUE-2']", "llama3.2", "2026-08-01"),
        (20260801, 2026080102, "['ISSUE-3', 'ISSUE-4']", "llama3.2", "2026-08-01"),
    ],
)
def test_insert_into_issue(conn, briefing_id, section_id, issues, model, created_at):
    """Test insert data into the issue table."""
    # GIVEN a database connection
    # WHEN inserting data into the issue table
    insert_into_issue(
        conn=conn,
        briefing_id=briefing_id,
        section_id=section_id,
        issues=issues,
        model=model,
        created_at=created_at,
    )
    result_df = get_issues_between_dates(conn=conn, start_date=created_at, end_date=created_at)

    # THEN data is returned from the database
    assert result_df.shape[0] > 0


@pytest.mark.parametrize(
    "briefing_id,section_id,issues,model,created_at",
    [
        (20260801, 2026080101, "['ISSUE-1', 'ISSUE-2']", "llama3.2", "2026-08-01"),
        (20260801, 2026080102, "['ISSUE-3', 'ISSUE-4']", "llama3.2", "2026-08-01"),
    ],
)
def test_delete_from_issue(conn, briefing_id, section_id, issues, model, created_at):
    """Test deleting data from issue."""
    insert_into_issue(
        conn=conn,
        briefing_id=briefing_id,
        section_id=section_id,
        issues=issues,
        model=model,
        created_at=created_at,
    )
    result_df = get_issues_between_dates(conn=conn, start_date=created_at, end_date=created_at)
    assert result_df.shape[0] > 0

    delete_from_issue(conn=conn, section_id=section_id, model=model)
    result_df = get_issues_between_dates(conn=conn, start_date=created_at, end_date=created_at)
    assert result_df.shape[0] == 0


@pytest.mark.parametrize(
    "briefing_id,section_id,issues,model,created_at",
    [
        (20260801, 2026080101, "['ISSUE-1', 'ISSUE-2']", "llama3.2", "2026-08-01"),
        (20260801, 2026080102, "['ISSUE-3', 'ISSUE-4']", "llama3.2", "2026-08-01"),
    ],
)
def test_get_issues_between_dates(conn, briefing_id, section_id, issues, model, created_at):
    """Test retrieving data from the issue table."""
    insert_into_issue(
        conn=conn,
        briefing_id=briefing_id,
        section_id=section_id,
        issues=issues,
        model=model,
        created_at=created_at,
    )
    result_df = get_issues_between_dates(conn=conn, start_date=created_at, end_date=created_at)
    assert result_df.shape[0] > 0


def test_load_briefing_to_db(briefing, conn):
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


def test_load_briefing_to_db_invalid_file(conn):
    """Test loading an invalid file returns False."""
    file_path = Path("tests/fixtures/nonexistent.json")
    result = load_briefing_to_db(file_path=file_path, conn=conn)
    assert result is False


def test_load_briefings_between_dates_empty_range(conn):
    """Test load_between_dates with empty date range."""
    # GIVEN a database connection
    # WHEN using provided conn fixture (already has briefing_2026-08-25.json)
    briefings_path = Path("tests/fixtures/briefings")
    result = load_briefings_between_dates(
        start_date=date(2025, 9, 1),
        end_date=date(2025, 9, 30),
        conn=conn,
        briefings_dir=briefings_path,
    )

    # THEN returns True (existing briefing in DB + no other files exist)
    assert result is True


def test_load_briefings_between_dates_dry_run(conn, caplog) -> None:
    """Tests dry run using JSON files in `tests/fixtures`"""
    briefings_path = Path("tests/fixtures/briefings")
    _ = load_briefings_between_dates(
        date(2026, 6, 12), date(2026, 8, 25), dry_run=True, conn=conn, briefings_dir=briefings_path
    )
    assert "DRY RUN - No changes will be made:" in caplog.text
    assert "Total: 75 dates requested." in caplog.text
    assert "[2026-06-12] Would load" in caplog.text
    assert "[2026-06-29] Would load" in caplog.text
    assert "[2026-08-25] Would load" in caplog.text
    assert "No JSON file for 2026-06-13" in caplog.text


@pytest.mark.parametrize(
    "start_date,end_date,expected",
    [
        (date(2026, 6, 12), date(2026, 6, 12), True),
        (date(2026, 6, 29), date(2026, 6, 29), True),
        (date(2026, 8, 25), date(2026, 8, 25), True),
    ],
)
def test_load_briefings_between_dates_success(start_date, end_date, expected, conn):
    """Tests successful load of briefings to the database"""
    briefings_path = Path("tests/fixtures/briefings")
    result = load_briefings_between_dates(
        start_date, end_date, conn=conn, briefings_dir=briefings_path
    )
    assert result is expected


@pytest.mark.parametrize(
    "start_date,end_date,expected",
    [
        (date(2026, 6, 13), date(2026, 6, 13), False),
        (date(2026, 6, 30), date(2026, 6, 30), False),
        (date(2026, 8, 26), date(2026, 8, 26), False),
    ],
)
def test_load_briefings_between_dates_returns_false_on_failure(
    start_date, end_date, expected, monkeypatch, conn
):
    """Tests unsuccessful load of briefings to the database"""
    monkeypatch.setattr(
        db_module, "_load_dates", lambda *args, **kwargs: [start_date.strftime("%Y-%m-%d")]
    )
    briefings_path = Path("tests/fixtures/briefings")
    result = load_briefings_between_dates(
        start_date, end_date, conn=conn, briefings_dir=briefings_path
    )
    assert result is expected


@pytest.mark.parametrize(
    "start_date,end_date,expected",
    [
        (date(2026, 6, 13), date(2026, 6, 13), "No JSON file for 2026-06-13, would skip"),
        (date(2026, 6, 30), date(2026, 6, 30), "No JSON file for 2026-06-30, would skip"),
        (date(2026, 8, 26), date(2026, 8, 26), "No JSON file for 2026-08-26, would skip"),
    ],
)
def test_load_briefings_between_dates_skips_missing_json_files(
    start_date, end_date, expected, conn, caplog
):
    """Tests that correctly skips missing files"""
    briefings_path = Path("tests/fixtures/briefings")
    _ = load_briefings_between_dates(
        start_date, end_date, dry_run=True, conn=conn, briefings_dir=briefings_path
    )
    assert "DRY RUN - No changes will be made:" in caplog.text
    assert expected in caplog.text


@pytest.mark.parametrize(
    "input_date,expected",
    [
        (date(2024, 1, 1), "No briefing found for 2024-01-01"),
        (date(2026, 8, 25), "Briefing found for 2026-08-25"),
    ],
)
def test_query_briefing_by_date(input_date, expected, conn, briefing, caplog):
    """Test query_briefing_by_date runs without error when no briefing exists."""
    insert_into_briefing(conn=conn, briefing=briefing)
    query_briefing_by_date(conn=conn, query_date=input_date)
    assert expected in caplog.text


@pytest.mark.parametrize(
    "status,expected",
    [
        ("available", "Found 1 briefings with status 'available'"),
        ("available", "2026-08-25"),
        ("not_published", "Found 0 briefings with status 'not_published'"),
        ("failed", "Found 0 briefings with status 'failed'"),
    ],
)
def test_query_briefing_by_status_specific(status, expected, conn, briefing, caplog):
    """Test query_briefing_by_status filters correctly by a specific status."""
    insert_into_briefing(conn=conn, briefing=briefing)
    query_briefing_by_status(conn=conn, status=status)
    assert expected in caplog.text


def test_query_briefing_by_status_all(conn, briefing, caplog):
    """Test query_briefing_by_status returns all briefings when status='all'."""
    _ = insert_into_briefing(conn=conn, briefing=briefing)
    query_briefing_by_status(conn=conn, status="all")  # type: ignore
    assert "Found 1 briefings with status 'all'" in caplog.text
    assert "2026-08-25" in caplog.text


def test_show_stats_empty_db(conn, caplog):
    """Test show_stats runs without error on an empty database."""
    show_stats(conn=conn)
    assert "Total briefings: 0" in caplog.text
    assert "Date range: None to None" in caplog.text


def test_show_stats_with_data(conn, briefing, caplog):
    """Test show_stats runs without error when briefings exist."""
    _ = insert_into_briefing(conn=conn, briefing=briefing)
    show_stats(conn=conn)
    assert "Total briefings: 1" in caplog.text
    assert "Date range: 2026-08-25 to 2026-08-25" in caplog.text
    assert "available: 1" in caplog.text


# -- sdg queries


@pytest.mark.parametrize(
    "start_date,end_date,status,expected",
    [
        (date(2026, 6, 12), date(2026, 6, 12), "available", ["2026-06-12"]),
        (date(2026, 6, 29), date(2026, 6, 29), "available", ["2026-06-29"]),
        (date(2026, 8, 25), date(2026, 8, 25), "available", ["2026-08-25"]),
        (
            date(2026, 6, 12),
            date(2026, 6, 29),
            "available",
            ["2026-06-12", "2026-06-29"],
        ),
        (date(2026, 8, 25), date(2026, 8, 25), "not_published", []),
        (date(2026, 8, 25), date(2026, 8, 25), "failed", []),
    ],
)
def test_get_dates_with_briefings(conn, start_date, end_date, status, expected):
    """Tests retrieving the dates with brifings in the database given a status."""
    briefings_path = Path("tests/fixtures/briefings")
    _ = load_briefings_between_dates(start_date, end_date, conn=conn, briefings_dir=briefings_path)
    result = get_dates_with_briefings(conn=conn, status=status)
    assert result == expected


@pytest.mark.parametrize(
    "start_date,end_date,status,expected",
    [
        (date(2026, 6, 12), date(2026, 6, 12), "available", ("2026-06-12", "2026-06-12")),
        (date(2026, 6, 29), date(2026, 6, 29), "available", ("2026-06-29", "2026-06-29")),
        (date(2026, 8, 25), date(2026, 8, 25), "available", ("2026-08-25", "2026-08-25")),
        (
            date(2026, 6, 12),
            date(2026, 8, 25),
            "available",
            ("2026-06-12", "2026-08-25"),
        ),
        (date(2026, 8, 25), date(2026, 8, 25), "not_published", (None, None)),
        (date(2026, 8, 25), date(2026, 8, 25), "failed", (None, None)),
    ],
)
def test_get_min_max_dates(conn, start_date, end_date, status, expected):
    """Tests retrieving the min and max dates with briefings of a given status."""
    briefings_path = Path("tests/fixtures/briefings")
    _ = load_briefings_between_dates(start_date, end_date, conn=conn, briefings_dir=briefings_path)
    result = get_min_max_dates(conn=conn, status=status)
    assert result == expected


@pytest.mark.parametrize(
    "briefing_id,section_id,country,iso_2,iso_3,model,created_at",
    [
        (20260801, 2026080101, "Chile", "CL", "CHL", "qwen3.5:4b", "2026-08-01"),
        (20260801, 2026080102, "Germany", "DE", "DEU", "qwen3.5:4b", "2026-08-02"),
    ],
)
def test_get_country_mentions_by_date(
    conn, briefing_id, section_id, country, iso_2, iso_3, model, created_at
):
    """Test retrieving country mentions."""
    insert_into_country(
        conn=conn,
        briefing_id=briefing_id,
        section_id=section_id,
        country=country,
        iso_2=iso_2,
        iso_3=iso_3,
        model=model,
        created_at=created_at,
    )
    start_date = "2026-08-01"
    end_date = "2026-08-02"
    result = get_country_mentions_by_date(
        conn=conn, model=model, start_date=start_date, end_date=end_date
    )
    assert result.shape[0] == 1


@pytest.mark.parametrize(
    "briefing_id,section_id,country,iso_2,iso_3,model,created_at,expected",
    [
        (20260801, 2026080101, "Chile", "CL", "CHL", "qwen3.5:4b", "2026-08-01", ["CL"]),
        (20260801, 2026080102, "Germany", "DE", "DEU", "qwen3.5:4b", "2026-08-02", ["DE"]),
    ],
)
def test_get_countries_by_section_id(
    conn, briefing_id, section_id, country, iso_2, iso_3, model, created_at, expected
):
    """Tests retrieving country lists based on the section_id."""
    insert_into_country(
        conn=conn,
        briefing_id=briefing_id,
        section_id=section_id,
        country=country,
        iso_2=iso_2,
        iso_3=iso_3,
        model=model,
        created_at=created_at,
    )
    result = get_countries_by_section_id(conn=conn, section_id=section_id, model=model)
    assert result == expected


@pytest.mark.parametrize(
    "briefing_id,section_id,country,iso_2,iso_3,model,created_at,iso_2_check,expected",
    [
        (20260801, 2026080101, "Chile", "CL", "CHL", "qwen3.5:4b", "2026-08-01", "CL", True),
        (20260801, 2026080101, "Chile", "CL", "CHL", "qwen3.5:4b", "2026-08-01", "BR", False),
        (20260801, 2026080102, "Germany", "DE", "DEU", "qwen3.5:4b", "2026-08-02", "DE", True),
    ],
)
def test_check_country_section_model_exists(
    conn, briefing_id, section_id, country, iso_2, iso_3, model, created_at, iso_2_check, expected
):
    """Test if a country mentions has been processed for a given section_id and model."""
    insert_into_country(
        conn=conn,
        briefing_id=briefing_id,
        section_id=section_id,
        country=country,
        iso_2=iso_2,
        iso_3=iso_3,
        model=model,
        created_at=created_at,
    )
    result = check_country_section_model_exists(
        conn=conn, section_id=section_id, iso_2=iso_2_check, model=model
    )
    assert result is expected


@pytest.mark.parametrize(
    "briefing_id,section_id,country,iso_2,iso_3,model,created_at,model_check,expected",
    [
        (
            20260801,
            2026080101,
            "Chile",
            "CL",
            "CHL",
            "qwen3.5:4b",
            "2026-08-01",
            "qwen3.5:4b",
            True,
        ),
        (
            20260801,
            2026080101,
            "Chile",
            "CL",
            "CHL",
            "qwen3.5:4b",
            "2026-08-01",
            "llama3.2",
            False,
        ),
        (
            20260801,
            2026080102,
            "Germany",
            "DE",
            "DEU",
            "qwen3.5:4b",
            "2026-08-02",
            "qwen3.5:4b",
            True,
        ),
    ],
)
def test__check_country_section_exists(
    conn, briefing_id, section_id, country, iso_2, iso_3, model, created_at, model_check, expected
):
    """Tests if a model has been used to process a given section."""
    insert_into_country(
        conn=conn,
        briefing_id=briefing_id,
        section_id=section_id,
        country=country,
        iso_2=iso_2,
        iso_3=iso_3,
        model=model,
        created_at=created_at,
    )
    result = _check_country_section_exists(conn=conn, section_id=section_id, model=model_check)
    assert result is expected


@pytest.mark.parametrize(
    "analysis_name,model_name,model_version,ollama_version,prompt_version,prompt,temperature",
    [
        ("analysis test 1", "llama3.2", "3.2", "1", "v4", "prompt test", 0),
        ("analysis test 2", "llama3.2", "3.2", "1", "v4", "prompt test", 0),
    ],
)
def test_insert_into_analysis_run(
    conn,
    analysis_name,
    model_name,
    model_version,
    ollama_version,
    prompt_version,
    prompt,
    temperature,
):
    """Test inserting data into the analysis_run table."""
    result = insert_into_analysis_run(
        conn=conn,
        analysis_name=analysis_name,
        model_name=model_name,
        model_version=model_version,
        ollama_version=ollama_version,
        prompt_version=prompt_version,
        prompt=prompt,
        temperature=temperature,
    )
    assert result == 1


@pytest.mark.parametrize(
    "analysis_name,model_name,model_version,ollama_version,prompt_version,prompt,temperature,analysis_id",
    [
        ("analysis test 1", "llama3.2", "3.2", "1", "v4", "prompt test", 0, 1),
        ("analysis test 2", "llama3.2", "3.2", "1", "v4", "prompt test", 0, 1),
    ],
)
def test_get_analysis_run(
    conn,
    analysis_name,
    model_name,
    model_version,
    ollama_version,
    prompt_version,
    prompt,
    temperature,
    analysis_id,
):
    """Tests retrieving data from the analysis_run table."""
    _ = insert_into_analysis_run(
        conn=conn,
        analysis_name=analysis_name,
        model_name=model_name,
        model_version=model_version,
        ollama_version=ollama_version,
        prompt_version=prompt_version,
        prompt=prompt,
        temperature=temperature,
    )
    result = get_analysis_run(conn=conn, analysis_id=analysis_id)
    assert isinstance(result, sqlite3.Row)
    assert result["analysis_id"] == 1
    assert result["model_name"] == model_name


@pytest.mark.parametrize(
    "briefing_path,start_date,end_date,expected",
    [
        ("tests/fixtures/briefings/2026/2026-08/2026-08-25.json", "2026-08-25", "2026-08-25", 14),
        ("tests/fixtures/briefings/2026/2026-06/2026-06-29.json", "2026-06-29", "2026-06-29", 13),
        ("tests/fixtures/briefings/2026/2026-06/2026-06-12.json", "2026-06-12", "2026-06-12", 11),
        ("tests/fixtures/briefings/2025/2025-01/2025-01-28.json", "2025-01-28", "2025-01-28", 9),
    ],
)
def test_get_sections_for_sentiment_analysis(conn, briefing_path, start_date, end_date, expected):
    """Test retrieving non empty sections for sentiment analysis."""
    load_briefing_to_db(file_path=Path(briefing_path), conn=conn)
    result_df = get_sections_for_sentiment_analysis(
        conn=conn, start_date=start_date, end_date=end_date
    )
    assert result_df.shape[0] == expected


@pytest.mark.parametrize(
    "analysis_name,model_name,model_version,ollama_version,prompt_version,prompt,temperature,analysis_id,briefing_id,section_id,briefing_date,sentiment,tone,status,error_message",
    [
        (
            "analysis test 1",
            "llama3.2",
            "3.2",
            "1",
            "v4",
            "prompt test",
            0,
            1,
            20260901,
            2026090101,
            "2026-09-01",
            "Positive",
            "Neutral/Informational",
            "success",
            None,
        )
    ],
)
def test_insert_sentiment_analysis(
    conn,
    analysis_name,
    model_name,
    model_version,
    ollama_version,
    prompt_version,
    prompt,
    temperature,
    analysis_id,
    briefing_id,
    section_id,
    briefing_date,
    sentiment,
    tone,
    status,
    error_message,
):
    """Test inserting data into sentiment_analysis table."""
    # needs to insert into analysis_run first due foreign key constraint
    _ = insert_into_analysis_run(
        conn=conn,
        analysis_name=analysis_name,
        model_name=model_name,
        model_version=model_version,
        ollama_version=ollama_version,
        prompt_version=prompt_version,
        prompt=prompt,
        temperature=temperature,
    )
    insert_sentiment_analysis(
        conn=conn,
        analysis_id=analysis_id,
        briefing_id=briefing_id,
        section_id=section_id,
        briefing_date=briefing_date,
        sentiment=sentiment,
        tone=tone,
        status=status,
        error_message=error_message,
    )
    result_ids = get_completed_section_ids(conn, analysis_id=analysis_id)
    assert result_ids == {section_id}


@pytest.mark.parametrize(
    "analysis_name,model_name,model_version,ollama_version,prompt_version,prompt,temperature,analysis_id,briefing_id,section_id,briefing_date,sentiment,tone,status,error_message,briefing_path",
    [
        (
            "analysis test 1",
            "llama3.2",
            "3.2",
            "1",
            "v4",
            "prompt test",
            0,
            1,
            20260825,
            2026082501,
            "2026-09-01",
            "Positive",
            "Neutral/Informational",
            "success",
            None,
            "tests/fixtures/briefings/2026/2026-08/2026-08-25.json",
        )
    ],
)
def test_get_sentiment_results(
    conn,
    analysis_name,
    model_name,
    model_version,
    ollama_version,
    prompt_version,
    prompt,
    temperature,
    analysis_id,
    briefing_id,
    section_id,
    briefing_date,
    sentiment,
    tone,
    status,
    error_message,
    briefing_path,
):
    """Test retrieving data of sentiment analysis."""
    load_briefing_to_db(file_path=Path(briefing_path), conn=conn)
    # needs to insert into analysis_run first due foreign key constraint
    _ = insert_into_analysis_run(
        conn=conn,
        analysis_name=analysis_name,
        model_name=model_name,
        model_version=model_version,
        ollama_version=ollama_version,
        prompt_version=prompt_version,
        prompt=prompt,
        temperature=temperature,
    )
    insert_sentiment_analysis(
        conn=conn,
        analysis_id=analysis_id,
        briefing_id=briefing_id,
        section_id=section_id,
        briefing_date=briefing_date,
        sentiment=sentiment,
        tone=tone,
        status=status,
        error_message=error_message,
    )
    result_df = get_sentiment_results(conn=conn, analysis_id=analysis_id)
    assert result_df.shape[0] == 1
    assert result_df.iloc[0]["sentiment"] == sentiment
    columns = [
        "analysis_result_id",
        "analysis_id",
        "briefing_id",
        "section_id",
        "briefing_date",
        "section_order",
        "title",
        "section_text",
        "sentiment",
        "tone",
        "status",
        "error_message",
        "created_at",
    ]
    for column in columns:
        assert column in result_df.columns


@pytest.mark.parametrize(
    "analysis_name,model_name,model_version,ollama_version,prompt_version,prompt,temperature,analysis_id,briefing_id,section_id,briefing_date,sentiment,tone,status,error_message",
    [
        (
            "analysis test 1",
            "llama3.2",
            "3.2",
            "1",
            "v4",
            "prompt test",
            0,
            1,
            20260901,
            2026090101,
            "2026-09-01",
            "Positive",
            "Neutral/Informational",
            "success",
            None,
        )
    ],
)
def test_get_sentiment_distribution(
    conn,
    analysis_name,
    model_name,
    model_version,
    ollama_version,
    prompt_version,
    prompt,
    temperature,
    analysis_id,
    briefing_id,
    section_id,
    briefing_date,
    sentiment,
    tone,
    status,
    error_message,
):
    """Test retrieving sentiment data."""
    # needs to insert into analysis_run first due foreign key constraint
    _ = insert_into_analysis_run(
        conn=conn,
        analysis_name=analysis_name,
        model_name=model_name,
        model_version=model_version,
        ollama_version=ollama_version,
        prompt_version=prompt_version,
        prompt=prompt,
        temperature=temperature,
    )
    insert_sentiment_analysis(
        conn=conn,
        analysis_id=analysis_id,
        briefing_id=briefing_id,
        section_id=section_id,
        briefing_date=briefing_date,
        sentiment=sentiment,
        tone=tone,
        status=status,
        error_message=error_message,
    )
    result_df = get_sentiment_distribution(conn=conn, analysis_id=analysis_id)
    assert "sentiment" in result_df.columns
    assert "count" in result_df.columns
    assert result_df.shape[0] == 1


@pytest.mark.parametrize(
    "analysis_name,model_name,model_version,ollama_version,prompt_version,prompt,temperature,analysis_id,briefing_id,section_id,briefing_date,sentiment,tone,status,error_message",
    [
        (
            "analysis test 1",
            "llama3.2",
            "3.2",
            "1",
            "v4",
            "prompt test",
            0,
            1,
            20260901,
            2026090101,
            "2026-09-01",
            "Positive",
            "Neutral/Informational",
            "success",
            None,
        )
    ],
)
def test_get_tone_distribution(
    conn,
    analysis_name,
    model_name,
    model_version,
    ollama_version,
    prompt_version,
    prompt,
    temperature,
    analysis_id,
    briefing_id,
    section_id,
    briefing_date,
    sentiment,
    tone,
    status,
    error_message,
):
    """Test retrieving tone data."""
    # needs to insert into analysis_run first due foreign key constraint
    _ = insert_into_analysis_run(
        conn=conn,
        analysis_name=analysis_name,
        model_name=model_name,
        model_version=model_version,
        ollama_version=ollama_version,
        prompt_version=prompt_version,
        prompt=prompt,
        temperature=temperature,
    )
    insert_sentiment_analysis(
        conn=conn,
        analysis_id=analysis_id,
        briefing_id=briefing_id,
        section_id=section_id,
        briefing_date=briefing_date,
        sentiment=sentiment,
        tone=tone,
        status=status,
        error_message=error_message,
    )
    result_df = get_tone_distribution(conn, analysis_id=1)
    assert "tone" in result_df.columns
    assert "count" in result_df.columns
    assert result_df.shape[0] == 1


@pytest.mark.parametrize(
    "analysis_name,model_name,model_version,ollama_version,prompt_version,prompt,temperature,expected",
    [
        ("analysis test 1", "llama3.2", "3.2", "1", "v4", "prompt test", 0, 1),
        ("analysis test 2", "llama3.2", "3.2", "1", "v4", "prompt test", 0, 1),
    ],
)
def test_get_latest_analysis_run(
    conn,
    analysis_name,
    model_name,
    model_version,
    ollama_version,
    prompt_version,
    prompt,
    temperature,
    expected,
):
    """Test retrieving latest analysis"""
    _ = insert_into_analysis_run(
        conn=conn,
        analysis_name=analysis_name,
        model_name=model_name,
        model_version=model_version,
        ollama_version=ollama_version,
        prompt_version=prompt_version,
        prompt=prompt,
        temperature=temperature,
    )
    result = get_latest_analysis_run(conn=conn, analysis_name=analysis_name)
    assert result == expected


@pytest.mark.parametrize(
    "analysis_name,model_name,model_version,ollama_version,prompt_version,prompt,temperature,analysis_id,briefing_id,section_id,briefing_date,sentiment,tone,status,error_message,expected",
    [
        (
            "analysis test 1",
            "llama3.2",
            "3.2",
            "1",
            "v4",
            "prompt test",
            0,
            1,
            20260901,
            2026090101,
            "2026-09-01",
            "Positive",
            "Neutral/Informational",
            "success",
            None,
            1,
        ),
        (
            "analysis test 2",
            "llama3.2",
            "3.2",
            "1",
            "v4",
            "prompt test",
            0,
            1,
            20260901,
            2026090101,
            "2026-09-01",
            "Positive",
            "Neutral/Informational",
            "error",
            None,
            0,
        ),
    ],
)
def test_count_successful_sections(
    conn,
    analysis_name,
    model_name,
    model_version,
    ollama_version,
    prompt_version,
    prompt,
    temperature,
    analysis_id,
    briefing_id,
    section_id,
    briefing_date,
    sentiment,
    tone,
    status,
    error_message,
    expected,
):
    """Test counting successful sections of sentiment analysis"""
    _ = insert_into_analysis_run(
        conn=conn,
        analysis_name=analysis_name,
        model_name=model_name,
        model_version=model_version,
        ollama_version=ollama_version,
        prompt_version=prompt_version,
        prompt=prompt,
        temperature=temperature,
    )
    insert_sentiment_analysis(
        conn=conn,
        analysis_id=analysis_id,
        briefing_id=briefing_id,
        section_id=section_id,
        briefing_date=briefing_date,
        sentiment=sentiment,
        tone=tone,
        status=status,
        error_message=error_message,
    )
    result = count_successful_sections(conn=conn, analysis_id=analysis_id)
    assert result == expected
