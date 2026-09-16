import ast
from datetime import datetime
from pathlib import Path
import sqlite3

from loguru import logger
import pandas as pd

from un_llm_analysis.config import BRIEFINGS_DB, SCHEMA_DB
from un_llm_analysis.extractor import ExtractedBriefing, ExtractedSection


def create_database(db_path: str | Path = BRIEFINGS_DB, schema_path: str | Path = SCHEMA_DB):
    """Create the database file and tables if they don't already exist.

    Args:
        db_path (str | Path): Path to the SQLite database file to create/open.
        schema_path (str | Path): Path to the SQL schema of the database.
    """
    with open(schema_path, "r", encoding="utf-8") as f:
        sql_schema = f.read()

    with get_db_connection(str(db_path)) as conn:
        conn.executescript(sql_schema)

        logger.info(f'Database created in "{db_path}"')


def get_db_connection(db_path: str | Path = str(BRIEFINGS_DB)) -> sqlite3.Connection:
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
        SELECT briefing_id, briefing_date, url, status, http_status, error, speaker_name, speaker_role, full_text, downloaded_at, processed_at
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
        SELECT briefing_id, briefing_date, url, status, http_status, error, speaker_name, speaker_role, full_text, downloaded_at, processed_at
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
        SELECT briefing_id, briefing_date, url, status, http_status, error, speaker_name, speaker_role, full_text, downloaded_at, processed_at
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


def get_briefing_id_by_url(conn: sqlite3.Connection, url: str) -> None | int:
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

    return row[0]


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
        briefing_id (int): ID of the parent briefing.
        sections (tuple[ExtractedSection, ...]): Sections from the briefing.
        db_path (str | Path): Path to find the database.
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
            section_exists = get_section(conn=conn, section_id=briefing_id * 100 + i)
            if section_exists:
                delete_section(conn=conn, section_id=briefing_id * 100 + i)
            insert_section(conn=conn, briefing_id=briefing_id, section=section, section_order=i)
    return briefing_id


def insert_section(
    conn: sqlite3.Connection,
    briefing_id: int,
    section: ExtractedSection,
    section_order: int,
):
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


def get_section(conn: sqlite3.Connection, section_id: int) -> ExtractedSection | None:
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


def delete_section(conn: sqlite3.Connection, section_id: int):
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


def delete_sections(conn: sqlite3.Connection, briefing_id: int):
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

    sql_query = """SELECT briefing_id, section_id, sdg, model, created_at FROM sdg WHERE briefing_id between ? AND ?;"""

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
