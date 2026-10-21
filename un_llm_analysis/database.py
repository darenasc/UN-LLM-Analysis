"""UN database module for persisting and querying UN briefing data.
Provides access to the following tables:

Tables:
    - `briefing`
    - `section`
    - `sdg`
    - `issue`
    - `analysis_run`
    - `sentiment_analysis`

Supports inserting, updating, and deleting briefings, sections, SDG mappings,
analysis runs, and sentiment results via SQL or Python interfaces.
"""

import ast
from dataclasses import dataclass
from datetime import date, datetime
from pathlib import Path
import sqlite3
from typing import Literal, get_args

from loguru import logger
import pandas as pd
import pendulum

from un_llm_analysis.config import BRIEFINGS_DB_PATH, BRIEFINGS_DIR, SCHEMA_DB
from un_llm_analysis.extractor import (
    ExtractedBriefing,
    ExtractedSection,
    extract_briefing,
)
from un_llm_analysis.scraper import FetchStatus
from un_llm_analysis.utils import (
    _dates_between,
    date_int_to_str,
)

AnalysisTableName = Literal["sdg", "issue", "country"]


@dataclass(frozen=True, kw_only=True)
class Section(ExtractedSection):
    """A stored section, including its actual database identifiers."""

    section_id: int
    briefing_id: int
    section_order: int


@dataclass(frozen=True, kw_only=True)
class Briefing(ExtractedBriefing):
    """A stored briefing with its database metadata and stored sections."""

    briefing_id: int
    processed_at: str
    full_text: str
    sections: tuple[Section, ...]


_BRIEFING_COLUMNS = """
    briefing_id, briefing_date, url, status, http_status, error,
    speaker_name, speaker_role, full_text, downloaded_at, processed_at
"""
_SECTION_COLUMNS = "section_id, briefing_id, section_order, title, text"


def _row_to_section(row: sqlite3.Row) -> Section:
    """Convert a sqlite3.Row to a Section dataclass instance.

    Args:
        row (sqlite3.Row): A row from the section table.

    Returns:
        Section: A Section dataclass instance populated with the row data.
    """
    return Section(**dict(row))


def _row_to_briefing(row: sqlite3.Row, sections: tuple[Section, ...]) -> Briefing:
    """Convert a sqlite3.Row to a Briefing dataclass instance.

    Args:
        row (sqlite3.Row): A row from the briefing table.
        sections (tuple[Section, ...]): A tuple of Section dataclass instances.

    Returns:
        Briefing: A Briefing dataclass instance populated with the row data and sections.
    """
    return Briefing(**dict(row), sections=sections)


def get_db_connection(db_path: str | Path = BRIEFINGS_DB_PATH) -> sqlite3.Connection:
    """Connect to SQLite database with foreign keys enabled.

    Args:
        db_path (str): Path to the SQLite database file (or ":memory:").

    Returns:
        sqlite3.Connection: Open connection with foreign_keys pragma set.
    """
    conn = sqlite3.connect(db_path)
    conn.execute("PRAGMA foreign_keys = ON")
    conn.row_factory = sqlite3.Row
    return conn


def create_database(
    db_path: str | Path = BRIEFINGS_DB_PATH, schema_path: str | Path = SCHEMA_DB
) -> None:
    """Create the database file and tables if they don't already exist.

    Args:
        db_path (str | Path): Path to the SQLite database file to create/open.
        schema_path (str | Path): Path to the SQL schema of the database.
    """
    with open(schema_path, "r", encoding="utf-8") as f:
        sql_schema = f.read()

    conn = get_db_connection(db_path)
    with conn:
        conn.executescript(sql_schema)
    conn.close()

    logger.info(f'Database created in "{db_path}"')


# --- briefing ------------------------------------------------------------
def get_briefing_id_from_date(date: str) -> int:
    """Returns a YYYYMMDD int from a 'YYYY-MM-DD' str.

    Args:
        date (str): Date of the briefing. Format 'YYYY-MM-DD'.

    Returns:
        int: The briefing date in numeric format YYYYMMDD.
    """
    briefing_date = datetime.strptime(date, "%Y-%m-%d")
    return briefing_date.year * 10000 + briefing_date.month * 100 + briefing_date.day


def get_min_max_briefing_ids_from_dates(start_date: str, end_date: str) -> tuple[int, int]:
    """Get the minimum and maximum briefing IDs for a given date range.

    Args:
        start_date (str): Start date in 'YYYY-MM-DD' format.
        end_date (str): End date in 'YYYY-MM-DD' format.

    Returns:
        tuple[int, int]: A tuple containing the minimum and maximum briefing IDs.
    """
    _start = get_briefing_id_from_date(start_date)
    _end = get_briefing_id_from_date(end_date)
    return min(_start, _end), max(_start, _end)


def insert_into_briefing(
    conn: sqlite3.Connection,
    briefing: ExtractedBriefing,
) -> int:
    """Insert a briefing into the database. If one with the same ID exists, delete it and its sections first.

    Args:
        conn (sqlite3.Connection): Database connection.
        briefing (ExtractedBriefing): Briefing object.

    Returns:
        int: `briefing_id` to confirm a successful insertion.
    """
    briefing_id = get_briefing_id_from_date(briefing.briefing_date)
    delete_briefing(conn=conn, briefing_id=briefing_id)

    query_insert = """
        INSERT INTO briefing (briefing_id, briefing_date, url, status, http_status, error, speaker_name, speaker_role, full_text, downloaded_at, processed_at)
        VALUES(?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """

    conn.execute(
        query_insert,
        (
            briefing_id,
            briefing.briefing_date,
            briefing.url,
            briefing.status,
            briefing.http_status,
            briefing.error,
            briefing.speaker_name,
            briefing.speaker_role,
            briefing.full_text or "",
            briefing.downloaded_at,
            str(datetime.now()),
        ),
    )

    logger.info(f"Briefing from '{briefing.briefing_date}' inserted to the database.")
    return briefing_id


