import argparse
from argparse import Namespace
from datetime import date, datetime, timedelta
import json
from zoneinfo import ZoneInfo

import pytest

import un_llm_analysis.scraper as scraper
from un_llm_analysis.scraper import _dates_between, _parse_date


def test_parse_date_valid():
    # GIVEN a valid date
    date_string = "2026-08-01"

    # WHEN _parse_date is called
    result = _parse_date(date_string)

    # THEN the result should match the expected date
    assert result == date(2026, 8, 1)


def test_parse_date_invalid():
    # GIVEN an invalid date
    date_string = "2026-02-30"

    # WHEN _parse_date is called
    # THEN ArgumentTypeError is raised.
    with pytest.raises(argparse.ArgumentTypeError):
        _parse_date(date_string)


def test_dates_between():
    # GIVEN a start date and an end date
    start_date = date(2026, 1, 30)
    end_date = date(2026, 2, 1)
    expected_dates = [date(2026, 1, 30), date(2026, 1, 31), date(2026, 2, 1)]

    # WHEN _dates_between is called
    result = list(_dates_between(start_date, end_date))

    # THEN the result should match the expected dates
    assert result == expected_dates


@pytest.mark.parametrize(
    "status, expected",
    [
        ("available", True),
        ("not_published", True),
        ("failed", False),
    ],
)
def test_is_briefing_scraped_status(
    tmp_path,
    monkeypatch,
    status,
    expected,
):
    """Test different briefing statuses."""

    briefing_date = date(2026, 8, 20)

    briefing_dir = tmp_path / "briefings"

    briefing_path = briefing_dir / "2026" / "2026-08" / "2026-08-20.json"

    briefing_path.parent.mkdir(parents=True)

    with open(briefing_path, "w", encoding="utf-8") as f:
        json.dump({"status": status}, f)

    monkeypatch.setattr(scraper, "BRIEFINGS_DIR", str(briefing_dir))

    result = scraper._is_briefing_scraped(briefing_date)

    assert result is expected


def test_is_briefing_scraped_returns_false_when_file_missing(
    tmp_path,
    monkeypatch,
):
    """Return False when no briefing file exists."""

    monkeypatch.setattr(
        scraper,
        "BRIEFINGS_DIR",
        str(tmp_path / "briefings"),
    )

    assert scraper._is_briefing_scraped(date(2026, 8, 20)) is False


def test_is_briefing_scraped_returns_false_for_invalid_json(
    tmp_path,
    monkeypatch,
):
    """Return False when the briefing file contains invalid JSON."""

    briefing_dir = tmp_path / "briefings"
    briefing_path = briefing_dir / "2026" / "2026-08" / "2026-08-20.json"

    briefing_path.parent.mkdir(parents=True)
    briefing_path.write_text("{invalid json", encoding="utf-8")

    monkeypatch.setattr(scraper, "BRIEFINGS_DIR", str(briefing_dir))

    assert scraper._is_briefing_scraped(date(2026, 8, 20)) is False


def test_build_parser_update_single_date():
    """Parse an update command with one date."""

    parser = scraper._build_parser()

    args = parser.parse_args(
        [
            "update",
            "2026-08-12",
        ]
    )

    assert args.command == "update"
    assert args.dates == [date(2026, 8, 12)]
    assert args.since is None
    assert args.overwrite is False


def test_build_parser_update_date_range():
    """Parse an update command with a date range."""

    parser = scraper._build_parser()

    args = parser.parse_args(
        [
            "update",
            "2026-08-01",
            "2026-08-12",
        ]
    )

    assert args.command == "update"
    assert args.dates == [
        date(2026, 8, 1),
        date(2026, 8, 12),
    ]
    assert args.since is None
    assert args.overwrite is False


def test_build_parser_update_since():
    """Parse an update command using --since."""

    parser = scraper._build_parser()

    args = parser.parse_args(
        [
            "update",
            "--since",
            "2026-08-01",
        ]
    )

    assert args.command == "update"
    assert args.dates == []
    assert args.since == date(2026, 8, 1)
    assert args.overwrite is False


def test_build_parser_update_overwrite():
    """Parse the --overwrite option."""

    parser = scraper._build_parser()

    args = parser.parse_args(
        [
            "update",
            "2026-08-12",
            "--overwrite",
        ]
    )

    assert args.command == "update"
    assert args.dates == [date(2026, 8, 12)]
    assert args.since is None
    assert args.overwrite is True


