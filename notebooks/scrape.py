import json
import time
from datetime import date, timedelta

from playwright.sync_api import sync_playwright

# --- Configuration ---
# Base URL for the UN Secretary-General noon briefing page.
# The date filter is appended as a query parameter (?date=YYYY-MM-DD).
BASE_URL = "https://www.un.org/sg/en/content/noon-briefing-highlight"

# The earliest date we want to scrape. Briefings before this date are
# either unavailable or outside our research scope.
START_DATE = date(2021, 1, 1)

# We scrape up to and including today. date.today() is called once at
# startup so the end date stays consistent throughout the run.
END_DATE = date.today()


def daterange(start, end):
    """
    A generator that yields every calendar date from start to end (inclusive),
    excluding weekends because no briefings are held on Saturdays and Sundays.

    We use a generator rather than building a full list upfront because it is
    more memory-efficient — it produces one date at a time instead of holding
    all ~850 dates in memory simultaneously.

    timedelta(days=1) steps forward exactly one day at a time, handling
    month boundaries and leap years automatically.
    """
    current = start
    while current <= end:
        # weekday() returns 0-6 where 0=Monday, 5=Saturday, 6=Sunday
        if current.weekday() < 5:
            yield current
        current += timedelta(days=1)


def scrape_briefing(page, date_str):
    """
    Visit the briefing page for a given date and extract the text content.

    Parameters:
        page      - the Playwright browser page object (a single reusable tab)
        date_str  - date in "YYYY-MM-DD" format, e.g. "2023-01-05"

    Returns a dict with date, url, and text if a briefing exists,
    or None if the page shows no content for that date.
    """

    # Build the full URL by appending the date as a query parameter.
    # The UN website uses this parameter to filter which briefing is displayed.
    url = f"{BASE_URL}?date={date_str}"

    # Navigate to the page. wait_until="domcontentloaded" fires as soon as the
    # initial HTML is parsed, without waiting for all network activity to settle.
    # This is faster than "networkidle" because the UN site makes many background
    # requests we don't care about.
    try:
        page.goto(url, wait_until="domcontentloaded")

        # After the HTML loads, the briefing text is still being injected by
        # JavaScript. wait_for_selector blocks until the content container
        # appears in the DOM, or raises a TimeoutError after 3000ms if it never
        # does. This replaces the slower networkidle approach while still
        # ensuring the content is present before we try to read it.
        # If there is no briefing for this date (holiday, etc.), the selector
        # will time out and the except block will return None.
        page.wait_for_selector(".views-element-container", timeout=3000)

        # Extract all visible text from the main content container.
        # ".views-element-container" is the CSS class wrapping the briefing body
        # on this site. We target this specific element rather than the whole page
        # to avoid capturing navigation menus, headers, footers, and other noise.
        text = page.inner_text(".views-element-container")

    except:
        # Catches both TimeoutError (no content for this date) and any other
        # unexpected errors (network issues, page structure changes, etc.).
        # Returning None signals to the caller that nothing was found.
        return None

    # Return a structured record. Storing the URL alongside the text makes it
    # easy to trace any record back to its source for verification later.
    return {"date": date_str, "url": url, "text": text.strip()}


def scrape_all():
    """
    Main scraping loop. Iterates over every date in the range, scrapes each
    briefing, and returns a list of result dicts.
    """
    results = []

    # sync_playwright() is a context manager that starts the Playwright engine
    # and ensures it is properly shut down when the block exits, even if an
    # error occurs. We use the sync (synchronous) API rather than the async API
    # because Jupyter notebooks run their own async event loop which conflicts
    # with Playwright's async implementation. Running as a plain Python script
    # avoids this problem entirely.
    with sync_playwright() as p:

        # Launch a headless Chromium browser. headless=True means the browser
        # runs in the background with no visible window, which is faster and
        # suitable for automated scraping. Set headless=False if you want to
        # watch the browser navigate pages (useful for debugging).
        browser = p.chromium.launch(headless=True)

        # Open a single browser tab (page) and reuse it for every request.
        # This is more efficient than opening and closing a new tab per URL,
        # as it avoids the overhead of repeatedly initialising a new context.
        page = browser.new_page()

        # Convert the generator to a list so we know the total count upfront
        # and can display progress as "[current/total]" in the logs.
        dates = list(daterange(START_DATE, END_DATE))
        print(f"Scraping {len(dates)} dates...")

        for i, d in enumerate(dates):
            # Format the date as a string in YYYY-MM-DD format, which is what
            # the UN website expects as a query parameter.
            date_str = d.strftime("%Y-%m-%d")
            print(f"[{i + 1}/{len(dates)}] {date_str}")

            try:
                result = scrape_briefing(page, date_str)
                if result:
                    results.append(result)
                    print(f"  ✓ Got briefing")
                else:
                    # None means the page existed but had no briefing content
                    # (weekend, holiday, etc.). This is expected and not an error.
                    print(f"  - No briefing")
            except Exception as e:
                # Catch any unexpected errors (network timeout, site changes,
                # etc.) and log them without stopping the whole scrape.
                print(f"  ✗ Error: {e}")

            # Save a partial backup file every 50 iterations. If the script
            # crashes or is interrupted after several hundred pages, this means
            # we don't lose all our progress — we can inspect the partial file
            # and resume from where we left off.
            if i % 50 == 0 and results:
                with open("noon_briefings_partial.json", "w", encoding="utf-8") as f:
                    # ensure_ascii=False preserves non-Latin characters
                    # (e.g. accented names like Guterres) in their original
                    # form rather than escaping them as \uXXXX sequences.
                    json.dump(results, f, ensure_ascii=False, indent=2)

            # Pause for 1 second between requests. This is good practice when
            # scraping: it reduces the load on the server and makes our traffic
            # look more like a human browsing, reducing the chance of being
            # blocked by the site's bot detection.
            time.sleep(1)

        # Explicitly close the browser to release memory and system resources.
        # This also happens automatically when the `with` block exits, but
        # calling it explicitly makes the intent clear.
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