def get_sections_by_briefing_id(conn: sqlite3.Connection, briefing_id: int) -> tuple[Section, ...]:
    """Return a tuple with the sections from the database corresponding the
    briefing_id.

    Args:
        conn (sqlite3.Connection): Database connection.
        briefing_id (int): Briefing id.

    Returns:
        tuple[Section, ...]: Sections stored in the database
            associated to the briefing.
    """
    rows = conn.execute(
        f"""
        SELECT {_SECTION_COLUMNS} FROM section
        WHERE briefing_id = ?
        ORDER BY section_id
        """,
        (briefing_id,),
    ).fetchall()

    sections = tuple(_row_to_section(row) for row in rows)

    return sections


def get_briefing_by_id(conn: sqlite3.Connection, briefing_id: int) -> Briefing | None:
    """Retrieve briefing by ID.

    Args:
        conn (sqlite3.Connection): Open database connection.
        briefing_id (int): Primary key of the briefing.

    Returns:
        Briefing | None: The briefing data from the database given a
            briefing_id, or None if not found.
    """
    row = conn.execute(
        f"""
        SELECT {_BRIEFING_COLUMNS} FROM briefing
        WHERE briefing_id = ?
        """,
        (briefing_id,),
    ).fetchone()

    if row:
        sections = get_sections_by_briefing_id(conn=conn, briefing_id=briefing_id)
        briefing = _row_to_briefing(row, sections)
        return briefing
    else:
        return None


def get_briefing_by_url(conn: sqlite3.Connection, url: str) -> Briefing | None:
    """Retrieve briefing by URL.

    Args:
        conn (sqlite3.Connection): Open database connection.
        url (str): URL of the briefing.

    Returns:
        Briefing | None: The matching briefing, or None if not found.
    """
    briefing_id = get_briefing_id_by_url(conn=conn, url=url)

    if briefing_id:
        return get_briefing_by_id(conn=conn, briefing_id=briefing_id)
    else:
        return None


def get_briefing_by_date(conn: sqlite3.Connection, date: str) -> Briefing | None:
    """Retrieve briefing by date.

    Args:
        conn (sqlite3.Connection): Open database connection.
        date (str): Date of the briefing.

    Returns:
        Briefing | None: The matching briefing, or None if not found.
    """
    briefing_id = get_briefing_id_from_date(date=date)
    briefing = get_briefing_by_id(conn=conn, briefing_id=briefing_id)
    return briefing


def get_briefings_between_dates(
    conn: sqlite3.Connection, start_date: str, end_date: str
) -> list[Briefing]:
    """Retrieve briefings between two dates.

    Args:
        conn (sqlite3.Connection): Database connection.
        start_date (str): Start date with format 'YYYY-MM-DD'.
        end_date (str): End date with format 'YYYY-MM-DD'.

    Returns:
        list[Briefing]: Matching briefings, or an empty list if none are found.
    """
    bounds = get_min_max_briefing_ids_from_dates(start_date, end_date)

    briefing_rows = conn.execute(
        f"""
        SELECT {_BRIEFING_COLUMNS} FROM briefing
        WHERE briefing_id BETWEEN ? AND ?;
        """,
        bounds,
    ).fetchall()

    sections = get_sections_between_dates(conn=conn, start_date=start_date, end_date=end_date)

    sections_by_briefing: dict[int, list[Section]] = {
        row["briefing_id"]: [] for row in briefing_rows
    }

    for section in sections:
        sections_by_briefing[section.briefing_id].append(section)

    logger.info(
        f"{len(briefing_rows):,} briefings obtained between '{start_date}' and '{end_date}'"
    )
    return [
        _row_to_briefing(
            row,
            tuple(sections_by_briefing[row["briefing_id"]]),
        )
        for row in briefing_rows
    ]


def get_briefing_id_by_url(conn: sqlite3.Connection, url: str) -> int | None:
    """Get briefing ID by URL.

    Args:
        conn (sqlite3.Connection): Open database connection.
        url (str): URL of the briefing.

    Returns:
        int | None: The briefing_id, or None if no match.
    """
    row = conn.execute(
        "SELECT briefing_id FROM briefing WHERE url = ?",
        (url,),
    ).fetchone()

    if row is None:
        return None

    return row["briefing_id"]


def delete_briefing(conn: sqlite3.Connection, briefing_id: int) -> bool:
    """Delete briefing by ID.

    Args:
        conn (sqlite3.Connection): Open database connection.
        briefing_id (int): Primary key of the briefing to delete.

    Returns:
        bool: True if a row was deleted, False otherwise.
    """
    cursor = conn.execute(
        "DELETE FROM briefing WHERE briefing_id = ?",
        (briefing_id,),
    )

    return cursor.rowcount > 0


# --- section ---------------------------------------------------------------


def insert_into_section(
    conn: sqlite3.Connection,
    briefing_id: int,
    sections: tuple[ExtractedSection, ...],
) -> int:
    """Insert sections into the database. If any sections already exist, delete them first.

    Args:
        conn (sqlite3.Connection): Open database connection.
        briefing_id (int): ID of the parent briefing.
        sections (tuple[ExtractedSection, ...]): Sections from the briefing.
    """
    delete_sections(conn=conn, briefing_id=briefing_id)

    query_insert = """
        INSERT INTO "section" (section_id, briefing_id, section_order, title, "text")
        VALUES(?, ?, ?, ?, ?)
    """

    data = []
    for i, section in enumerate(sections, start=1):
        section_id = briefing_id * 100 + i
        data.append((section_id, briefing_id, i, section.title, section.text))

    conn.executemany(query_insert, data)

    return briefing_id


