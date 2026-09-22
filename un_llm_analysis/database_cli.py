
"""CLI for managing the UN noon briefing database.

This module provides command-line interface for:
- Initializing the database from schema
- Loading extracted briefings from JSON files
- Querying briefings by date or status
- Displaying database statistics

The CLI follows a layered architecture:
- Data Layer: extractor.py, database.py
- Business Logic: Helper functions and core operations
- CLI Layer: Argument parsing, validation, and dispatch
"""

import argparse
from collections.abc import Iterator
from datetime import date, datetime, timedelta
import os
from pathlib import Path
import sqlite3
import sys
from zoneinfo import ZoneInfo

from loguru import logger

from un_llm_analysis.config import BRIEFINGS_DIR, MIN_SCRAPE_DATE
from un_llm_analysis.database import (
    create_database,
    get_briefing_by_id,
    get_briefing_id_from_date,
    get_db_connection,
    insert_into_briefing,
    insert_into_section,
)
from un_llm_analysis.extractor import extract_briefing




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


def _is_briefing_json_exists(briefing_date: date) -> bool:
    """Check if a briefing JSON file exists for the given date.

    Args:
        briefing_date (date): Date of the briefing to check.

    Returns:
        bool: True if the JSON file exists, False otherwise.
    """
    date_string = briefing_date.strftime("%Y-%m-%d")
    briefing_path = os.path.join(
        BRIEFINGS_DIR, date_string[:4], date_string[:7], f"{date_string}.json"
    )
    return os.path.exists(briefing_path)


def load_briefing_to_db(file_path: Path, conn: sqlite3.Connection) -> bool:
    """Load a single briefing JSON file into the database.

    Args:
        file_path (Path): Path to the briefing JSON file.
        conn (sqlite3.Connection): Database connection object.

    Returns:
        bool: True if loading succeeded, False otherwise.
    """
    try:
        briefing = extract_briefing(file_path)
        with conn:
            briefing_id = insert_into_briefing(conn, briefing)
            if briefing.sections:
                insert_into_section(conn, briefing_id, briefing.sections)
        logger.info(f"Loaded briefing from {file_path}")
        return True
    except Exception as exc:
        logger.error(f"Error loading {file_path}: {exc}")
        return False


def load_between_dates(
    start_date: date, end_date: date, overwrite: bool = False, dry_run: bool = False
) -> bool:
    """Load briefings from JSON files into database for a date range.

    Args:
        start_date (date): The date to start loading from.
        end_date (date): The date to end loading at.
        overwrite (bool): Whether to overwrite existing briefings. Defaults to False.
        dry_run (bool): If True, preview what would be loaded without actually loading. Defaults to False.

    Returns:
        bool: True if every loaded briefing succeeded (or nothing needed loading),
            False if at least one briefing failed to load.
    """
    requested_dates = list(_dates_between(start_date, end_date))

    if dry_run:
        logger.info("DRY RUN - No changes will be made:")
        for briefing_date in requested_dates:
            date_string = briefing_date.strftime("%Y-%m-%d")
            file_path = Path(
                f"{BRIEFINGS_DIR}/{date_string[:4]}/{date_string[:7]}/{date_string}.json"
            )
            if not _is_briefing_json_exists(briefing_date):
                logger.info(f"  - No JSON file for {date_string}, would skip")
            else:
                logger.infof"  [{date_string}] Would load from {file_path}")
        logger.info(f"Total: {len(requested_dates)} dates requested.")
        logger.info("Dry run complete.")
        return True

    failed_dates: list[str] = []

    with get_db_connection() as conn:
        if overwrite:
            dates_to_load = requested_dates
        else:
            existing_dates = _get_existing_briefing_dates(conn, start_date, end_date)
            dates_to_load = [d for d in requested_dates if d not in existing_dates]

        logger.info(f"{len(requested_dates)} dates requested. {len(dates_to_load)} to load.")

        if not dates_to_load:
            logger.info("All requested briefings already in database.")
            return True

        for i, briefing_date in enumerate(dates_to_load):
            date_string = briefing_date.strftime("%Y-%m-%d")
            file_path = Path(
                f"{BRIEFINGS_DIR}/{date_string[:4]}/{date_string[:7]}/{date_string}.json"
            )

            if not _is_briefing_json_exists(briefing_date):
                logger.info(f"  - No JSON file for {date_string}, skipping")
                continue

            logger.info(f"  [{i + 1}/{len(dates_to_load)}] {date_string} Loading...")
            success = load_briefing_to_db(file_path, conn)
            if not success:
                failed_dates.append(date_string)

    if failed_dates:
        print(f"Load complete with {len(failed_dates)} failure(s): {', '.join(failed_dates)}")
        return False

    logger.info("Load complete.")
    return True


