from argparse import Namespace
from datetime import date, datetime, timedelta
from unittest.mock import Mock
from zoneinfo import ZoneInfo

import pytest

from un_llm_analysis import main
from un_llm_analysis.main import (
    MIN_SCRAPE_DATE,
    _build_parser,
    _resolve_load_request,
    _resolve_update_request,
)


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


def test_main_init_db(monkeypatch, tmp_path):
    db_path = tmp_path / "test.db"
    args = Namespace(command="init-db", db_path=db_path)

    fake_parser = Mock()
    fake_parser.parse_args.return_value = args
    monkeypatch.setattr(main, "_build_parser", Mock(return_value=fake_parser))

    fake_create_database = Mock()
    monkeypatch.setattr(main, "create_database", fake_create_database)

    main.main()

    fake_create_database.assert_called_once_with(db_path=db_path)


@pytest.mark.parametrize("success", [True, False])
def test_main_load(monkeypatch, tmp_path, success):
    db_path = tmp_path / "test.db"
    args = Namespace(command="load", db_path=db_path)
    start_date = date(2026, 8, 1)
    end_date = date(2026, 8, 20)

    fake_parser = Mock()
    fake_parser.parse_args.return_value = args
    monkeypatch.setattr(main, "_build_parser", Mock(return_value=fake_parser))

    fake_resolve_load_request = Mock(return_value=(start_date, end_date, False, False))
    monkeypatch.setattr(main, "_resolve_load_request", fake_resolve_load_request)

    fake_get_db_connection = Mock()
    monkeypatch.setattr(main, "get_db_connection", fake_get_db_connection)

    fake_load_briefings = Mock(return_value=success)
    monkeypatch.setattr(main, "load_briefings_between_dates", fake_load_briefings)

    if success:
        main.main()
    else:
        with pytest.raises(SystemExit) as exc_info:
            main.main()
        assert exc_info.value.code == 1

    fake_resolve_load_request.assert_called_once()
    fake_get_db_connection.assert_called_once()
    fake_load_briefings.assert_called_once()


@pytest.mark.parametrize(
    "briefing_date,status",
    [
        (date(2026, 8, 20), None),
        (None, "available"),
    ],
)
def test_main_query(monkeypatch, tmp_path, briefing_date, status):
    fake_parser = Mock()
    fake_parser.parse_args.return_value = Namespace(
        command="query",
        db_path=tmp_path / "test.db",
        date=briefing_date,
        status=status,
    )
    monkeypatch.setattr(main, "_build_parser", Mock(return_value=fake_parser))
    monkeypatch.setattr(main, "get_db_connection", Mock())

    fake_query_by_date = Mock()
    fake_query_by_status = Mock()
    monkeypatch.setattr(main, "query_briefing_by_date", fake_query_by_date)
    monkeypatch.setattr(main, "query_briefing_by_status", fake_query_by_status)

    main.main()

    if briefing_date is not None:
        fake_query_by_date.assert_called_once()
        fake_query_by_status.assert_not_called()
    else:
        fake_query_by_status.assert_called_once()
        fake_query_by_date.assert_not_called()


def test_main_stats(monkeypatch, tmp_path):
    fake_parser = Mock()
    fake_parser.parse_args.return_value = Namespace(command="stats", db_path=tmp_path / "test.db")
    monkeypatch.setattr(main, "_build_parser", Mock(return_value=fake_parser))

    fake_get_db_connection = Mock()
    monkeypatch.setattr(main, "get_db_connection", fake_get_db_connection)

    fake_show_stats = Mock()
    monkeypatch.setattr(main, "show_stats", fake_show_stats)

    main.main()

    fake_get_db_connection.assert_called_once()
    fake_show_stats.assert_called_once()


def test_build_parser():
    """Test _build_parser creates parser with all subcommands."""
    parser = _build_parser()
    # assert parser.description == "Manage UN noon briefing database."
    assert (
        parser.description
        == "Download, check and (database) load and query UN noon briefing data."
    )

    # Test init-db command
    args = parser.parse_args(["init-db"])
    assert args.command == "init-db"

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