def insert_section(
    conn: sqlite3.Connection,
    briefing_id: int,
    section: ExtractedSection,
    section_order: int,
) -> int:
    """Insert a single section into the database.

    Args:
        conn (sqlite3.Connection): Open database connection.
        briefing_id (int): ID of the parent briefing.
        section (ExtractedSection): Section of the briefing containing the
            title and text.
        section_order (int): Position of the section within the briefing.

    Returns:
        int: The section_id of the inserted row.
    """
    section_id = briefing_id * 100 + section_order
    conn.execute(
        """
        INSERT INTO section (
            section_id,
            briefing_id,
            section_order,
            title,
            text
        )
        VALUES (?, ?, ?, ?, ?)
        """,
        (
            section_id,
            briefing_id,
            section_order,
            section.title,
            section.text,
        ),
    )

    return section_id


def get_section_by_id(conn: sqlite3.Connection, section_id: int) -> Section | None:
    """Retrieve section by ID.

    Args:
        conn (sqlite3.Connection): Open database connection.
        section_id (int): Primary key of the section.

    Returns:
        Section | None: The matching section, or None if not found.
    """
    row = conn.execute(
        f"""
            SELECT {_SECTION_COLUMNS} FROM section
            WHERE section_id = ?
        """,
        (section_id,),
    ).fetchone()

    return _row_to_section(row) if row else None


def get_sections_between_dates(
    conn: sqlite3.Connection,
    start_date: str,
    end_date: str,
) -> list[Section]:
    """Retrieve sections between two dates.

    "section_id, briefing_id, section_order, title, text"

    Args:
        conn (sqlite3.Connection): Database connection.
        start_date (str): Start date with format 'YYYY-MM-DD'.
        end_date (str): End date with format 'YYYY-MM-DD'.

    Returns:
        list[Section]: Matching sections, or an empty list if none are found.
    """
    bounds = get_min_max_briefing_ids_from_dates(start_date, end_date)

    rows = conn.execute(
        f"""
        SELECT {_SECTION_COLUMNS} FROM section
        WHERE briefing_id BETWEEN ? AND ?
        ORDER BY section_id;
        """,
        bounds,
    ).fetchall()

    return [_row_to_section(row) for row in rows]


def delete_section(conn: sqlite3.Connection, section_id: int) -> bool:
    """Delete a section by ID.

    Args:
        conn (sqlite3.Connection): Open database connection.
        section_id (int): Primary key of the section to delete.

    Returns:
        bool: True if a row was deleted, False otherwise.
    """
    cursor = conn.execute(
        "DELETE FROM section WHERE section_id = ?",
        (section_id,),
    )

    logger.info(f"Deleted section '{section_id}'")

    return cursor.rowcount > 0


def delete_sections(conn: sqlite3.Connection, briefing_id: int) -> bool:
    """Delete all sections with the same briefing_id.

    Args:
        conn (sqlite3.Connection): Open database connection.
        briefing_id (int): Briefing key of the sections to delete.

    Returns:
        bool: True if a row was deleted, False otherwise.
    """
    cursor = conn.execute(
        "DELETE FROM section WHERE briefing_id = ?",
        (briefing_id,),
    )

    logger.info(f"Deleted the sections of briefing '{briefing_id}'")

    return cursor.rowcount > 0


# --- sdg -------------------------------------------------------------------


def insert_into_sdg(
    conn: sqlite3.Connection,
    briefing_id: int,
    section_id: int,
    sdgs: list,
    model: str,
    created_at: str,
    verbose: bool = True,
) -> None:
    """Insert data into sdg table.

    Args:
        conn (sqlite3.Connection): Connection to the database.
        briefing_id (int): Id of the briefing.
        section_id (int): Id of the section (briefing_id * 100 + section_order)
        sdgs (str): Text with list of SDG codes. "['SDG1', ..., 'SDG17']"
        model (str): Model name.
        created_at (str): Date of the processing.
        verbose (bool, optional): Show logging of the process. Defaults to True.
    """
    sql_insert = """
        INSERT INTO sdg (briefing_id, section_id, sdg, model, created_at)
        VALUES(?, ?, ?, ?, ?)
    """

    with conn:
        delete_from_sdg(conn=conn, section_id=section_id, model=model, verbose=verbose)

        conn.executemany(
            sql_insert,
            [(briefing_id, section_id, sdg, model, created_at) for sdg in sdgs],
        )

    if verbose:
        logger.info(f"{section_id} {sdgs} data inserted into `sdg`")


def delete_from_sdg(
    conn: sqlite3.Connection, section_id: int, model: str, verbose: bool = True
) -> bool:
    """Delete data from the sdg table.

    Args:
        conn (sqlite3.Connection): Connection to the database.
        section_id (int): Id of the section.
        model (str): Model name.
        verbose (bool, optional): Show logging of the process. Defaults to True.

    Returns:
        bool: Whether or not data was deleted.
    """
    cursor = conn.execute(
        "DELETE FROM sdg WHERE section_id = ? AND model = ?",
        (section_id, model),
    )

    if verbose:
        logger.info(f"Deleted sdg section'{section_id}' of model '{model}'")

    return cursor.rowcount > 0


