"""UN database module for persisting and querying UN briefing data.
Provides access to five tables:

Tables:
    - `briefing`
    - `section`
    - `sdg`
    - `analysis_run`
    - `sentiment_analysis`

Supports inserting, updating, and deleting briefings, sections, SDG mappings,
analysis runs, and sentiment results via SQL or Python interfaces.
"""

import ast
from datetime import date, datetime
from pathlib import Path
import sqlite3

from loguru import logger
import pandas as pd

from un_llm_analysis.config import BRIEFINGS_DB_PATH, BRIEFINGS_DIR, SCHEMA_DB
from un_llm_analysis.extractor import (
    ExtractedBriefing,
    ExtractedSection,
    extract_briefing,
)
from un_llm_analysis.scraper import FetchStatus
from un_llm_analysis.utils import (
    _dates_between,
    _is_briefing_json_exists,
)


def create_database(db_path: str | Path = BRIEFINGS_DB_PATH, schema_path: str | Path = SCHEMA_DB):
    """Create the database file and tables if they don't already exist.

    Args:
        db_path (str | Path): Path to the SQLite database file to create/open.
        schema_path (str | Path): Path to the SQL schema of the database.
    """
    with open(schema_path, "r", encoding="utf-8") as f:
        sql_schema = f.read()

    conn = get_db_connection(str(db_path))
    try:
        conn.executescript(sql_schema)
        logger.info(f'Database created in "{db_path}"')
    finally:
        conn.close()


def get_db_connection(db_path: str | Path = str(BRIEFINGS_DB_PATH)) -> sqlite3.Connection:
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


