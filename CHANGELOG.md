# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/), and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## Unreleased

### Added


- #50 Proportionality of issues/topics

## [2.0.2]

### Added

- Notebook with heatmap and map visualising country mentions in the briefings
- Map visualisation in the Dashboard page of the Streamlit app
- New Country mentions page in the Streamlit app
- New `country` table to the database schema
- `run_model_prompt` function to the `prompts.py` module
- Country Wikipedia dataset with codes and unique names
- Country vector data to them using maps
- Country flag icons to the briefing reader page

### Removed

- `get_sdg_models` replaced by `get_models`
- `get_min_max_dates_with_sdg` replaced by `get_min_max_dates_with_table`

## [2.0.1]

### Added

- New function `get_sections_between_dates`

## [2.0.0]

### Added

- Introduce `Section` and `Briefing` dataclasses extending `ExtractedSection` and `ExtractedBriefing` to expose all database fields, including IDs.
- Add generalized `get_min_max_dates_with_table` and `get_models` functions, retaining the previous table-specific functions as wrappers.

### Changed

- **Breaking:** Require an explicit database connection for functions accepting `conn`.
- **Breaking:** Rename `query_by_date` to `query_briefing_by_date`, `query_by_status` to `query_briefing_by_status`, and `get_section_by_section_id` to `get_section_by_id`.
- Limit transaction management to `create_database`, `load_briefing_to_db`, `insert_into_sdg`, and `insert_into_issue`.
- Simplify database queries by replacing most explicit cursor calls with `conn.execute()`.

### Removed

- **Breaking:** Remove the `insert_all` parameter from `insert_into_briefing`.
## [1.2.0]
### Added
- Sentiment distribution  visualisation to show the number of sections classified as positive, neutral, or negative.
- Tone distribution visualisation to show the frequency of different communication tones in UN briefings.
- Sentiment and tone relationship visualisation to explore how sentiment categories relate to communication tones..
- The sentiment graph shows whether positive, neutral, or negative classifications increase or decrease over time.
- The tone graph shows how the frequency of communication tones changes each month.
- A value of zero means no successful classifications for that category were recorded in that month.
## [1.0.1]

### Added

- New module `analysis/` to keep the processing steps with LLM
- New submodule `analysis/sdg.py` to extract SDG mentions from sections
- Add a `tests/conftest.py` file for fixtures used by multiple modules
- Add a `prompts.py` module to save the multiple prompts used in the project
- SDG mentions page to the Streamlit app `02_SDG_Mentions.py`
- 17 SDG icons to the project in `app/static/sdg/`
- Add `pytest-mock` dev dependency for mocking

### Updated

- `SDG_mentions_in_briefings.ipynb` notebook using the database module


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