def get_sdgs_between_dates(
    conn: sqlite3.Connection, start_date: str, end_date: str
) -> pd.DataFrame:
    """Return data from the sdg table.

    Args:
        conn (sqlite3.Connection): Database connection.
        start_date (str): Start date with format 'YYYY-MM-DD'.
        end_date (str): End date with format 'YYYY-MM-DD'.

    Returns:
        pd.DataFrame: Data from the sdg table.
    """
    min_briefing_id, max_briefing_id = get_min_max_briefing_ids_from_dates(start_date, end_date)

    sql_query = """
        SELECT briefing_id, section_id, sdg, model, created_at
        FROM sdg
        WHERE briefing_id between ? AND ?
    """

    return pd.read_sql_query(
        sql_query,
        conn,
        params=(min_briefing_id, max_briefing_id),
    )


def get_min_max_dates_with_table(
    conn: sqlite3.Connection,
    table: AnalysisTableName,
) -> tuple[str, str]:
    """Return the min and max briefing dates for the specified table.

    Returns:
        tuple[str, str]: Dates in YYYY-MM-DD format.
            Returns ("", "") if the table is empty.
    """
    if table not in get_args(AnalysisTableName):
        raise ValueError(f"Unsupported table: {table}")

    query = f"SELECT MIN(briefing_id), MAX(briefing_id) FROM {table}"
    min_id, max_id = conn.execute(query).fetchone()

    if min_id is None or max_id is None:
        return "", ""

    return date_int_to_str(min_id), date_int_to_str(max_id)


def get_sdg_by_section_id(
    conn: sqlite3.Connection, section_id: int, model: str = "llama3.2"
) -> list[str]:
    """Return a list of SDGs given a section_id.

    Args:
        conn (sqlite3.Connection): Connection to the database.
        section_id (int): Section id in the database.
        model (str): Model used to extract SDGs from section.

    Returns:
        list[str]: List with SDGs, or empty list if no SDGs.
    """
    rows = conn.execute(
        """
        SELECT sdg FROM sdg
        WHERE section_id = ? AND model = ?
        """,
        (section_id, model),
    ).fetchall()

    return [row["sdg"] for row in rows]


def get_models(conn: sqlite3.Connection, table: AnalysisTableName) -> list[str]:
    """Returns a list of models used for the specified analysis table.

    Args:
        conn (sqlite3.Connection): Connection to the database.
        table (AnalysisTableName): The analysis table to query.
    """

    if table not in get_args(AnalysisTableName):
        raise ValueError(f"Unsupported table: {table}")

    rows = conn.execute(f"SELECT DISTINCT model FROM {table} ORDER BY model").fetchall()

    models = [x["model"] for x in rows]

    return models


# --- issue -------------------------------------------------------------------


def insert_into_issue(
    conn: sqlite3.Connection,
    briefing_id: int,
    section_id: int,
    issues: str,
    model: str,
    created_at: str,
    verbose: bool = True,
) -> None:
    """Insert data into issue table.

    Args:
        conn (sqlite3.Connection): Connection to the database.
        briefing_id (int): Id of the briefing.
        section_id (int): Id of the section (briefing_id * 100 + section_order)
        issues (str): Text with list of ISSUE codes. "['ISSUE-1', ..., 'ISSUE-24']"
        model (str): Model name.
        created_at (str): Date of the processing.
        verbose (bool, optional): Show logging of the process. Defaults to True.
    """
    parsed_issues = ast.literal_eval(issues)
    if parsed_issues is None:
        return
    sql_insert = """
        INSERT INTO issue (briefing_id, section_id, issue, model, created_at)
        VALUES(?, ?, ?, ?, ?)
    """

    with conn:
        delete_from_issue(conn=conn, section_id=section_id, model=model, verbose=verbose)

        conn.executemany(
            sql_insert,
            [(briefing_id, section_id, issue, model, created_at) for issue in parsed_issues],
        )

    if verbose:
        logger.info(f"{section_id} {issues} data inserted into `issue`")


def delete_from_issue(
    conn: sqlite3.Connection, section_id: int, model: str, verbose: bool = True
) -> bool:
    """Delete data from the issue table.

    Args:
        conn (sqlite3.Connection): Connection to the database.
        section_id (int): Id of the section.
        model (str): Model name.
        verbose (bool, optional): Show logging of the process. Defaults to True.

    Returns:
        bool: Whether or not data was deleted.
    """

    cursor = conn.execute(
        """
        DELETE FROM issue
        WHERE section_id = ? AND model = ?
        """,
        (section_id, model),
    )

    if verbose:
        logger.info(f"Deleted issue section '{section_id}' of model '{model}'")

    return cursor.rowcount > 0


def get_issues_between_dates(
    conn: sqlite3.Connection, start_date: str, end_date: str
) -> pd.DataFrame:
    """Return data from the issue table.

    Args:
        conn (sqlite3.Connection): Database connection.
        start_date (str): Start date with format 'YYYY-MM-DD'.
        end_date (str): End date with format 'YYYY-MM-DD'.

    Returns:
        pd.DataFrame: Data from the issue table.
    """
    min_briefing_id, max_briefing_id = get_min_max_briefing_ids_from_dates(start_date, end_date)

    sql_query = """
        SELECT briefing_id, section_id, issue, model, created_at
        FROM issue
        WHERE briefing_id between ? AND ?
    """

    return pd.read_sql_query(
        sql_query,
        conn,
        params=(min_briefing_id, max_briefing_id),
    )


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
    except FileNotFoundError:
        logger.exception(f"Error loading {file_path}")
        return False


