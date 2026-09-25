import argparse
from collections.abc import Iterator
from contextlib import closing
from dataclasses import dataclass
from datetime import date, datetime, timedelta, timezone
import json
import os
from pathlib import Path
import time
from typing import Literal
from zoneinfo import ZoneInfo

from playwright.sync_api import Error as PlaywrightError
from playwright.sync_api import Page, sync_playwright

from un_llm_analysis.config import BASE_URL, BRIEFINGS_DIR, MIN_SCRAPE_DATE
from un_llm_analysis.utils import _dates_between

FetchStatus = Literal["available", "not_published", "failed"]


@dataclass(frozen=True)
class FetchResult:
    """Result from scraping a briefing of a given date."""

    status: FetchStatus
    html: str | None
    http_status: int | None
    error: str | None = None


def scrape_briefing(page: Page, date_string: str, retries: int = 1) -> FetchResult:
    """Visit the briefing page for a given date and extract the (inner) html content.

    Args:
        page (Page): the Playwright browser page object (a single reusable tab)
        date_string (str): Date in "YYYY-MM-DD" format, e.g. "2023-01-05"
        retries (int, optional): Number of retries to download briefing. Defaults to 1.

    Returns:
        FetchResult: Result from scraping the briefing of a given date.
    """

    page_url = f"{BASE_URL}/{date_string}.html"

    for attempt in range(retries + 1):
        try:
            response = page.goto(page_url, wait_until="domcontentloaded", timeout=120_000)

            if response is None:
                print(f"  ✗ No response received for {page_url}.")
                return FetchResult(
                    status="failed", html=None, http_status=None, error="No response received."
                )

            status_code = response.status

            # Allow successful non-200 responses time to resolve, mainly for the WAF challenge.
            for _ in range(2):
                if response.ok and (status_code != 200):  # type: ignore
                    page.wait_for_timeout(3_000)

                    response = page.goto(page_url, wait_until="domcontentloaded", timeout=120_000)
                    status_code = response.status  # type: ignore
                else:
                    break

            if status_code in {404, 410}:
                print(f"  - No briefing available for {date_string} (HTTP {status_code}).")
                return FetchResult(
                    status="not_published", html=None, http_status=status_code, error=None
                )
            elif status_code != 200:
                print(f"  ✗ Unexpected status code for {date_string}: {status_code}")
                return FetchResult(
                    status="failed",
                    html=None,
                    http_status=status_code,
                    error=f"Unexpected status code: {status_code}",
                )

            body = page.locator(".field--name-body")
            body.wait_for(state="visible", timeout=120_000)
            html = body.inner_html()

            if not html:
                print(f"  - No briefing available for {date_string}.")
                return FetchResult(
                    status="not_published", html=None, http_status=status_code, error=None
                )

            return FetchResult(
                status="available", html=html.strip(), http_status=status_code, error=None
            )

        except PlaywrightError as exc:
            if attempt < retries:
                print(f"  ✗ Error on attempt {attempt + 1}: {exc}. Retrying...")
                time.sleep(2)
            else:
                print(f"  ✗ Error on final attempt: {exc}. Giving up.")
                return FetchResult(status="failed", html=None, http_status=None, error=str(exc))

    raise RuntimeError("Unexpected end of scrape_briefing")  # pragma: no cover


def _is_briefing_scraped(briefing_date: date) -> bool:
    """Check if a briefing for the given date has already been scraped.

    Args:
        briefing_date (date): Date of the briefing to be scraped.

    Returns:
        bool: Check whether or not the briefing has been already been scraped
            or not.
    """

    # Data paths pattern: PROJ_ROOT/data/raw/briefings/YYYY/YYYY-MM/YYYY-MM-DD.json

    date_string = briefing_date.strftime("%Y-%m-%d")

    briefing_path = os.path.join(
        BRIEFINGS_DIR, date_string[:4], date_string[:7], f"{date_string}.json"
    )

    if not os.path.exists(briefing_path):
        return False

    try:
        with open(briefing_path, "r", encoding="utf-8") as f:
            record = json.load(f)
            if record.get("status") not in {"available", "not_published"}:
                return False
    except (json.JSONDecodeError, IOError) as exc:
        print(f"  ✗ Error reading {briefing_path}: {exc}")
        return False

    return True


