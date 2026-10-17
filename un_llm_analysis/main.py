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
from zoneinfo import ZoneInfo

from loguru import logger

from un_llm_analysis.config import MIN_SCRAPE_DATE
from un_llm_analysis.database import (
    create_database,
    get_db_connection,
    load_briefings_between_dates,
    query_briefing_by_date,
    query_briefing_by_status,
    show_stats,
)
from un_llm_analysis.scraper import (
    _is_briefing_scraped,
    scrape_between_dates,
)
from un_llm_analysis.utils import _parse_date


def _build_parser() -> argparse.ArgumentParser:
    """Build and return the argument parser for the script."""

    formatter = argparse.RawDescriptionHelpFormatter

    parser = argparse.ArgumentParser(
        description="Download, check and (database) load and query UN noon briefing data.",
        epilog="""Examples:
  %(prog)s update 2026-08-12
  %(prog)s update 2026-08-01 2026-08-12
  %(prog)s update --since 2026-08-01
  %(prog)s check 2026-08-12
  %(prog)s init-db
  %(prog)s load 2026-08-01 2026-08-12
  %(prog)s load --since 2026-08-01
  %(prog)s query --date 2026-08-01
  %(prog)s query --status available
  %(prog)s stats

Run '%(prog)s COMMAND --help' for details about a command.
""",
        formatter_class=formatter,
    )

    subparsers = parser.add_subparsers(dest="command", required=True)

    update_parser = subparsers.add_parser(
        "update",
        help="Download briefings for a given date or range of dates.",
        description="""Download UN noon briefings and save them as JSON.

Use positional dates or the --since option, but do not combine them.
""",
        epilog="""Examples:
  %(prog)s 2026-08-12
  %(prog)s 2026-08-01 2026-08-12
  %(prog)s --since 2026-08-01

--overwrite may be added to any form.

Scraped raw data location:
  PROJ_ROOT/data/raw/briefings/YYYY/YYYY-MM/YYYY-MM-DD.json
""",
        usage=("%(prog)s [-h] [--overwrite] " "(DATE [DATE] | " "--since DATE)"),
        formatter_class=formatter,
    )

    update_parser.add_argument(
        "dates",
        nargs="*",
        type=_parse_date,
        metavar="DATE",
        help=(
            "One date to update, or two dates defining an inclusive range. " "Format: YYYY-MM-DD."
        ),
    )
    update_parser.add_argument(
        "--since",
        type=_parse_date,
        help=("Update from the given date through today, inclusive. " "Format: YYYY-MM-DD."),
    )
    update_parser.add_argument(
        "--overwrite",
        action="store_true",
        help="Re-download and overwrite existing data instead of skipping it.",
    )

    check_parser = subparsers.add_parser(
        "check",
        help="Check existence of stored briefing data for a given date.",
        description=(
            "Check if a briefing for a given date has already been downloaded and stored as JSON."
        ),
        epilog="""Example:
  %(prog)s 2026-08-12

Scraped raw data location:
  PROJ_ROOT/data/raw/briefings/YYYY/YYYY-MM/YYYY-MM-DD.json
""",
        formatter_class=formatter,
    )
    check_parser.add_argument(
        "date", type=_parse_date, metavar="DATE", help="Date to check in YYYY-MM-DD format."
    )

    # init-db command
    init_parser = subparsers.add_parser(
        "init-db",
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


def _resolve_update_request(
    parser: argparse.ArgumentParser, args: argparse.Namespace
) -> tuple[date, date, bool]:
    """Resolve update arguments into a tuple of (start_date, end_date,
        overwrite).

    Args:
        parser (argparse.ArgumentParser): Parser object.
        args (argparse.Namespace): Arguments passed.

    Returns:
        tuple[date, date, bool]: Arguments for start_date, end_date and
            overwrite.
    """

    today = datetime.now(ZoneInfo("America/New_York")).date()

    if args.dates and args.since is not None:
        parser.error("--since cannot be used with positional dates.")

    start_date = None
    end_date = None

    if args.dates:
        if len(args.dates) > 2:
            parser.error("At most two positional dates may be provided.")
        elif len(args.dates) == 1:
            start_date = end_date = args.dates[0]
        else:  # len(args.dates) must be 2
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

    overwrite = args.overwrite

    return start_date, end_date, overwrite


def _resolve_load_request(
    parser: argparse.ArgumentParser, args: argparse.Namespace
) -> tuple[date, date, bool, bool]:
    """Resolve load arguments into (start_date, end_date, overwrite, dry_run).

    Args:
        parser (argparse.ArgumentParser): Argument parser object.
        args (argparse.Namespace): Parsed command-line arguments.

    Returns:
        tuple[date, date, bool, bool]: Tuple containing start_date, end_date,
            overwrite flag, and dry_run flag.
    """
    today = datetime.now(ZoneInfo("America/New_York")).date()
    start_date = None
    end_date = None

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
    """Main entry point for the script."""

    parser = _build_parser()
    args = parser.parse_args()

    if args.command == "check":
        date_string = args.date.strftime("%Y-%m-%d")
        if _is_briefing_scraped(args.date):
            logger.info(f"Briefing for {date_string} exists in the data directory.")
        else:
            logger.info(f"Briefing for {date_string} does NOT exist in the data directory.")

    elif args.command == "update":  # pragma: no branch
        start_date, end_date, overwrite = _resolve_update_request(parser, args)
        logger.info(
            f"Updating briefings from {start_date} to {end_date}, overwrite={overwrite} ..."
        )
        scrape_between_dates(start_date, end_date, overwrite=overwrite)
        logger.info("Update complete.")

    elif args.command == "init-db":
        logger.info("Initializing database...")
        create_database()
        logger.info("Database initialized.")

    elif args.command == "load":
        start_date, end_date, overwrite, dry_run = _resolve_load_request(parser, args)
        logger.info(
            f"Loading briefings from {start_date} to {end_date}, overwrite={overwrite}, dry_run={dry_run}..."
        )
        success = load_briefings_between_dates(
            start_date, end_date, conn=get_db_connection(), overwrite=overwrite, dry_run=dry_run
        )
        if not success:
            sys.exit(1)

    elif args.command == "query":
        if args.date:
            query_briefing_by_date(args.date, conn=get_db_connection())
        else:
            query_briefing_by_status(args.status, conn=get_db_connection())

    elif args.command == "stats":
        show_stats(conn=get_db_connection())


if __name__ == "__main__":  # pragma: no cover
    main()