def load_briefings_between_dates(
    start_date: date,
    end_date: date,
    conn: sqlite3.Connection,
    overwrite: bool = False,
    dry_run: bool = False,
    briefings_dir: Path = BRIEFINGS_DIR,
) -> bool:
    """Load briefings from JSON files into database for a date range.

    Args:
        start_date (date): The date to start loading from.
        end_date (date): The date to end loading at.
        conn (sqlite3.Connection): Database connection object.
        overwrite (bool): Whether to overwrite existing briefings. Defaults to
            False.
        dry_run (bool): If True, preview what would be loaded without actually
            loading. Defaults to False.

    Returns:
        bool: True if every loaded briefing succeeded (or nothing needed loading),
            False if at least one briefing failed to load.
    """
    requested_dates = list(_dates_between(start_date, end_date))

    if dry_run:
        _log_dry_run(requested_dates=requested_dates, briefings_dir=briefings_dir)
        return True

    dates_to_load = _resolve_dates_to_load(
        conn=conn,
        requested_dates=requested_dates,
        start_date=start_date,
        end_date=end_date,
        overwrite=overwrite,
    )
    logger.info(f"{len(requested_dates)} dates requested. {len(dates_to_load)} to load.")

    if not dates_to_load:
        logger.info("All requested briefings already in database.")
        return True

    failed_dates = _load_dates(conn=conn, dates_to_load=dates_to_load, briefings_dir=briefings_dir)

    if failed_dates:
        logger.info(
            f"Load complete with {len(failed_dates)} failure(s): {', '.join(failed_dates)}"
        )
        return False

    logger.info("Load complete.")
    return True


def _log_dry_run(requested_dates: list[date], briefings_dir: Path = BRIEFINGS_DIR) -> None:
    """Log a preview of what load_between_dates would do, without loading anything."""
    logger.info("DRY RUN - No changes will be made:")
    for briefing_date in requested_dates:
        date_string = briefing_date.strftime("%Y-%m-%d")
        file_path = briefings_dir / date_string[:4] / date_string[:7] / f"{date_string}.json"
        if not file_path.exists():
            logger.info(f"  - No JSON file for {date_string}, would skip")
        else:
            logger.info(f"  [{date_string}] Would load from {file_path}")
    logger.info(f"Total: {len(requested_dates)} dates requested.")
    logger.info("Dry run complete.")


def _resolve_dates_to_load(
    conn: sqlite3.Connection,
    requested_dates: list[date],
    start_date: date,
    end_date: date,
    overwrite: bool,
) -> list[date]:
    """Filter requested_dates down to the ones that actually need loading.

    Args:
        conn (sqlite3.Connection): Open database connection.
        requested_dates (list[date]): All dates in the requested range.
        start_date (date): Start of the range (for existing-briefing lookup).
        end_date (date): End of the range (for existing-briefing lookup).
        overwrite (bool): If True, reload every requested date regardless of
            what's already in the database.

    Returns:
        list[date]: Dates that still need to be loaded.
    """
    if overwrite:
        return requested_dates
    existing_dates = _get_existing_briefing_dates(conn, start_date, end_date)
    return [d for d in requested_dates if d not in existing_dates]


def _load_dates(
    conn: sqlite3.Connection, dates_to_load: list[date], briefings_dir: Path = BRIEFINGS_DIR
) -> list[str]:
    """Load each date's briefing JSON into the database.

    Args:
        conn (sqlite3.Connection): Open database connection.
        dates_to_load (list[date]): Dates to attempt loading.
        briefings_dir (Path): Directory to search for JSON briefings.
            Defatuls to BRIEFINGS_DIR.

    Returns:
        list[str]: Date strings (YYYY-MM-DD) that failed to load.
    """
    failed_dates: list[str] = []

    for i, briefing_date in enumerate(dates_to_load):
        date_string = briefing_date.strftime("%Y-%m-%d")
        file_path = briefings_dir / date_string[:4] / date_string[:7] / f"{date_string}.json"

        if not file_path.exists():
            logger.info(f"  - No JSON file for {date_string}, skipping")
            continue

        logger.info(f"  [{i + 1}/{len(dates_to_load)}] {date_string} Loading...")
        success = load_briefing_to_db(file_path, conn)
        if not success:
            failed_dates.append(date_string)

    return failed_dates


def query_briefing_by_date(query_date: date, conn: sqlite3.Connection) -> None:
    """Query and display a briefing by date.

    Args:
        query_date (date): Date of the briefing to query.
        conn (sqlite3.Connection): Open database connection.
    """
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


def query_briefing_by_status(
    status: FetchStatus | Literal["all"], conn: sqlite3.Connection
) -> None:
    """Query and display briefings by status.

    Args:
        status (str): Status to filter briefings by, or "all" for all briefings.
        conn (sqlite3.Connection): Open database connection.
    """
    if status == "all":
        rows = conn.execute("SELECT briefing_date, url, status FROM briefing").fetchall()
    else:
        rows = conn.execute(
            """
            SELECT briefing_date, url, status FROM briefing
            WHERE status = ?
            """,
            (status,),
        ).fetchall()

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
    rows = conn.execute(
        """
        SELECT briefing_date FROM briefing
        WHERE briefing_date BETWEEN ? AND ?
        """,
        (start_date.isoformat(), end_date.isoformat()),
    ).fetchall()

    return {date.fromisoformat(row["briefing_date"]) for row in rows}


# --- streamlit app


def get_min_max_dates(
    conn: sqlite3.Connection, status: FetchStatus = "available"
) -> tuple[str, str] | tuple[None, None]:
    """Returns minimum and maximum dates present in the database with briefings.

    Args:
        conn (sqlite3.Connection): Connection to a database.
        status (FetchStatus, optional): Status of the briefing download. Defaults to "available".

    Returns:
        tuple[str, str] | tuple[None, None]: Min and max dates present in the database
    """
    query = """
        SELECT MIN(briefing_date), MAX(briefing_date)
        FROM briefing
        WHERE status = ?
    """
    min_date, max_date = conn.execute(query, (status,)).fetchone()

    return min_date, max_date