def test_build_parser_check():
    """Parse a check command."""

    parser = scraper._build_parser()

    args = parser.parse_args(
        [
            "check",
            "2026-08-12",
        ]
    )

    assert args.command == "check"
    assert args.date == date(2026, 8, 12)


def test_build_parser_missing_command():
    """Reject arguments when no command is provided."""

    parser = scraper._build_parser()

    with pytest.raises(SystemExit):
        parser.parse_args([])


def test_resolve_update_request_single_date():
    parser = scraper._build_parser()

    args = Namespace(
        dates=[date(2026, 8, 20)],
        since=None,
        overwrite=False,
    )

    start_date, end_date, overwrite = scraper._resolve_update_request(
        parser,
        args,
    )

    assert start_date == date(2026, 8, 20)
    assert end_date == date(2026, 8, 20)
    assert overwrite is False


def test_resolve_update_request_date_range():
    parser = scraper._build_parser()

    args = Namespace(
        dates=[date(2026, 8, 1), date(2026, 8, 20)],
        since=None,
        overwrite=False,
    )

    start_date, end_date, overwrite = scraper._resolve_update_request(
        parser,
        args,
    )

    assert start_date == date(2026, 8, 1)
    assert end_date == date(2026, 8, 20)
    assert overwrite is False


def test_resolve_update_request_since(monkeypatch):
    class FixedDateTime(datetime):
        @classmethod
        def now(cls, tz=None):
            return cls(2026, 8, 23, tzinfo=tz)

    monkeypatch.setattr(scraper, "datetime", FixedDateTime)

    parser = scraper._build_parser()

    since_date = date(2026, 8, 1)

    args = Namespace(
        dates=[],
        since=since_date,
        overwrite=False,
    )

    start_date, end_date, overwrite = scraper._resolve_update_request(
        parser,
        args,
    )

    expected_today = date(2026, 8, 23)

    assert start_date == since_date
    assert end_date == expected_today
    assert overwrite is False


def test_resolve_update_request_overwrite():
    parser = scraper._build_parser()

    args = Namespace(
        dates=[date(2026, 8, 20)],
        since=None,
        overwrite=True,
    )

    start_date, end_date, overwrite = scraper._resolve_update_request(
        parser,
        args,
    )

    assert start_date == date(2026, 8, 20)
    assert end_date == date(2026, 8, 20)
    assert overwrite is True


def test_resolve_update_request_since_with_dates():
    parser = scraper._build_parser()

    args = Namespace(
        dates=[date(2026, 8, 20)],
        since=date(2026, 8, 1),
        overwrite=False,
    )

    with pytest.raises(SystemExit):
        scraper._resolve_update_request(parser, args)


def test_resolve_update_request_too_many_dates():
    parser = scraper._build_parser()

    args = Namespace(
        dates=[
            date(2026, 8, 1),
            date(2026, 8, 10),
            date(2026, 8, 20),
        ],
        since=None,
        overwrite=False,
    )

    with pytest.raises(SystemExit):
        scraper._resolve_update_request(parser, args)


def test_resolve_update_request_no_dates():
    parser = scraper._build_parser()

    args = Namespace(
        dates=[],
        since=None,
        overwrite=False,
    )

    with pytest.raises(SystemExit):
        scraper._resolve_update_request(parser, args)


def test_resolve_update_request_start_after_end():
    parser = scraper._build_parser()

    args = Namespace(
        dates=[date(2026, 8, 20), date(2026, 8, 1)],
        since=None,
        overwrite=False,
    )

    with pytest.raises(SystemExit):
        scraper._resolve_update_request(parser, args)


def test_resolve_update_request_before_min_scrape_date():
    parser = scraper._build_parser()

    invalid_date = scraper.MIN_SCRAPE_DATE - timedelta(days=1)

    args = Namespace(
        dates=[invalid_date],
        since=None,
        overwrite=False,
    )

    with pytest.raises(SystemExit):
        scraper._resolve_update_request(parser, args)


def test_resolve_update_request_date_after_today(monkeypatch):
    class FixedDateTime(datetime):
        @classmethod
        def now(cls, tz=None):
            return cls(2026, 8, 23, tzinfo=tz)

    monkeypatch.setattr(scraper, "datetime", FixedDateTime)

    parser = scraper._build_parser()

    today = date(2026, 8, 23)
    tomorrow = today + timedelta(days=1)

    args = Namespace(
        dates=[tomorrow],
        since=None,
        overwrite=False,
    )

    with pytest.raises(SystemExit):
        scraper._resolve_update_request(parser, args)
