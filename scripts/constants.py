from datetime import date, datetime
from zoneinfo import ZoneInfo

# SATURDAY = 5
# BACKUP_EVERY_X_ITERATIONS = 50

# BASE_URL = "https://www.un.org/sg/en/content/noon-briefing-highlight"
# The date filter is appended as a query parameter (?date=YYYY-MM-DD), but it seems no longer usable.

BASE_URL = "https://www.un.org/sg/en/content/highlight/"
# The date filter is appended as "YYYY-MM-DD.html" to the URL, e.g. "https://www.un.org/sg/en/content/highlight/2026-08-01.html"

START_DATE = date(2021, 1, 1)
# END_DATE is set to New York time, the UN site timezone.
END_DATE = datetime.now(ZoneInfo("America/New_York")).date()
RAW_BRIEFINGS_ROOT = "data/raw/briefings"