def query_by_date(query_date: date) -> None:
    """Query and display a briefing by date.

    Args:
        query_date (date): Date of the briefing to query.
    """
    with get_db_connection() as conn:
        briefing_id = get_briefing_id_from_date(query_date.strftime("%Y-%m-%d"))
        briefing = get_briefing_by_id(conn, briefing_id)

    if briefing:
        logger.info(f"Briefing found for {query_date}:")
        logger.info(f"  URL: {briefing.url}")
        logger.info(f"  Status: {briefing.status}")
        logger.info(f"  Speaker: {briefing.speaker_name} ({briefing.speaker_role})")
        logger.info(f"  Sections: {len(briefing.sections)}")
    else:
        logger.info(f"No briefing found for {query_date}")


def query_by_status(status: str) -> None:
    """Query and display briefings by status.

    Args:
        status (str): Status to filter briefings by, or "all" for all briefings.
    """
    with get_db_connection() as conn:
        cursor = conn.cursor()
        if status == "all":
            cursor.execute("SELECT briefing_date, url, status FROM briefing")
        else:
            cursor.execute(
                "SELECT briefing_date, url, status FROM briefing WHERE status = ?",
                (status,),
            )
        rows = cursor.fetchall()

    logger.info(f"Found {len(rows)} briefings with status '{status}':")
    for row in rows:
        logger.info(f"  {row['briefing_date']}: {row['url']}")


def _get_existing_briefing_dates(
    conn: sqlite3.Connection, start_date: date, end_date: date
) -> set[date]:
    """Fetch the set of briefing dates already in the database within a range.

    Args:
        conn (sqlite3.Connection): Database connection object.
        start_date (date): Start of the range (inclusive).
        end_date (date): End of the range (inclusive).

    Returns:
        set[date]: Dates that already have a briefing row in the database.
    """
    cursor = conn.cursor()
    cursor.execute(
        "SELECT briefing_date FROM briefing WHERE briefing_date BETWEEN ? AND ?",
        (start_date.isoformat(), end_date.isoformat()),
    )
    return {date.fromisoformat(row["briefing_date"]) for row in cursor.fetchall()}


def show_stats() -> None:
    """Display database statistics.

    Prints total briefings count, date range, and count by status.
    """
    with get_db_connection() as conn:
        cursor = conn.cursor()

        # Total count
        cursor.execute("SELECT COUNT(*) as count FROM briefing")
        total = cursor.fetchone()["count"]

        # Count by status
        cursor.execute("SELECT status, COUNT(*) as count FROM briefing GROUP BY status")
        status_counts = {row["status"]: row["count"] for row in cursor.fetchall()}

        # Date range
        cursor.execute(
            "SELECT MIN(briefing_date) as min_date, MAX(briefing_date) as max_date FROM briefing"
        )
        date_range = cursor.fetchone()

    logger.info("Database Statistics:")
    logger.info(f"  Total briefings: {total}")
    logger.info(f"  Date range: {date_range['min_date']} to {date_range['max_date']}")
    logger.info("  By status:")
    for status, count in status_counts.items():
        logger.info(f"    {status}: {count}")


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


