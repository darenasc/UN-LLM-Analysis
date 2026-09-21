# About the project

The UN LLM Analysis project analyzes language patterns and themes in UN noon briefings using large language models (LLMs).

The aim is to identify trends and insights on global issues, policy developments, and emerging challenges.

# Requirements:

- [Python 3.12](https://www.python.org/downloads/release/python-31213/)
- [`pipenv`](https://pipenv.pypa.io/en/latest/)

# Set up the project

```bash
# Clone the repository and install dependencies
git clone https://github.com/darenasc/correlaid-mentoring-project.git
cd correlaid-mentoring-project
pipenv shell
pipenv install Pipfile
```

# Usage

## `scraper update`
Download UN noon briefings and save them as JSON.

```bash
# usage: scraper update [-h] [--overwrite] (DATE [DATE] | --since DATE)

# Update briefing for a single date
scraper update 2026-08-12

# Update briefings for a date range
scraper update 2026-08-01 2026-08-12

# Update briefings since a given date:
scraper update --since 2026-08-01
```

## `scraper check`
Check if a briefing for a given date has already been downloaded and stored as JSON.

```bash
# usage: scraper check [-h] DATE

scraper check 2026-08-12
```

Scraped raw data location:
  `data/raw/briefings/YYYY/YYYY-MM/YYYY-MM-DD.json`

## `extractor`

Extract structured content from a scraped briefing JSON file.

```python
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
