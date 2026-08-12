from html import parser
import json
import time
from datetime import timedelta, datetime, date, timezone
import os
import argparse
from pathlib import Path
from playwright.sync_api import sync_playwright
from playwright.sync_api import Error as PlaywrightError
from scripts.constants import BASE_URL, START_DATE, END_DATE, RAW_BRIEFINGS_ROOT

# Basically UN Noon Briefing skips weekends and fixed official New York holidays, but still some exceptions, such as the following two dates:
# https://www.un.org/sg/en/content/highlight/2013-08-31.html (Saturday, but has briefing)
# https://www.un.org/sg/en/content/highlight/2013-09-01.html (Sunday, but has briefing)
#

def scrape_briefing(page_object, date_string, retries: int = 1):
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
            page_object.goto(
                page_url, 
                wait_until="domcontentloaded", 
                timeout=120_000
            )
            
            body = page_object.locator(".field--name-body")
            body.wait_for(state="visible", timeout=120_000)
            html = body.inner_html(timeout=120_000)
            
            return html.strip()
        
        except PlaywrightError as exc:
            if attempt < retries:
                print(f"  ✗ Error on attempt {attempt + 1}: {exc}. Retrying...")
                time.sleep(2)  # Wait a bit before retrying
            else:
                print(f"  ✗ Error on final attempt: {exc}. Giving up.")
                return None


def is_scraped(date_string):
    """Check if a briefing for the given date has already been scraped."""

    # Data paths follow this pattern: 
    #   "data/raw/briefings/YYYY/YYYY-MM/YYYY-MM-DD.json"

    BRIEFING_PATH = os.path.join(RAW_BRIEFINGS_ROOT, date_string[:4], date_string[:7], f"{date_string}.json")
    if not os.path.exists(BRIEFING_PATH):
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
            file_path = Path(f"{RAW_BRIEFINGS_ROOT}/{date_string[:4]}/{date_string[:7]}/{date_string}.json")

            if is_scraped(date_string) and not overwrite:
                print(f"  - Already scraped, skipping")
                continue

            try:
                page_result = scrape_briefing(page, date_string)
                file_path.parent.mkdir(parents=True, exist_ok=True)
                if page_result:
                    print(f"  ✓ Got briefing")
                else:                   
                    print(f"  - No briefing")
                    page_result = None

                downloaded_at = datetime.now(timezone.utc).isoformat(timespec="seconds")
                page_url = f"{BASE_URL}/{date_string}.html"
                json_content = {"date": date_string, "url": page_url, "html": page_result, "downloaded_at": downloaded_at}
                # Even no briefing exists for this date, we still save a JSON file with "html": null to indicate that we checked and found nothing.  
                with open(file_path, "w", encoding="utf-8") as f:
                    json.dump(json_content, f, ensure_ascii=False, indent=2)
            except Exception as e:
                print(f"  ✗ Error: {e}")

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
    parser = argparse.ArgumentParser(description="Scrape UN noon briefings.")
    subparsers = parser.add_subparsers(dest="command", required=True)

    # Subparser for the "update" command
    update_parser = subparsers.add_parser("update", help="Download briefings for a given date or range of dates.")
    update_parser.add_argument("date1", nargs="?", type=parse_date, metavar="DATE")
    update_parser.add_argument("date2", nargs="?", type=parse_date, metavar="DATE")
    update_parser.add_argument("--start", type=parse_date)
    update_parser.add_argument("--end", type=parse_date)
    update_parser.add_argument("--overwrite", action="store_true", help="Overwrite existing data instead of skipping.")

    # Subparser for the "check" command
    check_parser = subparsers.add_parser("check", help="Check existence of briefing data for a given date.")
    check_parser.add_argument("date", type=parse_date, metavar="DATE")

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
