import json
import time
from datetime import timedelta, datetime, date, timezone
from zoneinfo import ZoneInfo
import os
import argparse
from pathlib import Path
from playwright.sync_api import sync_playwright
from playwright.sync_api import Error as PlaywrightError

from dataclasses import dataclass
from typing import Literal

from un_llm_analysis.config import BASE_URL, BRIEFINGS_DIR

# Basically UN Noon Briefing skips weekends and fixed official New York holidays, but still some exceptions, such as the following two dates:
# https://www.un.org/sg/en/content/highlight/2013-08-31.html (Saturday, but has briefing)
# https://www.un.org/sg/en/content/highlight/2013-09-01.html (Sunday, but has briefing)

START_DATE = date(2021, 1, 1)
# END_DATE is set to New York time, the UN site timezone.
END_DATE = datetime.now(ZoneInfo("America/New_York")).date()

FetchStatus = Literal[
    "available",
    "not_published",
    "failed"
]

@dataclass(frozen=True)
class FetchResult:
    status: FetchStatus
    html: str | None
    http_status: int | None
    error: str | None = None

def scrape_briefing(
        page_object, 
        date_string: str, 
        retries: int = 1
) -> FetchResult:
    """
    Visit the briefing page for a given date and extract the (inner) html content.

    Parameters:
        page_object  - the Playwright browser page object (a single reusable tab)
        date_string  - date in "YYYY-MM-DD" format, e.g. "2023-01-05"
    """

    # page_url = f"{BASE_URL}?date={date_string}"
    page_url = f"{BASE_URL}/{date_string}.html"

    for attempt in range(retries + 1):
        try:
            response = page_object.goto(
                page_url, 
                wait_until="domcontentloaded", 
                timeout=120_000
            )

            if response is None:
                print(f"  ✗ No response received for {page_url}.")
                return FetchResult(status="failed", html=None, http_status=None, error="No response received.")

            status_code = response.status
            if status_code in {404, 410}:
                print(f"  - No briefing found for {date_string} (HTTP {status_code}).")
                return FetchResult(status="not_published", html=None, http_status=status_code, error=None)
            elif status_code != 200:
                print(f"  ✗ Unexpected status code for {date_string}: {status_code}")
                return FetchResult(status="failed", html=None, http_status=status_code, error=f"Unexpected status code: {status_code}")

            body = page_object.locator(".field--name-body")
            body.wait_for(state="visible", timeout=120_000)
            html = body.inner_html().strip()

            if not html:
                print(f"  - No briefing found for {date_string}.")
                return FetchResult(status="not_published", html=None, http_status=status_code, error=None)
            
            return FetchResult(status="available", html=html, http_status=status_code, error=None)
        
        except PlaywrightError as exc:
            if attempt < retries:
                print(f"  ✗ Error on attempt {attempt + 1}: {exc}. Retrying...")
                time.sleep(2)  # Wait a bit before retrying
            else:
                print(f"  ✗ Error on final attempt: {exc}. Giving up.")
                return FetchResult(status="failed", html=None, http_status=None, error=str(exc))


def is_scraped(date_string) -> bool:
    """Check if a briefing for the given date has already been scraped."""

    # Data paths follow this pattern: 
    #   "data/raw/briefings/YYYY/YYYY-MM/YYYY-MM-DD.json"

    BRIEFING_PATH = os.path.join(BRIEFINGS_DIR, date_string[:4], date_string[:7], f"{date_string}.json")
    if not os.path.exists(BRIEFING_PATH):
        return False

    try:
        with open(BRIEFING_PATH, "r", encoding="utf-8") as f:
            record = json.load(f)
            if record.get("status") not in {"available", "not_published"}:
                return False
    except (json.JSONDecodeError, IOError) as exc:
        print(f"  ✗ Error reading {BRIEFING_PATH}: {exc}")
        return False

    return True

def date_range(start_date, end_date):
    """
    Generate a list of dates between start_date and end_date.
    """

    current_date = start_date
    while current_date <= end_date:
        yield current_date
        current_date += timedelta(days=1)

def scrape_between_dates(start_date, end_date, overwrite=False):
    """
    Scrape UN noon briefings for all dates between start_date and end_date.
    """

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()

        dates = list(date_range(start_date, end_date))

        print(f"{len(dates)} dates to scrape ...")

        for i, date in enumerate(dates):
            date_string = date.strftime("%Y-%m-%d")
            print(f"[{i + 1}/{len(dates)}] {date_string}")
            file_path = Path(f"{BRIEFINGS_DIR}/{date_string[:4]}/{date_string[:7]}/{date_string}.json")

            if is_scraped(date_string) and not overwrite:
                print(f"  - Already scraped, skipping")
                continue

            try:
                page_result = scrape_briefing(page, date_string)
                file_path.parent.mkdir(parents=True, exist_ok=True)
                if page_result.status == "available":
                    print(f"  ✓ Got briefing")
                else:                   
                    print(f"  - No briefing")

                downloaded_at = datetime.now(timezone.utc).isoformat(timespec="seconds")
                page_url = f"{BASE_URL}/{date_string}.html"
                json_content = {
                    "date": date_string, 
                    "url": page_url, 
                    "status": page_result.status,
                    "http_status": page_result.http_status,
                    "html": page_result.html,
                    "error": page_result.error,
                    "downloaded_at": downloaded_at
                }
                # Even no briefing exists for this date, we still save a JSON file with "html": null to indicate that we checked and found nothing.  
                with open(file_path, "w", encoding="utf-8") as f:
                    json.dump(json_content, f, ensure_ascii=False, indent=2)
            except Exception as exc:
                print(f"  ✗ Error: {exc}")

            time.sleep(1)

        browser.close()

