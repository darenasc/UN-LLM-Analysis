from datetime import date
from pathlib import Path
from unittest.mock import patch

import pytest

from un_llm_analysis.utils import _dates_between, _parse_date


def test_dates_between():
    # GIVEN a start date and an end date
    start_date = date(2026, 1, 30)
    end_date = date(2026, 2, 1)
    expected_dates = [date(2026, 1, 30), date(2026, 1, 31), date(2026, 2, 1)]

    # WHEN _dates_between is called
    result = list(_dates_between(start_date, end_date))

    # THEN the result should match the expected dates
    assert result == expected_dates


def test_dates_between_single_day():
    """Test _dates_between with single day range."""
    start = date(2023, 1, 1)
    end = date(2023, 1, 1)
    result = list(_dates_between(start, end))
    expected = [date(2023, 1, 1)]
    assert result == expected


def test_parse_date_valid():
    """Test _parse_date with valid date string."""
    result = _parse_date("2023-08-12")
    assert result == date(2023, 8, 12)


def test_parse_date_invalid():
    """Test _parse_date with invalid date string."""
    with pytest.raises(Exception):  # argparse.ArgumentTypeError
        _parse_date("2023/08/12")


def test_parse_date_invalid_format():
    """Test _parse_date with malformed date string."""
    with pytest.raises(Exception):  # argparse.ArgumentTypeError
        _parse_date("not-a-date")
