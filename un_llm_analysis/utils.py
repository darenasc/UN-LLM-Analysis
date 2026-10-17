import argparse
from collections.abc import Iterator
from datetime import date, datetime, timedelta

from loguru import logger
import ollama


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


def date_int_to_str(value: int) -> str:
    """Convert YYYYMMDD integer to YYYY-MM-DD string.

    Args:
        value (int): Date as an integer in YYYYMMDD format.

    Returns:
        str: Date string in YYYY-MM-DD format.
    """
    return date.fromisoformat(str(value)).isoformat()


def _check_ollama_model_exists(model: str) -> bool:
    """Check if a given model is available via Ollama.

    Args:
        model (str): Model name.

    Returns:
        bool: True if the model is available.
    """
    model_list = ollama.list()
    models = [x["model"] for x in model_list["models"]]
    if model in models or model in [x["model"].split(":")[0] for x in model_list["models"]]:
        return True
    else:
        logger.warning(
            f"'{model}' not available. Please select one of the following models {models} or pull {model} with Ollama."
        )
        return False
