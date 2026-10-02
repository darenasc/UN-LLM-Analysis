import argparse
from collections.abc import Iterator
from datetime import date, timedelta


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


def _parse_date(value: str) -> date:
    """Parse a string in YYYY-MM-DD format into a date object.

    Args:
        value (str): Date string in YYYY-MM-DD format.

    Returns:
        date: Parsed date object.

    Raises:
        argparse.ArgumentTypeError: If the date string is invalid.
    """
    try:
        return date.fromisoformat(value)
    except ValueError as exc:
        raise argparse.ArgumentTypeError(f"Invalid date: {value}. Expected YYYY-MM-DD.") from exc