def scrape_between_dates(start_date: date, end_date: date, overwrite: bool = False) -> None:
    """Scrape UN noon briefings for all dates between start_date and end_date

    Args:
        start_date (date): The date to start the sequence from..
        end_date (date): The date to end the sequence at.
        overwrite (bool, optional): Whether or not to overwrite an already
            downloaded briefing. Defaults to False.
    """

    requested_dates = list(_dates_between(start_date, end_date))
    dates_to_fetch = {
        briefing_date
        for briefing_date in requested_dates
        if overwrite or not _is_briefing_scraped(briefing_date)
    }

    skipped_count = len(requested_dates) - len(dates_to_fetch)

    print(
        f"{len(requested_dates)} dates requested. "
        f"{len(dates_to_fetch)} to fetch, {skipped_count} to skip."
    )

    if not dates_to_fetch:
        print("All requested briefings already exist.")
        return

    with sync_playwright() as p, closing(p.chromium.launch(headless=True)) as browser:

        page = browser.new_page()

        for i, _date in enumerate(requested_dates):
            date_string = _date.strftime("%Y-%m-%d")
            print(f"[{i + 1}/{len(requested_dates)}] {date_string}")
            file_path = Path(
                f"{BRIEFINGS_DIR}/{date_string[:4]}/{date_string[:7]}/{date_string}.json"
            )

            if _date not in dates_to_fetch:
                print("  - Already scraped, skipping")
                continue

            try:
                page_result = scrape_briefing(page, date_string)
                file_path.parent.mkdir(parents=True, exist_ok=True)
                if page_result.status == "available":
                    print("  ✓ Got briefing")
                else:
                    print("  - No briefing")

                downloaded_at = datetime.now(timezone.utc).isoformat(timespec="seconds")
                page_url = f"{BASE_URL}/{date_string}.html"
                json_content = {
                    "date": date_string,
                    "url": page_url,
                    "status": page_result.status,
                    "http_status": page_result.http_status,
                    "html": page_result.html,
                    "error": page_result.error,
                    "downloaded_at": downloaded_at,
                }
                # Record checked dates even when no briefing is available.
                with open(file_path, "w", encoding="utf-8") as f:
                    json.dump(json_content, f, ensure_ascii=False, indent=2)
            except Exception as exc:
                print(f"  ✗ Error: {exc}")

            time.sleep(1)


def _parse_date(value: str) -> date:
    """Parse a string in YYYY-MM-DD format into a date object.

    Args:
        value (str): Date in str type. YYYY-MM-DD format is expected.

    Raises:
        argparse.ArgumentTypeError: Exception for type.

    Returns:
        date: date type returned from str.
    """
    try:
        return date.fromisoformat(value)
    except ValueError as exc:
        raise argparse.ArgumentTypeError(f"Invalid date: {value}. Expected YYYY-MM-DD.") from exc


# def _build_parser() -> argparse.ArgumentParser:
#     """Build and return the argument parser for the script."""

#     formatter = argparse.RawDescriptionHelpFormatter

#     parser = argparse.ArgumentParser(
#         description="Download and check UN noon briefing data.",
#         epilog="""Examples:
#   %(prog)s update 2026-08-12
#   %(prog)s update 2026-08-01 2026-08-12
#   %(prog)s update --since 2026-08-01
#   %(prog)s check 2026-08-12

# Run '%(prog)s COMMAND --help' for details about a command.
# """,
#         formatter_class=formatter,
#     )

#     subparsers = parser.add_subparsers(dest="command", required=True)

#     update_parser = subparsers.add_parser(
#         "update",
#         help="Download briefings for a given date or range of dates.",
#         description="""Download UN noon briefings and save them as JSON.

