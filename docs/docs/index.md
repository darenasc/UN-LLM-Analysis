# About the project

UN LLM Analysis is a CorrelAid mentoring project that explores data analysis and
natural language processing techniques using United Nations noon briefing data.

The project was developed collaboratively through the CorrelAid mentoring
programme. It includes tools for scraping, extracting, storing, and analysing
UN noon briefing data.

# Requirements:

- [Python 3.12](https://www.python.org/downloads/release/python-31213/)
- [`uv`](https://docs.astral.sh/uv/#installation)

# Set up the project

```bash
# Clone the repository and install dependencies
git clone https://github.com/darenasc/correlaid-mentoring-project.git
cd correlaid-mentoring-project

# Create the virtual environment and install dependencies
uv sync
```

# Usage

## CLI scraper update

Download UN noon briefings and save them as JSON.

```bash
# usage: briefings update [-h] [--overwrite] (DATE [DATE] | --since DATE)

# Update briefing for a single date
briefings update 2026-08-12

# Update briefings for a date range
briefings update 2026-08-01 2026-08-12

# Update briefings since a given date:
briefings update --since 2026-08-01
```

## CLI scraper check

Check if a briefing for a given date has already been downloaded and stored as JSON.

```bash
# usage: briefings check [-h] DATE

briefings check 2026-08-12
```

Scraped raw data location:
  `data/raw/briefings/YYYY/YYYY-MM/YYYY-MM-DD.json`

## CLI database

Command line interface to initialise, load and query the database.

```bash
briefings init-db
briefings load 2026-08-12 2026-08-12
briefings load --since 2026-08-12 --dry-run
briefings query --date 2026-08-12
briefings query --status available
briefings stats
```

## `extractor` module

Extract structured content from a scraped briefing JSON file.

```py
from pathlib import Path

from un_llm_analysis.config import RAW_DATA_DIR
from un_llm_analysis.extractor import extract_briefing

briefing = extract_briefing(RAW_DATA_DIR / "briefings" / "2026" / "2026-08" / "2026-08-12.json")
```

The extracted result includes speaker information, sections, and full text when available.

## `streamlit app`

This project adds a streamlit app to visualise some of the data and analysis.
Run the following command from the terminal to launch it.

```bash
# Start a streamlit app

streamlit run app/Dashboard.py
```

The app will be running locally in http://localhost:8501

# Project resources

The project includes tools and documentation for collecting and analyzing UN noon briefing data.