def _build_parser() -> argparse.ArgumentParser:
    """Build and return the argument parser for the script.

    Returns:
        argparse.ArgumentParser: Configured argument parser with subcommands.
    """
    formatter = argparse.RawDescriptionHelpFormatter

    parser = argparse.ArgumentParser(
        description="Manage UN noon briefing database.",
        epilog="""Examples:
  %(prog)s init
  %(prog)s load 2023-01-01 2023-12-31
  %(prog)s load --since 2023-01-01
  %(prog)s query --date 2023-08-12
  %(prog)s query --status available
  %(prog)s stats

Run '%(prog)s COMMAND --help' for details about a command.
""",
        formatter_class=formatter,
    )

    subparsers = parser.add_subparsers(dest="command", required=True)

    # init command
    init_parser = subparsers.add_parser(
        "init",
        help="Initialize the database from schema.",
        description="Create the database file and tables from the SQL schema.",
    )

    # load command
    load_parser = subparsers.add_parser(
        "load",
        help="Load briefings from JSON files into database.",
        description="Load extracted briefings from JSON files into the database.",
        epilog="""Examples:
  %(prog)s 2023-01-01
  %(prog)s 2023-01-01 2023-12-31
  %(prog)s --since 2023-01-01

--overwrite and --dry-run may be added to any form.
""",
        usage="%(prog)s [-h] [--overwrite] [--dry-run] (DATE [DATE] | --since DATE)",
        formatter_class=formatter,
    )
    load_parser.add_argument(
        "dates",
        nargs="*",
        type=_parse_date,
        metavar="DATE",
        help="One date to load, or two dates defining an inclusive range. Format: YYYY-MM-DD.",
    )
    load_parser.add_argument(
        "--since",
        type=_parse_date,
        help="Load from the given date through today, inclusive. Format: YYYY-MM-DD.",
    )
    load_parser.add_argument(
        "--overwrite",
        action="store_true",
        help="Re-load and overwrite existing data instead of skipping it.",
    )
    load_parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Preview what would be loaded without actually loading.",
    )

    # query command
    query_parser = subparsers.add_parser(
        "query",
        help="Query briefings from the database.",
        description="Query and display briefings by date or status.",
    )
    query_group = query_parser.add_mutually_exclusive_group(required=True)
    query_group.add_argument(
        "--date",
        type=_parse_date,
        metavar="DATE",
        help="Query briefing by date. Format: YYYY-MM-DD.",
    )
    query_group.add_argument(
        "--status",
        choices=["available", "not_published", "failed", "all"],
        help="Query briefings by status.",
    )

    # stats command
    stats_parser = subparsers.add_parser(
        "stats",
        help="Show database statistics.",
        description="Display statistics about the database contents.",
    )

    return parser


def _resolve_load_request(
    parser: argparse.ArgumentParser, args: argparse.Namespace
) -> tuple[date, date, bool, bool]:
    """Resolve load arguments into (start_date, end_date, overwrite, dry_run).

    Args:
        parser (argparse.ArgumentParser): Argument parser object.
        args (argparse.Namespace): Parsed command-line arguments.

    Returns:
        tuple[date, date, bool, bool]: Tuple containing start_date, end_date, overwrite flag, and dry_run flag.
    """
    today = datetime.now(ZoneInfo("America/New_York")).date()

    if args.dates and args.since is not None:
        parser.error("--since cannot be used with positional dates.")

    if args.dates:
        if len(args.dates) > 2:
            parser.error("At most two positional dates may be provided.")
        elif len(args.dates) == 1:
            start_date = end_date = args.dates[0]
        else:
            start_date, end_date = args.dates
    elif args.since is not None:
        start_date = args.since
        end_date = today
    else:
        parser.error(
            "No dates specified. Provide one or two positional dates, or use --since DATE."
        )

    if start_date > end_date:
        parser.error(f"Start date {start_date} cannot be after end date {end_date}.")

    if start_date < MIN_SCRAPE_DATE or end_date > today:
        parser.error(f"Dates must be between {MIN_SCRAPE_DATE} and {today}.")

    return start_date, end_date, args.overwrite, args.dry_run


def main() -> None:
    """Main entry point for the script.

    Parses command-line arguments and dispatches to the appropriate command handler.
    """
    parser = _build_parser()
    args = parser.parse_args()

    if args.command == "init":
        logger.info("Initializing database...")
        create_database()
        logger.info("Database initialized.")

    elif args.command == "load":
        start_date, end_date, overwrite, dry_run = _resolve_load_request(parser, args)
        logger.info(
            f"Loading briefings from {start_date} to {end_date}, overwrite={overwrite}, dry_run={dry_run}..."
        )
        success = load_between_dates(start_date, end_date, overwrite=overwrite, dry_run=dry_run)
        if not success:
            sys.exit(1)

    elif args.command == "query":
        if args.date:
            query_by_date(args.date)
        else:
            query_by_status(args.status)

    elif args.command == "stats":
        show_stats()


if __name__ == "__main__":
    main()
