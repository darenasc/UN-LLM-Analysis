import json
import time
from datetime import timedelta
import os
from playwright.sync_api import sync_playwright
from notebooks.constants import SATURDAY, BACKUP_EVERY_X_ITERATIONS, BASE_URL, START_DATE, END_DATE


# --- Configuration ---
# Base URL for the UN Secretary-General noon briefing page.
# The date filter is appended as a query parameter (?date=YYYY-MM-DD).

# The earliest date we want to scrape. Briefings before this date are
# either unavailable or outside our research scope.

# We scrape up to and including today. date.today() is called once at
# startup so the end date stays consistent throughout the run.


def daterange(START_DATE, END_DATE):
    """
    A generator that yields every calendar date from start to end (inclusive),
    excluding weekends because no briefings are held on Saturdays and Sundays.

    We use a generator rather than building a full list upfront because it is
    more memory-efficient — it produces one date at a time instead of holding
    all ~850 dates in memory simultaneously.

    timedelta(days=1) steps forward exactly one day at a time, handling
    month boundaries and leap years automatically.
    """
    current_date = START_DATE
    while current_date <= END_DATE:
        # weekday() returns 0-6 where 0=Monday, 5=Saturday, 6=Sunday
        if current_date.weekday() < SATURDAY:
            yield current_date
        current_date += timedelta(days=1)


def scrape_briefing(page_object, date_string):
    """
    Visit the briefing page for a given date and extract the text content.

    Parameters:
        page      - the Playwright browser page object (a single reusable tab)
        date_string  - date in "YYYY-MM-DD" format, e.g. "2023-01-05"

    Returns a dict with date, url, and text if a briefing exists,
    or None if the page shows no content for that date.
    """

    # Build the full URL by appending the date as a query parameter.
    # The UN website uses this parameter to filter which briefing is displayed.
    page_url = f"{BASE_URL}?date={date_string}"

    # Navigate to the page. wait_until="domcontentloaded" fires as soon as the
    # initial HTML is parsed, without waiting for all network activity to settle.
    # This is faster than "networkidle" because the UN site makes many background
    # requests we don't care about.
    try:
        page_object.goto(page_url, wait_until="domcontentloaded")

        # After the HTML loads, the briefing text is still being injected by
        # JavaScript. wait_for_selector blocks until the content container
        # appears in the DOM, or raises a TimeoutError after 3000ms if it never
        # does. This replaces the slower networkidle approach while still
        # ensuring the content is present before we try to read it.
        # If there is no briefing for this date (holiday, etc.), the selector
        # will time out and the except block will return None.
        page_object.wait_for_selector(".views-element-container", timeout=3000)

        # Extract all visible text from the main content container.
        # ".views-element-container" is the CSS class wrapping the briefing body
        # on this site. We target this specific element rather than the whole page
        # to avoid capturing navigation menus, headers, footers, and other noise.
        text = page_object.inner_text(".views-element-container")

    except:
        # Catches both TimeoutError (no content for this date) and any other
        # unexpected errors (network issues, page structure changes, etc.).
        # Returning None signals to the caller that nothing was found.
        return None

    # Return a structured record. Storing the URL alongside the text makes it
    # easy to trace any record back to its source for verification later.
    return {"date": date_string, "page_url": page_url, "text": text.strip()}

def load_existing_results(path="noon_briefings.json"):
    """Load previously scraped results, if any, so we can skip re-scraping them."""
    if os.path.exists(path):
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    return []


def scrape_all():
    existing_results = load_existing_results()
    scraped_dates = {r["date"] for r in existing_results}

    results = list(existing_results)  # keep what we already have

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()

        all_dates = list(daterange(START_DATE, END_DATE))
        # Only scrape dates we haven't already got
        dates = [d for d in all_dates if d.strftime("%Y-%m-%d") not in scraped_dates]

        print(f"{len(all_dates)} dates in range, {len(dates)} new dates to scrape...")

        for i, date in enumerate(dates):
            date_string = date.strftime("%Y-%m-%d")
            print(f"[{i + 1}/{len(dates)}] {date_string}")

            try:
                result = scrape_briefing(page, date_string)
                if result:
                    results.append(result)
                    print(f"  ✓ Got briefing")
                else:
                    print(f"  - No briefing")
            except Exception as e:
                print(f"  ✗ Error: {e}")

            if i % BACKUP_EVERY_X_ITERATIONS == 0 and results:
                with open("noon_briefings_partial.json", "w", encoding="utf-8") as f:
                    json.dump(results, f, ensure_ascii=False, indent=2)

            time.sleep(1)

        browser.close()

    return results

# This guard ensures the scraping only runs when the script is executed
# directly (e.g. `python scrape.py`), not when it is imported as a module
# by another script. This is a standard Python best practice.
if __name__ == "__main__":
    results = scrape_all()

    # Write the final complete dataset to a JSON file.
    # indent=2 makes the file human-readable (one key per line, indented).
    with open("noon_briefings.json", "w", encoding="utf-8") as f:
        json.dump(results, f, ensure_ascii=False, indent=2)

    print(f"\nDone. Saved {len(results)} briefings.")