# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/), and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## Unreleased

### Added

- #52 Sentiment & tone over time
- #50 Proportionality of issues/topics
- #47 Country mention heatmap

## [1.0.0]
- Sentiment distribution  visualisation to show the number of sections classified as positive, neutral, or negative.
- Tone distribution visualisation to show the frequency of different communication tones in UN briefings.
- Sentiment and tone relationship visualisation to explore how sentiment categories relate to communication tones..
- The sentiment graph shows whether positive, neutral, or negative classifications increase or decrease over time.
- The tone graph shows how the frequency of communication tones changes each month.
- A value of zero means no successful classifications for that category were recorded in that month.
### Features

- Initial release of `un_llm_analysis`
- UN noon briefing scraper and CLI for downloading briefing data.
- Content extractor for structured briefing data, including speakers and sections.
- SQLite database interface and CLI for database initialization, loading, and querying.
- Streamlit app for visualising project data and LLM analysis.
- SDG analysis of briefing sections using the 17 UN Sustainable Development Goals.
- Project documentation using MkDocs.
- CHANGELOG.md file with notable changes of the project

### Dependencies/Updates

- Python 3.12 as the base language.
- Pipenv for dependency management.
- Pre-commit hooks for code quality.