def get_dates_with_briefings(
    conn: sqlite3.Connection, status: FetchStatus = "available"
) -> list[str]:
    """Return a list with dates ['YYYY-MM-DD', ...] where there is a briefing
    on the status requested.

    Args:
        conn (sqlite3.Connection): Connection to a database.
        status (FetchStatus, optional): Status of the briefing download.
            Defaults to "available".

    Returns:
        list[str]: List with dates of the briefings in the database with the
            status requested.
    """
    query = (
        """SELECT DISTINCT briefing_date FROM briefing WHERE status = ? ORDER BY briefing_date"""
    )
    rows = conn.execute(query, (status,)).fetchall()

    briefing_dates = [x["briefing_date"] for x in rows]

    return briefing_dates


# --- section analysis ---------------------------------------------------------------


def insert_into_analysis_run(
    conn: sqlite3.Connection,
    analysis_name: str,
    model_name: str,
    model_version: str,
    ollama_version: None | str,
    prompt_version: str,
    prompt: str,
    temperature: float,
) -> int | None:
    """Create one sentiment/tone analysis run and return analysis_id.

    Args:
        conn (sqlite3.Connection): Database connection.
        analysis_name (str): Name of the analysis.
        model_name (str): LLM name.
        model_version (str): Version of the LLM.
        ollama_version (None | str): Ollama version.
        prompt_version (str): Version of the prompt used.
        prompt (str): Prompt used.
        temperature (float): Temperature between 0 and 1.

    Returns:
        int | None: Last row id from the `analysis_run` table or None.
    """

    cursor = conn.execute(
        """
        INSERT INTO analysis_run (
            analysis_name,
            model_name,
            model_version,
            ollama_version,
            prompt_version,
            prompt,
            temperature,
            created_at
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            analysis_name,
            model_name,
            model_version,
            ollama_version,
            prompt_version,
            prompt,
            temperature,
            datetime.now().isoformat(),
        ),
    )
    conn.commit()

    return int(cursor.lastrowid) if cursor.lastrowid is not None else None


def get_analysis_run(
    conn: sqlite3.Connection,
    analysis_id: int,
) -> sqlite3.Row:
    """Return metadata for one analysis run.

    Args:
        conn (sqlite3.Connection): Database connection.
        analysis_id (int): Analysis id.

    Returns:
        sqlite3.Row: The first row from query to the `analysis_run` table.
    """

    return conn.execute(
        """
        SELECT
            analysis_id,
            analysis_name,
            model_name,
            model_version,
            ollama_version,
            prompt_version,
            temperature,
            created_at
        FROM analysis_run
        WHERE analysis_id = ?
        """,
        (analysis_id,),
    ).fetchone()


def get_sections_for_sentiment_analysis(
    conn: sqlite3.Connection,
    start_date: str,
    end_date: str,
) -> pd.DataFrame:
    """Get the existing briefing sections that will be analysed.

        Data comes from the project's existing briefing and section tables.

        If start_date and end_date are provided, only sections belonging to
        briefings within that date range are returned.

    Args:
        conn (sqlite3.Connection): Database connection
        start_date (str): Start date to query sections for sentiment analysis.
        end_date (str): End date to query sections for sentiment analysis.

    Returns:
        pd.DataFrame: Data with non empty sections to apply sentiment analysis
            on them.
    """
    bounds = get_min_max_briefing_ids_from_dates(start_date, end_date)
    query = f"""
        SELECT 	s.section_id
                , s.briefing_id
                , b.briefing_date
                , s.section_order
                , s.title
                , s.text as section_text
        FROM briefing b INNER JOIN "section" s
                ON b.briefing_id = s.briefing_id
                AND b.briefing_id between {bounds[0]} and {bounds[1]}
        WHERE   s."text" is not null
                AND TRIM(s.text) != ''
        ORDER BY b.briefing_date, s.section_order;"""
    df = pd.read_sql(query, conn)

    if df.empty:
        return df

    df["briefing_date"] = pd.to_datetime(
        df["briefing_date"],
        errors="coerce",
    )

    return df.drop_duplicates(
        ["briefing_id", "section_id"],
        keep="first",
    ).reset_index(drop=True)


def get_completed_section_ids(
    conn: sqlite3.Connection,
    analysis_id: int,
) -> set[int]:
    """Return section IDs already successfully analysed for this analysis run.

    Args:
        conn (sqlite3.Connection): Database connection.
        analysis_id (int): Analysis id.

    Returns:
        set[int]: Set with successfully processed `section_id`s given an
            `analysis_id`.
    """

    rows = conn.execute(
        """
        SELECT section_id
        FROM sentiment_analysis
        WHERE analysis_id = ?
          AND status = 'success'
        """,
        (analysis_id,),
    ).fetchall()

    return {int(row["section_id"]) for row in rows}


def insert_sentiment_analysis(
    conn: sqlite3.Connection,
    analysis_id: int,
    briefing_id: int,
    section_id: int,
    briefing_date: str | None,
    sentiment: str | None,
    tone: str | None,
    status: str,
    error_message: str | None = None,
) -> None:
    """Store one sentiment/tone result.

    This matches the notebook's sentiment_analysis table:
        analysis_id
        briefing_id
        section_id
        briefing_date
        sentiment
        tone
        status
        error_message
        created_at

    Args:
        conn (sqlite3.Connection): Database connection.
        analysis_id (int): Analysis ID.
        briefing_id (int): Briefing ID.
        section_id (int): Section ID.
        briefing_date (str | None): Briefing date.
        sentiment (str | None): Sentiment from the analysis. It can be
            ["Positive", "Neutral", "Negative"]
        tone (str | None): Tone from the analysis. It can take the values of:
            "Diplomatic", "Concerned", "Critical", "Urgent", "Optimistic",
            "Neutral/Informational", or "Constructive".
        status (str): Status of the analysis. It can take the values of
            'success' or 'error'.
        error_message (str | None, optional): Error message in case the status
            is equal to 'error'. Defaults to None.
    """
    # Normalize briefing date for SQLite
    if briefing_date is not None:
        if isinstance(briefing_date, datetime):
            briefing_date = briefing_date.strftime("%Y-%m-%d")
    else:
        briefing_date = str(briefing_date)
    conn.execute(
        """
        INSERT INTO sentiment_analysis (
            analysis_id,
            briefing_id,
            section_id,
            briefing_date,
            sentiment,
            tone,
            status,
            error_message,
            created_at
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            analysis_id,
            briefing_id,
            section_id,
            briefing_date,
            sentiment,
            tone,
            status,
            error_message,
            datetime.now().isoformat(),
        ),
    )

    conn.commit()


