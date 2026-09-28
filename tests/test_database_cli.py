"""Unit tests for database_cli.py module."""

from datetime import date, datetime
from pathlib import Path
import sqlite3
from unittest.mock import MagicMock, patch
from zoneinfo import ZoneInfo

import pytest

from un_llm_analysis import database_cli as db_cli
from un_llm_analysis.config import SCHEMA_DB
from un_llm_analysis.database import (
    create_database,
    get_db_connection,
    insert_into_briefing,
)
from un_llm_analysis.database_cli import (
    _build_parser,
    _resolve_load_request,
    show_stats,
)
from un_llm_analysis.extractor import extract_briefing


def test_build_parser():
    """Test _build_parser creates parser with all subcommands."""
    parser = _build_parser()
    assert parser.description == "Manage UN noon briefing database."

    # Test init command
    args = parser.parse_args(["init"])
    assert args.command == "init"

    # Test load command
    args = parser.parse_args(["load", "2023-01-01"])
    assert args.command == "load"
    assert args.dates == [date(2023, 1, 1)]

    # Test query command
    args = parser.parse_args(["query", "--date", "2023-01-01"])
    assert args.command == "query"
    assert args.date == date(2023, 1, 1)

    # Test stats command
    args = parser.parse_args(["stats"])
    assert args.command == "stats"


def test_build_parser_load_with_since():
    """Test load parser with --since flag."""
    parser = _build_parser()
    args = parser.parse_args(["load", "--since", "2023-01-01"])
    assert args.command == "load"
    assert args.since == date(2023, 1, 1)
    assert args.dates == []


def test_build_parser_load_with_overwrite():
    """Test load parser with --overwrite flag."""
    parser = _build_parser()
    args = parser.parse_args(["load", "2023-01-01", "--overwrite"])
    assert args.command == "load"
    assert args.overwrite is True


def test_build_parser_load_with_dry_run():
    """Test load parser with --dry-run flag."""
    parser = _build_parser()
    args = parser.parse_args(["load", "2023-01-01", "--dry-run"])
    assert args.command == "load"
    assert args.dry_run is True


def test_build_parser_query_by_status():
    """Test query parser with --status flag."""
    parser = _build_parser()
    args = parser.parse_args(["query", "--status", "available"])
    assert args.command == "query"
    assert args.status == "available"


def test_build_parser_query_by_status_all():
    """Test query parser with --status all."""
    parser = _build_parser()
    args = parser.parse_args(["query", "--status", "all"])
    assert args.command == "query"
    assert args.status == "all"


def test_resolve_load_request_single_date():
    """Test _resolve_load_request with single date."""
    parser = _build_parser()
    args = parser.parse_args(["load", "2023-01-01"])
    start, end, overwrite, dry_run = _resolve_load_request(parser, args)
    assert start == date(2023, 1, 1)
    assert end == date(2023, 1, 1)
    assert overwrite is False
    assert dry_run is False


def test_resolve_load_request_date_range():
    """Test _resolve_load_request with date range."""
    parser = _build_parser()
    args = parser.parse_args(["load", "2023-01-01", "2023-12-31"])
    start, end, overwrite, dry_run = _resolve_load_request(parser, args)
    assert start == date(2023, 1, 1)
    assert end == date(2023, 12, 31)
    assert overwrite is False
    assert dry_run is False


def test_resolve_load_request_since():
    """Test _resolve_load_request with --since flag."""
    parser = _build_parser()
    args = parser.parse_args(["load", "--since", "2023-01-01"])
    start, end, overwrite, dry_run = _resolve_load_request(parser, args)
    assert start == date(2023, 1, 1)
    # end should be today
    today = datetime.now(ZoneInfo("America/New_York")).date()
    assert end == today
    assert overwrite is False
    assert dry_run is False


def test_resolve_load_request_with_overwrite():
    """Test _resolve_load_request with --overwrite flag."""
    parser = _build_parser()
    args = parser.parse_args(["load", "2023-01-01", "--overwrite"])
    start, end, overwrite, dry_run = _resolve_load_request(parser, args)
    assert overwrite is True


def test_resolve_load_request_with_dry_run():
    """Test _resolve_load_request with --dry-run flag."""
    parser = _build_parser()
    args = parser.parse_args(["load", "2023-01-01", "--dry-run"])
    start, end, overwrite, dry_run = _resolve_load_request(parser, args)
    assert dry_run is True


def test_resolve_load_request_since_with_dates_error():
    """Test _resolve_load_request errors when --since used with dates."""
    parser = _build_parser()
    args = parser.parse_args(["load", "2023-01-01", "--since", "2023-01-01"])
    with pytest.raises(SystemExit):
        _resolve_load_request(parser, args)


def test_resolve_load_request_too_many_dates_error():
    """Test _resolve_load_request errors with more than 2 dates."""
    parser = _build_parser()
    args = parser.parse_args(["load", "2023-01-01", "2023-01-02", "2023-01-03"])
    with pytest.raises(SystemExit):
        _resolve_load_request(parser, args)


def test_resolve_load_request_no_dates_error():
    """Test _resolve_load_request errors with no dates."""
    parser = _build_parser()
    args = parser.parse_args(["load"])
    with pytest.raises(SystemExit):
        _resolve_load_request(parser, args)


def test_resolve_load_request_start_after_end_error():
    """Test _resolve_load_request errors when start > end."""
    parser = _build_parser()
    args = parser.parse_args(["load", "2023-12-31", "2023-01-01"])
    with pytest.raises(SystemExit):
        _resolve_load_request(parser, args)


def test_resolve_load_request_before_min_date_error():
    """Test _resolve_load_request errors when date < MIN_SCRAPE_DATE."""
    parser = _build_parser()
    args = parser.parse_args(["load", "2004-01-01"])
    with pytest.raises(SystemExit):
        _resolve_load_request(parser, args)


def test_resolve_load_request_after_today_error():
    """Test _resolve_load_request errors when date > today."""
    parser = _build_parser()
    future_date = date(2099, 12, 31)
    args = parser.parse_args(["load", future_date.isoformat()])
    with pytest.raises(SystemExit):
        _resolve_load_request(parser, args)


@pytest.fixture(scope="function")
def conn():
    """Fixture serving an in-memory database connection."""
    conn = get_db_connection(":memory:")

    sql_schema = Path(SCHEMA_DB).read_text(encoding="utf-8")
    conn.executescript(sql_schema)

    yield conn

    conn.close()


@pytest.fixture()
def briefing():
    """Fixture with an ExtractedBriefing."""
    return extract_briefing(
        file_path=Path("tests/fixtures/briefings/2026/2026-08/2026-08-25.json")
    )


def test_show_stats_empty_db(monkeypatch, conn):
    """Test show_stats runs without error on an empty database."""
    monkeypatch.setattr(db_cli, "get_db_connection", lambda *a, **kw: conn)
    result = show_stats()
    assert result is None


def test_show_stats_with_data(monkeypatch, conn, briefing):
    """Test show_stats runs without error when briefings exist."""
    monkeypatch.setattr(db_cli, "get_db_connection", lambda *a, **kw: conn)
    insert_into_briefing(conn=conn, briefing=briefing)
    result = show_stats()
    assert result is None
