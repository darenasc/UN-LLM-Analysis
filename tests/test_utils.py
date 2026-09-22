from datetime import date
from un_llm_analysis.utils import _dates_between

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
    """Test _dates_between with single day range.
    """
    start = date(2023, 1, 1)
    end = date(2023, 1, 1)
    result = list(_dates_between(start, end))
    expected = [date(2023, 1, 1)]
    assert result == expected

