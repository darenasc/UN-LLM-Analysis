import argparse
from datetime import date

import pytest

from un_llm_analysis.scraper import _dates_between, _parse_date


def test_parse_date_valid():
    # GIVEN a valid date
    date_string = "2026-08-01"

    # WHEN _parse_date is called
    result = _parse_date(date_string)

    # THEN the result should match the expected date
    assert result == date(2026, 8, 1)


def test_parse_date_invalid():
    # GIVEN an invalid date
    date_string = "2026-02-30"

    # WHEN _parse_date is called
    # THEN ArgumentTypeError is raised.
    with pytest.raises(argparse.ArgumentTypeError):
        _parse_date(date_string)


def test_dates_between():
    # GIVEN a start date and an end date
    start_date = date(2026, 1, 30)
    end_date = date(2026, 2, 1)
    expected_dates = [date(2026, 1, 30), date(2026, 1, 31), date(2026, 2, 1)]

    # WHEN _dates_between is called
    result = list(_dates_between(start_date, end_date))

    # THEN the result should match the expected dates
    assert result == expected_dates