def insert_into_briefing(
    conn: sqlite3.Connection,
    briefing: ExtractedBriefing,
) -> int:
    """Insert a briefing into the database.

    If a briefing with this url already exists, it is deleted first,
    then the new version is inserted.

    Args:
        conn (sqlite3.Connection): Database connection.
        briefing (ExtractedBriefing): Briefing object.

    Returns:
        int: `briefing_id` to confirm a successful insertion.
    """
    query_insert = """INSERT INTO briefing
            (briefing_id, briefing_date, url, status, http_status, error, speaker_name, speaker_role, full_text, downloaded_at, processed_at)
            VALUES(?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?);"""

    briefing_exists = get_briefing_by_id(
        conn=conn, briefing_id=get_briefing_id_from_date(briefing.briefing_date)
    )
    if briefing_exists is not None:
        delete_briefing(conn=conn, briefing_id=get_briefing_id_from_date(briefing.briefing_date))

    with conn:
        cursor = conn.cursor()
        cursor.execute(
            query_insert,
            (
                get_briefing_id_from_date(briefing.briefing_date),
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
        conn.commit()
        cursor.close()

        logger.info(f"Briefing from '{briefing.briefing_date}' inserted to the database.")
    return get_briefing_id_from_date(briefing.briefing_date)


def get_sections_by_briefing_id(
    conn: sqlite3.Connection, briefing_id: int
) -> tuple[ExtractedSection, ...]:
    """Return a tuple with the sections from the database corresponding the
    briefing_id.

    Args:
        conn (sqlite3.Connection): Database connection.
        briefing_id (int): Briefing id.

    Returns:
        tuple[ExtractedSection, ...]: Sections stored in the database
            associated to the briefing.
    """
    cursor = conn.cursor()
    cursor.execute(
        """
        SELECT section_id, briefing_id, section_order, title, "text"
        FROM section
        WHERE briefing_id = ?
        ORDER BY section_id
        """,
        (briefing_id,),
    )
    rows = cursor.fetchall()
    sections = []
    for row in rows:
        sections.append(ExtractedSection(title=row["title"], text=row["text"]))

    return tuple(sections)


def get_briefing_by_id(conn: sqlite3.Connection, briefing_id: int) -> ExtractedBriefing | None:
    """Retrieve briefing by ID.

    Args:
        conn (sqlite3.Connection): Open database connection.
        briefing_id (int): Primary key of the briefing.

    Returns:
        ExtractedBriefing | None: The briefing data from the database given a
            briefing_id, or None if not found.
    """
    cursor = conn.cursor()
    cursor.execute(
        """
        SELECT briefing_id, briefing_date, url, status, http_status, error,
            speaker_name, speaker_role, full_text, downloaded_at, processed_at
        FROM briefing
        WHERE briefing_id = ?
        """,
        (briefing_id,),
    )
    row = cursor.fetchone()
    cursor.close()

    if row:
        briefing = ExtractedBriefing(
            briefing_date=row["briefing_date"],
            url=row["url"],
            status=row["status"],
            http_status=row["http_status"],
            error=row["error"],
            downloaded_at=row["downloaded_at"],
            speaker_name=row["speaker_name"],
            speaker_role=row["speaker_role"],
            sections=get_sections_by_briefing_id(conn=conn, briefing_id=briefing_id),
            full_text=row["full_text"],
        )
        return briefing
    else:
        return None


def get_briefing_by_url(conn: sqlite3.Connection, url: str) -> ExtractedBriefing | None:
    """Retrieve briefing by URL.

    Args:
        conn (sqlite3.Connection): Open database connection.
        url (str): URL of the briefing.

    Returns:
        sqlite3.Row | None: The matching row, or None if not found.
    """
    cursor = conn.cursor()
    cursor.execute(
        """
        SELECT briefing_id, briefing_date, url, status, http_status, error,
            speaker_name, speaker_role, full_text, downloaded_at, processed_at
        FROM briefing
        WHERE url = ?
        """,
        (url,),
    )
    row = cursor.fetchone()
    if row:
        briefing = ExtractedBriefing(
            briefing_date=row["briefing_date"],
            url=row["url"],
            status=row["status"],
            http_status=row["http_status"],
            error=row["error"],
            downloaded_at=row["downloaded_at"],
            speaker_name=row["speaker_name"],
            speaker_role=row["speaker_role"],
            sections=get_sections_by_briefing_id(
                conn=conn, briefing_id=get_briefing_id_from_date(row["briefing_date"])
            ),
            full_text=row["full_text"],
        )
        return briefing
    else:
        return None


def get_briefing_by_date(conn: sqlite3.Connection, date: str) -> ExtractedBriefing | None:
    """Retrieve briefing by date.

    Args:
        conn (sqlite3.Connection): Open database connection.
        date (str): Date of the briefing.

    Returns:
        sqlite3.Row | None: The matching row, or None if not found.
    """
    briefing_id = get_briefing_id_from_date(date=date)
    briefing = get_briefing_by_id(conn=conn, briefing_id=briefing_id)
    return briefing


def get_briefings_between_dates(
    conn: sqlite3.Connection, start_date: str, end_date: str
) -> list[ExtractedBriefing] | None:
    """Retrieve briefings between two dates.

    Args:
        conn (sqlite3.Connection): Database connection.
        start_date (str): Start date with format 'YYYY-MM-DD'.
        end_date (str): End date with format 'YYYY-MM-DD'.

    Returns:
        list[ExtractedBriefing] | None: List with requested that are in the
            database briefings or None.
    """
    min_date = min(get_briefing_id_from_date(start_date), get_briefing_id_from_date(end_date))
    max_date = max(get_briefing_id_from_date(start_date), get_briefing_id_from_date(end_date))

    cursor = conn.cursor()
    cursor.execute(
        """
        SELECT briefing_id, briefing_date, url, status, http_status, error,
            speaker_name, speaker_role, full_text, downloaded_at, processed_at
        FROM briefing
        WHERE briefing_id between ? and ?;
        """,
        (
            min_date,
            max_date,
        ),
    )
    rows = cursor.fetchall()
    cursor.close()

    if rows:
        briefings = []
        for row in rows:
            briefing = ExtractedBriefing(
                briefing_date=row["briefing_date"],
                url=row["url"],
                status=row["status"],
                http_status=row["http_status"],
                error=row["error"],
                downloaded_at=row["downloaded_at"],
                speaker_name=row["speaker_name"],
                speaker_role=row["speaker_role"],
                sections=get_sections_by_briefing_id(conn=conn, briefing_id=row["briefing_id"]),
                full_text=row["full_text"],
            )
            briefings.append(briefing)
        return briefings
    else:
        return None


def get_briefing_id_by_url(conn: sqlite3.Connection, url: str) -> int | None:
    """Get briefing ID by URL.

    Args:
        conn (sqlite3.Connection): Open database connection.
        url (str): URL of the briefing.

    Returns:
        int | None: The briefing_id, or None if no match.
    """
    row = conn.execute(
        """
        SELECT briefing_id
        FROM briefing
        WHERE url = ?
        """,
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
    cur = conn.execute(
        """
        DELETE FROM briefing
        WHERE briefing_id = ?
        """,
        (briefing_id,),
    )

    conn.commit()
    return cur.rowcount > 0


# --- section ---------------------------------------------------------------


def insert_into_section(
    conn: sqlite3.Connection,
    briefing_id: int,
    sections: tuple[ExtractedSection, ...],
    insert_all: bool = True,
) -> int:
    """Insert a section into the database.

    Args:
        conn (sqlite3.Connection): Open database connection.
        briefing_id (int): ID of the parent briefing.
        sections (tuple[ExtractedSection, ...]): Sections from the briefing.
        insert_all (bool): Whether or not to insert all the sections at once or
            one by one. Default to True.
    """
    query_insert = """INSERT INTO "section"
                    (section_id, briefing_id, section_order, title, "text")
                    VALUES(?, ?, ?, ?, ?);"""

    # conn = get_db_connection(db_path=db_path)
    if insert_all:
        delete_sections(conn=conn, briefing_id=briefing_id)

        data = []
        for i, section in enumerate(sections, start=1):
            data.append((briefing_id * 100 + i, briefing_id, i, section.title, section.text))

        with conn:
            cursor = conn.cursor()
            cursor.executemany(query_insert, data)
            conn.commit()
            cursor.close()
    else:
        for i, section in enumerate(sections, start=1):
            section_exists = get_section_by_section_id(conn=conn, section_id=briefing_id * 100 + i)
            if section_exists:
                delete_section(conn=conn, section_id=briefing_id * 100 + i)
            insert_section(conn=conn, briefing_id=briefing_id, section=section, section_order=i)
    return briefing_id


def insert_section(
    conn: sqlite3.Connection,
    briefing_id: int,
    section: ExtractedSection,
    section_order: int,
) -> int:
    """Insert a section into the database.

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
    cursor = conn.cursor()
    cursor.execute(
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
    conn.commit()
    cursor.close()

    return section_id


# TODO: rename to get_section_by_id and apply to tests too.
def get_section_by_section_id(
    conn: sqlite3.Connection, section_id: int
) -> ExtractedSection | None:
    """Retrieve section by ID.

    Args:
        conn (sqlite3.Connection): Open database connection.
        section_id (int): Primary key of the section.

    Returns:
        sqlite3.Row | None: The matching row, or None if not found.
    """
    cursor = conn.cursor()
    cursor.execute(
        """
            SELECT section_id, title, "text"
            FROM section
            WHERE section_id = ?
            """,
        (section_id,),
    )
    rows = cursor.fetchone()
    return ExtractedSection(rows["title"], rows["text"]) if rows else None


def delete_section(conn: sqlite3.Connection, section_id: int) -> bool:
    """Delete section by ID.

    Args:
        conn (sqlite3.Connection): Open database connection.
        section_id (int): Primary key of the section to delete.

    Returns:
        bool: True if a row was deleted, False otherwise.
    """
    cur = conn.execute(
        """
        DELETE FROM section
        WHERE section_id = ?
        """,
        (section_id,),
    )

    conn.commit()

    logger.info(f"Deleted section '{section_id}'")

    return cur.rowcount > 0


def delete_sections(conn: sqlite3.Connection, briefing_id: int) -> bool:
    """Delete all sections with the same briefing_id.

    Args:
        conn (sqlite3.Connection): Open database connection.
        briefing_id (int): Briefing key of the sections to delete.

    Returns:
        bool: True if a row was deleted, False otherwise.
    """
    cur = conn.execute(
        """
        DELETE FROM section
        WHERE briefing_id = ?
        """,
        (briefing_id,),
    )

    conn.commit()

    logger.info(f"Deleted the sections of briefing '{briefing_id}'")
    return cur.rowcount > 0


# --- sdg -------------------------------------------------------------------


def insert_into_sdg(
    conn: sqlite3.Connection,
    briefing_id: int,
    section_id: int,
    sdgs: str,
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
    parsed_sdgs = ast.literal_eval(sdgs)
    if parsed_sdgs is None:
        return
    sql_insert = """INSERT INTO sdg
                    (briefing_id, section_id, sdg, model, created_at)
                    VALUES(?, ?, ?, ?, ?);"""
    with conn:
        delete_from_sdg(conn=conn, section_id=section_id, model=model, verbose=verbose)

        cursor = conn.cursor()
        for sdg in parsed_sdgs:
            cursor.execute(sql_insert, (briefing_id, section_id, sdg, model, created_at))
        conn.commit()

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
    query_delete = """DELETE FROM sdg WHERE section_id = ? AND model = ?"""
    with conn:
        cursor = conn.cursor()
        cursor.execute(
            query_delete,
            (
                section_id,
                model,
            ),
        )
        conn.commit()
        was_deleted = cursor.rowcount > 1
        cursor.close()

    if verbose:
        logger.info(f"Deleted sdg section'{section_id}' of model '{model}'")
    return was_deleted


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
    min_date = min(get_briefing_id_from_date(start_date), get_briefing_id_from_date(end_date))
    max_date = max(get_briefing_id_from_date(start_date), get_briefing_id_from_date(end_date))

    sql_query = """SELECT briefing_id, section_id, sdg, model, created_at
                    FROM sdg WHERE briefing_id between ? AND ?;"""

    with conn:
        cursor = conn.cursor()
        cursor.execute(
            sql_query,
            (
                min_date,
                max_date,
            ),
        )
        rows = cursor.fetchall()
        column_names = [x[0] for x in cursor.description]
        cursor.close()
    if rows:
        df = pd.DataFrame(rows, columns=column_names)
        return df
    else:
        return pd.DataFrame()


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


def load_briefings_between_dates(
    start_date: date,
    end_date: date,
    overwrite: bool = False,
    dry_run: bool = False,
    conn: sqlite3.Connection | None = None,
) -> bool:
    """Load briefings from JSON files into database for a date range.

    Args:
        start_date (date): The date to start loading from.
        end_date (date): The date to end loading at.
        overwrite (bool): Whether to overwrite existing briefings. Defaults to
            False.
        dry_run (bool): If True, preview what would be loaded without actually
            loading. Defaults to False.
        conn (sqlite3.Connection | None): Existing connection to reuse. If None,
            a new connection is opened and closed automatically.

    Returns:
        bool: True if every loaded briefing succeeded (or nothing needed loading),
            False if at least one briefing failed to load.
    """
    requested_dates = list(_dates_between(start_date, end_date))

    if dry_run:
        _log_dry_run(requested_dates)
        return True

    if conn is None:
        conn = get_db_connection()

    try:
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

        failed_dates = _load_dates(conn=conn, dates_to_load=dates_to_load)
    finally:
        conn.close()

    if failed_dates:
        logger.info(
            f"Load complete with {len(failed_dates)} failure(s): {', '.join(failed_dates)}"
        )
        return False

    logger.info("Load complete.")
    return True


def _log_dry_run(requested_dates: list[date]) -> None:
    """Log a preview of what load_between_dates would do, without loading anything."""
    logger.info("DRY RUN - No changes will be made:")
    for briefing_date in requested_dates:
        date_string = briefing_date.strftime("%Y-%m-%d")
        file_path = BRIEFINGS_DIR / date_string[:4] / date_string[:7] / f"{date_string}.json"
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


def _load_dates(conn: sqlite3.Connection, dates_to_load: list[date]) -> list[str]:
    """Load each date's briefing JSON into the database.

    Args:
        conn (sqlite3.Connection): Open database connection.
        dates_to_load (list[date]): Dates to attempt loading.

    Returns:
        list[str]: Date strings (YYYY-MM-DD) that failed to load.
    """
    failed_dates: list[str] = []

    for i, briefing_date in enumerate(dates_to_load):
        date_string = briefing_date.strftime("%Y-%m-%d")
        file_path = BRIEFINGS_DIR / date_string[:4] / date_string[:7] / f"{date_string}.json"

        if not file_path.exists():
            logger.info(f"  - No JSON file for {date_string}, skipping")
            continue

        logger.info(f"  [{i + 1}/{len(dates_to_load)}] {date_string} Loading...")
        success = load_briefing_to_db(file_path, conn)
        if not success:
            failed_dates.append(date_string)

    return failed_dates


def query_by_date(query_date: date, conn: sqlite3.Connection | None = None) -> None:
    """Query and display a briefing by date.

    Args:
        query_date (date): Date of the briefing to query.
    """
    conn = conn or get_db_connection()
    with conn:
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


def query_by_status(status: FetchStatus, conn: sqlite3.Connection | None = None) -> None:
    """Query and display briefings by status.

    Args:
        status (str): Status to filter briefings by, or "all" for all briefings.
    """
    conn = conn or get_db_connection()
    with conn:
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


# --- streamlit app


def get_min_max_dates(
    conn: sqlite3.Connection, status: FetchStatus = "available"
) -> tuple[str, str] | tuple[None, None]:
    """Returns minimum and maximum dates present in the database with briefings.

    Args:
        conn (sqlite3.Connection): Connection to a database.
        status (FetchStatus, optional): Status of the briefing download.
            Defaults to "available".

    Returns:
        tuple[str, str]: Min and max dates present in the database
    """
    query = """select min(b.briefing_id) as min_briefing_id
                , max(b.briefing_id) as max_briefing_id
                from briefing b
                where b.status = ?;"""
    with conn:
        cursor = conn.cursor()
        cursor.execute(query, (status,))
        row = cursor.fetchall()
        cursor.close()
        if row:
            min_briefing_id, max_briefing_id = row[0]
            return datetime.strptime(str(min_briefing_id), "%Y%m%d").strftime(
                "%Y-%m-%d"
            ), datetime.strptime(str(max_briefing_id), "%Y%m%d").strftime("%Y-%m-%d")
        else:
            return None, None


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
    query = """select distinct b.briefing_id from briefing b where b.status = ?;"""
    briefing_dates = []
    with conn:
        cursor = conn.cursor()
        cursor.execute(query, (status,))
        rows = cursor.fetchall()
        cursor.close()

    briefing_dates = [datetime.strptime(str(x[0]), "%Y%m%d").strftime("%Y-%m-%d") for x in rows]
    return briefing_dates


def show_stats(conn: sqlite3.Connection | None = None) -> None:
    """Display database statistics.

    Prints total briefings count, date range, and count by status.
    """
    if conn is None:
        conn = get_db_connection()
    with conn:
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
    logger.info(f"  Total briefings: {total:,}")
    logger.info(f"  Date range: {date_range['min_date']} to {date_range['max_date']}")
    logger.info("  By status:")
    for status, count in status_counts.items():
        logger.info(f"    {status}: {count:,}")
