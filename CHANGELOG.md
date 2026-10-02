# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/), and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [1.0.0]

### Features

- Initial release of `un_llm_analysis`
- UN noon briefing scraper and CLI for downloading briefing data.
- Content extractor for structured briefing data, including speakers and sections.
- SQLite database interface and CLI for database initialization, loading, and querying.
- Streamlit app for visualising project data and LLM analysis.
- SDG analysis of briefing sections using the 17 UN Sustainable Development Goals.
- Project documentation using MkDocs.

### To be added

- #52 Sentiment & tone over time
- #50 Proportionality of issues/topics
- #47 Country mention heatmap
- #40 List of Data Analysis Ideas

### Dependencies/Updates

- Python 3.12 as the base language.
- Pipenv for dependency management.
- Pre-commit hooks for code quality.
