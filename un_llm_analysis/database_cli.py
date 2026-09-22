
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
from datetime import date, datetime
import sys
import sqlite3
from zoneinfo import ZoneInfo
from loguru import logger

from un_llm_analysis.config import MIN_SCRAPE_DATE
from un_llm_analysis.database import (
    create_database,
    get_db_connection,
    query_by_date, query_by_status,
    load_between_dates
)
from un_llm_analysis.utils import _parse_date

def show_stats(conn: sqlite3.Connection | None = None) -> None:
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
