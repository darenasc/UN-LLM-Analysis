from argparse import Namespace
from datetime import date, datetime, timedelta
from unittest.mock import Mock

import pytest

from un_llm_analysis import main
from un_llm_analysis.main import MIN_SCRAPE_DATE, _build_parser, _resolve_update_request


@pytest.fixture
def fixed_today(monkeypatch):
    class FixedDateTime(datetime):
        @classmethod
        def now(cls, tz=None):
            return cls(2026, 8, 20, tzinfo=tz)

    monkeypatch.setattr(main, "datetime", FixedDateTime)

    return date(2026, 8, 20)


def test_build_parser_check():
    """Parse a check command."""

    parser = _build_parser()

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

    parser = _build_parser()

    with pytest.raises(SystemExit):
        parser.parse_args([])


def test_resolve_update_request_single_date():
    parser = _build_parser()

    args = Namespace(
        dates=[date(2026, 8, 20)],
        since=None,
        overwrite=False,
    )

    start_date, end_date, overwrite = _resolve_update_request(
        parser,
        args,
    )

    assert start_date == date(2026, 8, 20)
    assert end_date == date(2026, 8, 20)
    assert overwrite is False


def test_resolve_update_request_date_range():
    parser = _build_parser()

    args = Namespace(
        dates=[date(2026, 8, 1), date(2026, 8, 20)],
        since=None,
        overwrite=False,
    )

    start_date, end_date, overwrite = _resolve_update_request(
        parser,
        args,
    )

    assert start_date == date(2026, 8, 1)
    assert end_date == date(2026, 8, 20)
    assert overwrite is False


def test_build_parser_update_date_range():
    """Parse an update command with a date range."""

    parser = _build_parser()

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

    parser = _build_parser()

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

    parser = _build_parser()

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


def test_build_parser_update_single_date():
    """Parse an update command with one date."""

    parser = _build_parser()

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


def test_resolve_update_request_since(fixed_today):
    parser = _build_parser()

    since_date = date(2026, 8, 1)

    args = Namespace(
        dates=[],
        since=since_date,
        overwrite=False,
    )

    start_date, end_date, overwrite = _resolve_update_request(
        parser,
        args,
    )

    expected_today = fixed_today

    assert start_date == since_date
    assert end_date == expected_today
    assert overwrite is False


def test_resolve_update_request_overwrite():
    parser = _build_parser()

    args = Namespace(
        dates=[date(2026, 8, 20)],
        since=None,
        overwrite=True,
    )

    start_date, end_date, overwrite = _resolve_update_request(
        parser,
        args,
    )

    assert start_date == date(2026, 8, 20)
    assert end_date == date(2026, 8, 20)
    assert overwrite is True


def test_resolve_update_request_since_with_dates():
    parser = _build_parser()

    args = Namespace(
        dates=[date(2026, 8, 20)],
        since=date(2026, 8, 1),
        overwrite=False,
    )

    with pytest.raises(SystemExit):
        _resolve_update_request(parser, args)


def test_resolve_update_request_too_many_dates():
    parser = _build_parser()

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
        _resolve_update_request(parser, args)


def test_resolve_update_request_no_dates():
    parser = _build_parser()

    args = Namespace(
        dates=[],
        since=None,
        overwrite=False,
    )

    with pytest.raises(SystemExit):
        _resolve_update_request(parser, args)


def test_resolve_update_request_start_after_end():
    parser = _build_parser()

    args = Namespace(
        dates=[date(2026, 8, 20), date(2026, 8, 1)],
        since=None,
        overwrite=False,
    )

    with pytest.raises(SystemExit):
        _resolve_update_request(parser, args)


def test_resolve_update_request_before_min_scrape_date():
    parser = _build_parser()

    invalid_date = MIN_SCRAPE_DATE - timedelta(days=1)

    args = Namespace(
        dates=[invalid_date],
        since=None,
        overwrite=False,
    )

    with pytest.raises(SystemExit):
        _resolve_update_request(parser, args)


def test_resolve_update_request_date_after_today(fixed_today):
    parser = _build_parser()

    tomorrow = fixed_today + timedelta(days=1)

    args = Namespace(
        dates=[tomorrow],
        since=None,
        overwrite=False,
    )

    with pytest.raises(SystemExit):
        _resolve_update_request(parser, args)


@pytest.mark.parametrize("is_scraped", [True, False])
def test_main_check(monkeypatch, is_scraped):
    briefing_date = date(2026, 8, 20)

    fake_parser = Mock()
    fake_parser.parse_args.return_value = Namespace(
        command="check",
        date=briefing_date,
    )
    monkeypatch.setattr(main, "_build_parser", Mock(return_value=fake_parser))

    fake_is_briefing_scraped = Mock(return_value=is_scraped)
    monkeypatch.setattr(
        main,
        "_is_briefing_scraped",
        fake_is_briefing_scraped,
    )

    main.main()

    fake_is_briefing_scraped.assert_called_once_with(briefing_date)


def test_main_update(monkeypatch):
    args = Namespace(command="update")

    fake_parser = Mock()
    fake_parser.parse_args.return_value = args
    monkeypatch.setattr(main, "_build_parser", Mock(return_value=fake_parser))

    fake_resolve_update_request = Mock(
        return_value=(
            date(2026, 8, 1),
            date(2026, 8, 20),
            False,
        )
    )
    monkeypatch.setattr(
        main,
        "_resolve_update_request",
        fake_resolve_update_request,
    )

    fake_scrape_between_dates = Mock()
    monkeypatch.setattr(
        main,
        "scrape_between_dates",
        fake_scrape_between_dates,
    )

    main.main()

    fake_resolve_update_request.assert_called_once_with(fake_parser, args)
    fake_scrape_between_dates.assert_called_once_with(
        date(2026, 8, 1),
        date(2026, 8, 20),
        overwrite=False,
    )
