from datetime import timedelta
from collections.abc import Iterator

def _dates_between(start_date: date, end_date: date) -> Iterator[date]:
    """Yield dates from start_date to end_date, inclusive.

    Args:
        start_date (date): The date to start the sequence from.
        end_date (date): The date to end the sequence at.

    Yields:
        Iterator[date]: An iterator yielding dates in the range [start_date, end_date].
    """
    min_date = min(start_date, end_date)
    max_date = max(start_date, end_date)
    current_date = min_date
    while current_date <= max_date:
        yield current_date
        current_date += timedelta(days=1)