def parse_date(value: str) -> date:
    """
    Parse a string in YYYY-MM-DD format into a date object.
    Raises argparse.ArgumentTypeError if the format is invalid.
    """
    try:
        return date.fromisoformat(value)
    except ValueError as exc:
        raise argparse.ArgumentTypeError(
            f"Invalid date: {value}. Expected YYYY-MM-DD."
        ) from exc

def build_parser() -> argparse.ArgumentParser:
    """
    Build and return the argument parser for the script.
    """

    formatter = argparse.RawDescriptionHelpFormatter

    parser = argparse.ArgumentParser(
        description=(
            "Download and inspect UN noon briefing data."
        ), 
        epilog="""Examples:
  %(prog)s update 2026-08-12
  %(prog)s update 2026-08-01 2026-08-12
  %(prog)s check 2026-08-12

Run '%(prog)s COMMAND --help' for details about a command.
""", 
        formatter_class=formatter
    )

    subparsers = parser.add_subparsers(dest="command", required=True)


    update_parser = subparsers.add_parser(
        "update", 
        help="Download briefings for a given date or range of dates.", 
        description="""Download UN noon briefings and save them as JSON.

Use positional dates or --start/--end options, but do not mix
the two forms.
""", 
        epilog="""Accepted forms:
  %(prog)s DATE1
  %(prog)s DATE1 DATE2
  %(prog)s --start DATE
  %(prog)s --end DATE
  %(prog)s --start DATE --end DATE

DATE must use the YYYY-MM-DD format.
--overwrite may be added to any form.
""", 
        usage=(
            "%(prog)s [-h] [--overwrite] "
            "(DATE1 [DATE2] | "
            "--start DATE [--end DATE] | "
            "--end DATE)"
        ), 
        formatter_class=formatter
    )

    update_parser.add_argument(
        "date1", 
        nargs="?", 
        type=parse_date, 
        metavar="DATE1", 
        help=("Single date, or the first date of an inclusive range.")
    )
    update_parser.add_argument(
        "date2", 
        nargs="?", 
        type=parse_date, 
        metavar="DATE2", 
        help="Last date of the inclusive positional range."
    )
    update_parser.add_argument(
        "--start", 
        type=parse_date, 
        help=("First date of the range. If --end is omitted, the range ends today in New York.")
    )
    update_parser.add_argument(
        "--end", 
        type=parse_date, 
        help=f"Last date of the range. If --start is omitted, the range starts from {START_DATE}."
    )
    update_parser.add_argument(
        "--overwrite", 
        action="store_true", 
        help="Overwrite existing data instead of skipping."
    )


    check_parser = subparsers.add_parser(
        "check", 
        help="Check existence of stored briefing data for a given date.", 
        description=("Check if a briefing for a given date has already been downloaded and stored as JSON."), 
        epilog="""Example:
  %(prog)s 2026-08-12
""", 
        formatter_class=formatter
    )
    check_parser.add_argument(
        "date", 
        type=parse_date, 
        metavar="DATE", 
        help="Date to check in YYYY-MM-DD format."
    )

    return parser

def resolve_update_requests(parser: argparse.ArgumentParser, args: argparse.Namespace) -> tuple[date, date, bool]:
    """
    Determine the start and end dates for the update operation based on
    command-line arguments. Returns a tuple of (start_date, end_date, overwrite).
    """

    if args.date1 and (args.start or args.end):
        parser.error("Invalid combination of arguments: --start/--end cannot be used with positional dates.")

    if args.start:
        start_date = args.start
        if args.end:
            end_date = args.end
        else:
            end_date = END_DATE
    elif args.end:
        end_date = args.end
        start_date = START_DATE
    elif args.date1 and args.date2:
        start_date = args.date1
        end_date = args.date2
    elif args.date1:
        start_date = end_date = args.date1
    else:
        parser.error("No dates specified. Use positional dates or --start/--end options.")

    if start_date > end_date:
        parser.error(f"Start date {start_date} cannot be after end date {end_date}.")

    if start_date < START_DATE or end_date > END_DATE:
        parser.error(f"Dates must be between {START_DATE} and {END_DATE}.")

    overwrite = args.overwrite if hasattr(args, 'overwrite') else False
    
    return start_date, end_date, overwrite


def main() -> None:
    """
    Main entry point for the script. 
    """

    parser = build_parser()    
    args = parser.parse_args()

    if args.command == "check":
        date_string = args.date.strftime("%Y-%m-%d")
        if is_scraped(date_string):
            print(f"Briefing for {date_string} exists in the data directory.")
        else:
            print(f"Briefing for {date_string} does NOT exist in the data directory.")
        return

    if args.command == "update":
        start_date, end_date, overwrite = resolve_update_requests(parser, args)
        print(f"Updating briefings from {start_date} to {end_date}, overwrite={overwrite} ...")
        scrape_between_dates(start_date, end_date, overwrite=overwrite)
        print("Update complete.")

if __name__ == "__main__":
    main()