def get_sentiment_results(
    conn: sqlite3.Connection,
    analysis_id: int,
) -> pd.DataFrame:
    """Return sentiment/tone results together with the original briefing and
    section information.

    Args:
        conn (sqlite3.Connection): Database connection.
        analysis_id (int): Analysis ID.

    Returns:
        pd.DataFrame: Data with the results of the sentiment analysis stored in
            the database.
    """

    query = """
        SELECT
            sa.analysis_result_id,
            sa.analysis_id,
            sa.briefing_id,
            sa.section_id,
            sa.briefing_date,
            s.section_order,
            s.title,
            s.text AS section_text,
            sa.sentiment,
            sa.tone,
            sa.status,
            sa.error_message,
            sa.created_at
        FROM sentiment_analysis AS sa
        JOIN section AS s
            ON sa.section_id = s.section_id
        WHERE sa.analysis_id = ?
        ORDER BY sa.briefing_date, s.section_order
    """

    return pd.read_sql_query(
        query,
        conn,
        params=(analysis_id,),
    )


def get_sentiment_distribution(
    conn: sqlite3.Connection,
    analysis_id: int,
) -> pd.DataFrame:
    """Return sentiment counts for one analysis run.

    Args:
        conn (sqlite3.Connection): Database connection.
        analysis_id (int): Sentiment analysis ID.

    Returns:
        pd.DataFrame: Frequency of the sentiments "Positive", "Neutral", and
            "Negative".
    """

    return pd.read_sql_query(
        """
        SELECT
            sentiment,
            COUNT(*) AS count
        FROM sentiment_analysis
        WHERE analysis_id = ?
          AND status = 'success'
        GROUP BY sentiment
        ORDER BY count DESC
        """,
        conn,
        params=(analysis_id,),
    )


def get_tone_distribution(
    conn: sqlite3.Connection,
    analysis_id: int,
) -> pd.DataFrame:
    """Return tone counts for one analysis run.

    Args:
        conn (sqlite3.Connection): Database connection._
        analysis_id (int): Sentiment analysis ID.

    Returns:
        pd.DataFrame: Frequency of the tones "Diplomatic", "Concerned",
            "Critical", "Urgent", "Optimistic", "Neutral/Informational", and
            "Constructive".
    """

    return pd.read_sql_query(
        """
        SELECT
            tone,
            COUNT(*) AS count
        FROM sentiment_analysis
        WHERE analysis_id = ?
          AND status = 'success'
        GROUP BY tone
        ORDER BY count DESC
        """,
        conn,
        params=(analysis_id,),
    )


# Get the latest analysis run for the given analysis name.
def get_latest_analysis_run(conn: sqlite3.Connection, analysis_name: str) -> sqlite3.Row | None:
    """Get the latest analysis run for the given analysis name.

    Args:
        conn (sqlite3.Connection): Database connection.
        analysis_name (str): Name of the analysis.

    Returns:
        sqlite3.Row | None: Sentiment analysis ID or None if it there no record
            for the given name of the analysis.
    """

    row = conn.execute(
        """
        SELECT analysis_id
        FROM analysis_run
        WHERE analysis_name = ?
        ORDER BY analysis_id DESC
        LIMIT 1
        """,
        (analysis_name,),
    ).fetchone()

    if row is None:
        return None

    return row[0]


# Get count of successfully analysed sections for an analysis run.
def count_successful_sections(conn: sqlite3.Connection, analysis_id: int) -> int:
    """Count successfully analysed sections for an analysis run.

    Args:
        conn (sqlite3.Connection): Database connection.
        analysis_id (int): Sentiment analysis ID.

    Returns:
        int: Number of sections successfully processed.
    """

    row = conn.execute(
        """
        SELECT COUNT(DISTINCT section_id)
        FROM sentiment_analysis
        WHERE analysis_id = ?
          AND status = 'success'
        """,
        (analysis_id,),
    ).fetchone()

    return row[0] if row else 0


def verify_sentiment_tables(
    conn: sqlite3.Connection,
) -> list[str]:  # pragma: no cover
    """Return the analysis tables currently present in the database.

    Args:
        conn (sqlite3.Connection): Database connection.

    Returns:
        list[str]: Names of the tables that exists in the database.
    """

    required = {
        "analysis_run",
        "sentiment_analysis",
    }

    rows = conn.execute("""
        SELECT name
        FROM sqlite_master
        WHERE type = 'table'
        """).fetchall()

    existing = {row["name"] for row in rows}

    return sorted(required.intersection(existing))


