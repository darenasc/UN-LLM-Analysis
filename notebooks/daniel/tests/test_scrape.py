from datetime import date
from unittest.mock import MagicMock, call, patch

from playwright.sync_api import TimeoutError as PlaywrightTimeoutError
import pytest

from notebooks.daniel.constants import BASE_URL
import notebooks.daniel.scrape as scrape
from notebooks.daniel.scrape import daterange, scrape_all, scrape_briefing


@pytest.mark.parametrize(
    "start, end, expected",
    [
        # Normal case: full working week, Mon–Fri
        (
            date(2023, 1, 2),  # Monday
            date(2023, 1, 6),  # Friday
            [
                date(2023, 1, 2),
                date(2023, 1, 3),
                date(2023, 1, 4),
                date(2023, 1, 5),
                date(2023, 1, 6),
            ],
        ),
        # Start date on a Saturday
        (
            date(2023, 1, 7),  # Saturday
            date(2023, 1, 10),  # Tuesday
            [date(2023, 1, 9), date(2023, 1, 10)],
        ),
        # Start date on a Sunday
        (
            date(2023, 1, 8),  # Sunday
            date(2023, 1, 10),  # Tuesday
            [date(2023, 1, 9), date(2023, 1, 10)],
        ),
        # End date on a Saturday
        (
            date(2023, 1, 5),  # Thursday
            date(2023, 1, 7),  # Saturday
            [date(2023, 1, 5), date(2023, 1, 6)],
        ),
        # End date on a Sunday
        (
            date(2023, 1, 5),  # Thursday
            date(2023, 1, 8),  # Sunday
            [date(2023, 1, 5), date(2023, 1, 6)],
        ),
        # Single-day range, weekday
        (
            date(2023, 1, 3),  # Tuesday
            date(2023, 1, 3),
            [date(2023, 1, 3)],
        ),
        # Single-day range, weekend
        (
            date(2023, 1, 7),  # Saturday
            date(2023, 1, 7),
            [],
        ),
        # Invalid range: start after end
        (
            date(2023, 1, 10),
            date(2023, 1, 5),
            [],
        ),
        # Month boundary
        (
            date(2023, 1, 30),  # Monday
            date(2023, 2, 3),  # Friday
            [
                date(2023, 1, 30),
                date(2023, 1, 31),
                date(2023, 2, 1),
                date(2023, 2, 2),
                date(2023, 2, 3),
            ],
        ),
        # Leap year February boundary
        (
            date(2024, 2, 26),  # Monday
            date(2024, 3, 1),  # Friday
            [
                date(2024, 2, 26),
                date(2024, 2, 27),
                date(2024, 2, 28),
                date(2024, 2, 29),
                date(2024, 3, 1),
            ],
        ),
        # Year boundary (Dec 31 / Jan 1 fall on a weekend and are excluded)
        (
            date(2022, 12, 29),  # Thursday
            date(2023, 1, 3),  # Tuesday
            [date(2022, 12, 29), date(2022, 12, 30), date(2023, 1, 2), date(2023, 1, 3)],
        ),
    ],
    ids=[
        "full_weekday_range",
        "start_on_saturday",
        "start_on_sunday",
        "end_on_saturday",
        "end_on_sunday",
        "single_weekday",
        "single_weekend",
        "start_after_end",
        "month_boundary",
        "leap_year_boundary",
        "year_boundary",
    ],
)
def test_daterange(start, end, expected):
    """
    Using parameterized test:
    - yields all weekdays between two dates inclusive of both endpoints
    - excludes saturdays and sundays correctly (edge cases: start date is a Saturday/Sunday, and end date is a Saturday/Sunday)
    - returns nothing when start > end
    - handles single day range where start == end (weekday vs weekend)
    - correcly crosses a month/year boundary (e.g. Dec 30->Jan 2) and a leap-year february
    """
    result = list(daterange(start, end))
    assert result == expected


def test_scrape_briefing():
    """
    - need to pass a mock object
    - builds correct URL? and passes it to `goto`?
    - returns a dict with correct date, page_url and text stripped of whitesace when the selector is found?
    - reuturns None when wait_for_selector raises a TimeoutError?
    - turns None on any other exception raised inside the try block

    """
    mock_page = MagicMock()

    mock_page.inner_text.return_value = "  Briefing text here  "

    date_string = "2023-01-05"

    result = scrape_briefing(mock_page, date_string)

    assert result == {
        "date": "2023-01-05",
        "page_url": f"{BASE_URL}?date={date_string}",  # match your real BASE_URL
        "text": "Briefing text here",  # note: stripped of whitespace
    }


def make_playwright_mock():
    mock_p = MagicMock()
    mock_browser = MagicMock()
    mock_page = MagicMock()
    mock_p.chromium.launch.return_value = mock_browser
    mock_browser.new_page.return_value = mock_page
    return mock_p


@patch("notebooks.daniel.scrape.time.sleep")
@patch("builtins.open", new_callable=MagicMock)
@patch("notebooks.daniel.scrape.scrape_briefing")
@patch("notebooks.daniel.scrape.sync_playwright")
@patch("notebooks.daniel.scrape.load_existing_results")
@patch("notebooks.daniel.scrape.daterange")
def test_scrape_all_skips_already_scraped_dates(
    mock_daterange,
    mock_load_existing,
    mock_sync_playwright,
    mock_scrape_briefing,
    mock_open,
    mock_sleep,
):
    """
    - Given existing results with certain dates already scraped, confirms only scrapes NEW dates (tests scraped_dates filtering logic)
    - Confirms partial results are written to non_briefings_partial.json every BACKUP_EVERY_X_ITERATIONS (mock open/json.dump)
    - Confirms a scrap exception for one date does not stop the loop. Subsequent dates still get processed.
    - Confirms time.sleep is called between requests.
    NOTE: scrape_briefing's network behaviour requires Playwright's own testing tools or a live/staging fixture not pytest unit tests.

    """
    # Control the date range so the test is deterministic
    mock_daterange.return_value = [date(2023, 1, 2), date(2023, 1, 3), date(2023, 1, 4)]

    # Pretend Jan 2 is already scraped
    mock_load_existing.return_value = [{"date": "2023-01-02", "page_url": "x", "text": "old"}]

    # Playwright setup
    mock_sync_playwright.return_value.__enter__.return_value = make_playwright_mock()

    # scrape_briefing returns something for every date it's called with
    mock_scrape_briefing.return_value = {"date": "new", "page_url": "x", "text": "new"}

    scrape.scrape_all()

    # scrape_briefing should only be called for Jan 3 and Jan 4, not Jan 2
    called_dates = [c.args[1] for c in mock_scrape_briefing.call_args_list]
    assert called_dates == ["2023-01-03", "2023-01-04"]


# TODO need to mock scrape_briefing() - already tested separately, just want to control what it returns per call
# TODO load_existing_results() - control what "already scraped" data looks like
# TODO open()/json.dump() - avoid writing real files to disk
# TODO time.sleep() - avoid the test taking 1 second per test