# Use positional dates or the --since option, but do not combine them.
# """,
#         epilog="""Examples:
#   %(prog)s 2026-08-12
#   %(prog)s 2026-08-01 2026-08-12
#   %(prog)s --since 2026-08-01

# --overwrite may be added to any form.

# Scraped raw data location:
#   PROJ_ROOT/data/raw/briefings/YYYY/YYYY-MM/YYYY-MM-DD.json
# """,
#         usage=("%(prog)s [-h] [--overwrite] " "(DATE [DATE] | " "--since DATE)"),
#         formatter_class=formatter,
#     )

#     update_parser.add_argument(
#         "dates",
#         nargs="*",
#         type=_parse_date,
#         metavar="DATE",
#         help=(
#             "One date to update, or two dates defining an inclusive range. " "Format: YYYY-MM-DD."
#         ),
#     )
#     update_parser.add_argument(
#         "--since",
#         type=_parse_date,
#         help=("Update from the given date through today, inclusive. " "Format: YYYY-MM-DD."),
#     )
#     update_parser.add_argument(
#         "--overwrite",
#         action="store_true",
#         help="Re-download and overwrite existing data instead of skipping it.",
#     )

#     check_parser = subparsers.add_parser(
#         "check",
#         help="Check existence of stored briefing data for a given date.",
#         description=(
#             "Check if a briefing for a given date has already been downloaded and stored as JSON."
#         ),
#         epilog="""Example:
#   %(prog)s 2026-08-12

# Scraped raw data location:
#   PROJ_ROOT/data/raw/briefings/YYYY/YYYY-MM/YYYY-MM-DD.json
# """,
#         formatter_class=formatter,
#     )
#     check_parser.add_argument(
#         "date", type=_parse_date, metavar="DATE", help="Date to check in YYYY-MM-DD format."
#     )

#     return parser


# def _resolve_update_request(
#     parser: argparse.ArgumentParser, args: argparse.Namespace
# ) -> tuple[date, date, bool]:
#     """Resolve update arguments into a tuple of (start_date, end_date,
#         overwrite).

#     Args:
#         parser (argparse.ArgumentParser): Parser object.
#         args (argparse.Namespace): Arguments passed.

#     Returns:
#         tuple[date, date, bool]: Arguments for start_date, end_date and
#             overwrite.
#     """

#     today = datetime.now(ZoneInfo("America/New_York")).date()

#     if args.dates and args.since is not None:
#         parser.error("--since cannot be used with positional dates.")

#     if args.dates:
#         if len(args.dates) > 2:
#             parser.error("At most two positional dates may be provided.")
#         elif len(args.dates) == 1:
#             start_date = end_date = args.dates[0]
#         else:  # len(args.dates) must be 2
#             start_date, end_date = args.dates
#     elif args.since is not None:
#         start_date = args.since
#         end_date = today
#     else:
#         parser.error(
#             "No dates specified. Provide one or two positional dates, or use --since DATE."
#         )

#     if start_date > end_date:
#         parser.error(f"Start date {start_date} cannot be after end date {end_date}.")

#     if start_date < MIN_SCRAPE_DATE or end_date > today:
#         parser.error(f"Dates must be between {MIN_SCRAPE_DATE} and {today}.")

#     overwrite = args.overwrite

#     return start_date, end_date, overwrite


# def main() -> None:
#     """Main entry point for the script."""

#     parser = _build_parser()
#     args = parser.parse_args()

#     if args.command == "check":
#         date_string = args.date.strftime("%Y-%m-%d")
#         if _is_briefing_scraped(args.date):
#             print(f"Briefing for {date_string} exists in the data directory.")
#         else:
#             print(f"Briefing for {date_string} does NOT exist in the data directory.")

#     elif args.command == "update":  # pragma: no branch
#         start_date, end_date, overwrite = _resolve_update_request(parser, args)
#         print(f"Updating briefings from {start_date} to {end_date}, overwrite={overwrite} ...")
#         scrape_between_dates(start_date, end_date, overwrite=overwrite)
#         print("Update complete.")


# if __name__ == "__main__":  # pragma: no cover
#     main()