# --- country mentions


def get_country_mentions_by_date(
    conn: sqlite3.Connection, model: str, start_date: str, end_date: str
) -> pd.DataFrame:
    """Return country mentions in the sections filtering by date.

    Args:
        conn (sqlite3.Connection): Database connection.
        model (str): Model used.
        start_date (str): Start date in format 'YYYY-MM-DD'.
        end_date (str): End date in format 'YYYY-MM-DD'.

    Returns:
        pd.DataFrame: Data with country mentions.
    """
    start_briefing_id = pendulum.from_format(start_date, "YYYY-MM-DD").format("YYYYMMDD")
    end_briefing_id = pendulum.from_format(end_date, "YYYY-MM-DD").format("YYYYMMDD")

    query = f"""select briefing_id, section_id, country, iso_2, iso_3, model
                from country where model = '{model}'
                and briefing_id between {start_briefing_id} and {end_briefing_id};"""

    df_country = pd.read_sql(query, conn)

    df_country["date"] = df_country["briefing_id"].apply(
        lambda x: pendulum.from_format(str(x), "YYYYMMDD").format("YYYY-MM-DD")
    )
    df_country["week"] = df_country["briefing_id"].apply(
        lambda x: pendulum.from_format(str(x), "YYYYMMDD").start_of("week").format("YYYY-MM-DD")
    )
    df_country["month"] = df_country["briefing_id"].apply(
        lambda x: pendulum.from_format(str(x), "YYYYMMDD").start_of("month").format("YYYY-MM-DD")
    )
    df_country["year"] = df_country["briefing_id"].apply(
        lambda x: pendulum.from_format(str(x), "YYYYMMDD").start_of("year").format("YYYY-MM-DD")
    )
    return df_country


def get_countries_by_section_id(
    conn: sqlite3.Connection, section_id: int, model: str = "qwen3.5:4b"
) -> None | list[str]:
    """Return a list of countries given a section_id.

    Args:
        conn (sqlite3.Connection): Connection to the database.
        section_id (int): Section id in the database.
        model (str): Model used to extract SDGs from section.

    Returns:
        None | list[str]: List with countries or None.
    """
    rows = conn.execute(
        """select iso_2 from country where section_id = ? and model = ?;""",
        (section_id, model),
    ).fetchall()

    return [x[0] for x in rows]


def check_country_section_model_exists(
    conn: sqlite3.Connection, section_id: int, iso_2: str, model: str
) -> bool:
    """Check if there is data for that section_id, model and country.

    Args:
        conn (sqlite3.Connection): Database connection.
        section_id (int): Section id.
        iso_2 (str): ISO code of country.
        model (str): LLM.

    Returns:
        bool: Whether or not a record exists for that combination.
    """
    query_select = """SELECT briefing_id, section_id, country, iso_2, iso_3, model
                    FROM country
                    WHERE section_id = ?
                        AND iso_2 = ?
                        AND model = ?;"""
    rows = conn.execute(query_select, (section_id, iso_2, model)).fetchall()
    return bool(rows)


def _check_country_section_exists(conn: sqlite3.Connection, section_id: int, model: str) -> bool:
    """Check if a section has been processed already.

    Args:
        conn (sqlite3.Connection): Database connection.
        section_id (int): Section id.
        model (str): LLM.

    Returns:
        bool: Whether or not a record exists for that section_id and model.
    """
    query_select = """SELECT briefing_id, section_id, country, iso_2, iso_3, model
                    FROM country
                    WHERE section_id = ?
                        AND model = ?;"""
    rows = conn.execute(query_select, (section_id, model)).fetchall()
    return bool(rows)


def insert_into_country(
    conn: sqlite3.Connection,
    briefing_id: int,
    section_id: int,
    country: str,
    iso_2: str,
    iso_3: str,
    model: str,
    created_at: datetime,
):
    """Insert data into country table.

    Args:
        conn (sqlite3.Connection): Database connection.
        briefing_id (int): Briefing id.
        section_id (int): Section id.
        country (str): Country name.
        iso_2 (str): ISO 3166-1 Alpha-2 code.
        iso_3 (str): ISO 3166-1 Alpha-3 code.
        model (str): LLM used.
        created_at (datetime): Creation date.
    """
    query_insert = """INSERT INTO country
                (briefing_id, section_id, country, iso_2, iso_3, model, created_at)
                VALUES(?, ?, ?, ?, ?, ?, ?);"""
    query_delete = """DELETE FROM country WHERE section_id = ? AND iso_2 = ? AND model = ?"""

    with conn:
        cursor = conn.cursor()
        cursor.execute(query_delete, (section_id, iso_2, model))

        cursor.execute(
            query_insert, (briefing_id, section_id, country, iso_2, iso_3, model, created_at)
        )
        cursor.close()


def show_stats(conn: sqlite3.Connection) -> None:
    """Display database statistics.

    Prints total briefings count, date range, and count by status.
    """
    # Total count and date range
    total, min_date, max_date = conn.execute("""
        SELECT COUNT(*), MIN(briefing_date), MAX(briefing_date)
        FROM briefing
        """).fetchone()

    # Count by status
    status_counts = dict(conn.execute("SELECT status, COUNT(*) FROM briefing GROUP BY status"))

    logger.info("Database Statistics:")
    logger.info(f"  Total briefings: {total:,}")
    logger.info(f"  Date range: {min_date} to {max_date}")
    logger.info("  By status:")
    for status, count in status_counts.items():
        logger.info(f"    {status}: {count:,}")
