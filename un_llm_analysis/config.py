from datetime import date
from pathlib import Path

BASE_URL = "https://www.un.org/sg/en/content/highlight"
MIN_SCRAPE_DATE = date(2004, 4, 5)

PROJ_ROOT = Path(__file__).resolve().parents[1]

DATA_DIR = PROJ_ROOT / "data"
RAW_DATA_DIR = DATA_DIR / "raw"
BRIEFINGS_DIR = RAW_DATA_DIR / "briefings"
INTERIM_DATA_DIR = DATA_DIR / "interim"
PROCESSED_DATA_DIR = DATA_DIR / "processed"
EXTERNAL_DATA_DIR = DATA_DIR / "external"

MODELS_DIR = PROJ_ROOT / "models"

REPORTS_DIR = PROJ_ROOT / "reports"
FIGURES_DIR = REPORTS_DIR / "figures"

DATA_DIR.mkdir(parents=True, exist_ok=True)
RAW_DATA_DIR.mkdir(parents=True, exist_ok=True)
BRIEFINGS_DIR.mkdir(parents=True, exist_ok=True)
INTERIM_DATA_DIR.mkdir(parents=True, exist_ok=True)
PROCESSED_DATA_DIR.mkdir(parents=True, exist_ok=True)
EXTERNAL_DATA_DIR.mkdir(parents=True, exist_ok=True)
MODELS_DIR.mkdir(parents=True, exist_ok=True)
REPORTS_DIR.mkdir(parents=True, exist_ok=True)
FIGURES_DIR.mkdir(parents=True, exist_ok=True)

SCHEMA_DB = PROJ_ROOT / "database" / "schema.sql"
BRIEFINGS_DB = PROJ_ROOT / "app" / "briefings.db"


def get_country_data():
    """Fetch country data from Wikipedia.

    Returns:
        list[tuple]: List of tuples containing (code, name, alternative_names).
    """
    import curl_cffi
    from bs4 import BeautifulSoup

    url = "https://en.wikipedia.org/wiki/List_of_alternative_country_names"
    response = curl_cffi.get(url, impersonate="chrome")
    soup = BeautifulSoup(response.text, "html.parser")
    tables = soup.find_all(class_="wikitable")

    data = []
    for table in tables:
        for row in table.find_all("tr")[1:]:  # ignores the column names row
            cell_data = row.find_all("td")
            if len(cell_data) == 3:  # only process when there are 3 columns
                code, name, names = cell_data
                country_name = name.find("a")["title"].strip()
                other_names = "|".join(
                    [x.text.strip() for x in names.find_all("b")]
                    + [x.text.strip() for x in names.find_all("i")]
                )
                data.append((code.text, country_name, other_names))

    return data
