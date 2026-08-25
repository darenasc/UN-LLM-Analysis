import argparse
from argparse import Namespace
from datetime import date, datetime, timedelta
import json
from unittest.mock import Mock

from playwright.sync_api import TimeoutError as PlaywrightTimeoutError
import pytest

import un_llm_analysis.scraper as scraper


def test_parse_date_valid():
    # GIVEN a valid date
    date_string = "2026-08-01"

    # WHEN _parse_date is called
    result = scraper._parse_date(date_string)

    # THEN the result should match the expected date
    assert result == date(2026, 8, 1)


def test_parse_date_invalid():
    # GIVEN an invalid date
    date_string = "2026-02-30"

    # WHEN _parse_date is called
    # THEN ArgumentTypeError is raised.
    with pytest.raises(argparse.ArgumentTypeError):
        scraper._parse_date(date_string)


def test_dates_between():
    # GIVEN a start date and an end date
    start_date = date(2026, 1, 30)
    end_date = date(2026, 2, 1)
    expected_dates = [date(2026, 1, 30), date(2026, 1, 31), date(2026, 2, 1)]

    # WHEN _dates_between is called
    result = list(scraper._dates_between(start_date, end_date))

    # THEN the result should match the expected dates
    assert result == expected_dates


@pytest.mark.parametrize(
    "status, expected",
    [
        ("available", True),
        ("not_published", True),
        ("failed", False),
        ("unknown", False),
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


@pytest.fixture
def fixed_today(monkeypatch):
    class FixedDateTime(datetime):
        @classmethod
        def now(cls, tz=None):
            return cls(2026, 8, 20, tzinfo=tz)

    monkeypatch.setattr(scraper, "datetime", FixedDateTime)

    return date(2026, 8, 20)


def test_resolve_update_request_since(fixed_today):
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

    expected_today = fixed_today

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


def test_resolve_update_request_date_after_today(fixed_today):
    parser = scraper._build_parser()

    tomorrow = fixed_today + timedelta(days=1)

    args = Namespace(
        dates=[tomorrow],
        since=None,
        overwrite=False,
    )

    with pytest.raises(SystemExit):
        scraper._resolve_update_request(parser, args)


def fake_scrape_brieing(page, briefing_date):
    return scraper.FetchResult(
        status="available",
        html="<p>Briefing</p>",
        http_status=200,
        error=None,
    )


def test_scrape_briefing_available():
    """Test successful scraping of an available briefing."""

    response = Mock(status=200, ok=True)
    html = "<p>Briefing</p>"

    page = Mock()
    page.goto.return_value = response
    page.locator.return_value.inner_html.return_value = html

    result = scraper.scrape_briefing(page, "2026-08-20")

    expected = scraper.FetchResult(
        status="available", html=html, http_status=response.status, error=None
    )

    page.goto.assert_called_once()
    page.locator.assert_called_once()
    assert result == expected


def make_mock_page(response, html):
    page = Mock()
    page.goto.return_value = response
    page.locator.return_value.inner_html.return_value = html

    return page


@pytest.mark.parametrize(
    "response, html, expected",
    [
        (
            Mock(status=200, ok=True),
            "<p>Briefing</p>",
            scraper.FetchResult(
                status="available", html="<p>Briefing</p>", http_status=200, error=None
            ),
        ),
        (
            Mock(status=200, ok=True),
            "",
            scraper.FetchResult(status="not_published", html=None, http_status=200, error=None),
        ),
        (
            None,
            None,
            scraper.FetchResult(
                status="failed", html=None, http_status=None, error="No response received."
            ),
        ),
        (
            Mock(status=404, ok=False),
            None,
            scraper.FetchResult(status="not_published", html=None, http_status=404, error=None),
        ),
        (
            Mock(status=403, ok=False),
            None,
            scraper.FetchResult(
                status="failed", html=None, http_status=403, error="Unexpected status code: 403"
            ),
        ),
    ],
    ids=[
        "available-200",
        "empty-html-200",
        "no-response",
        "not-published-404",
        "failed-403",
    ],
)
def test_scrape_briefing_by_basic_http_responses(response, html, expected):
    page = make_mock_page(response, html)

    result = scraper.scrape_briefing(page, "2026-08-20")

    page.goto.assert_called_once()

    if response is not None and response.status == 200:
        page.locator.assert_called_once()
        page.locator.return_value.inner_html.assert_called_once()
    else:
        page.locator.assert_not_called()

    assert result == expected


def test_scrape_briefing_status_202_retry_fails():
    page = make_mock_page(Mock(status=202, ok=True), None)

    result = scraper.scrape_briefing(page, "2026-08-20")

    expected = scraper.FetchResult(
        status="failed", html=None, http_status=202, error="Unexpected status code: 202"
    )

    assert page.goto.call_count == 3
    assert page.wait_for_timeout.call_count == 2
    page.locator.assert_not_called()

    assert result == expected


def test_scrape_briefing_status_202_retry_succeeds():
    html = "<p>Briefing</p>"

    response_202 = Mock(status=202, ok=True)
    response_200 = Mock(status=200, ok=True)

    page = make_mock_page(response_202, html)
    page.goto.side_effect = [response_202, response_200]

    result = scraper.scrape_briefing(page, "2026-08-20")

    expected = scraper.FetchResult(status="available", html=html, http_status=200, error=None)

    assert page.goto.call_count == 2
    page.wait_for_timeout.assert_called_once()
    page.locator.assert_called_once()
    page.locator.return_value.inner_html.assert_called_once()

    assert result == expected


def test_scrape_briefing_selector_wait_timeout(monkeypatch):
    page = make_mock_page(Mock(status=200, ok=True), None)

    error_message = "Target selector not found"

    page.locator.return_value.wait_for.side_effect = PlaywrightTimeoutError(error_message)

    # Skip the real retry delay
    monkeypatch.setattr(scraper.time, "sleep", lambda _seconds: None)

    result = scraper.scrape_briefing(page, "2026-08-20")

    expected = scraper.FetchResult(
        status="failed", html=None, http_status=None, error=error_message
    )

    assert page.goto.call_count == 2
    assert page.locator.call_count == 2
    assert page.locator.return_value.wait_for.call_count == 2
    assert page.locator.return_value.inner_html.call_count == 0

    assert result == expected
