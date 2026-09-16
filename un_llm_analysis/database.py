import sqlite3
from sqlite3 import Connection, Row
from typing import Any

from un_llm_analysis.config import BRIEFINGS_DB, SCHEMA_DB

def connect_db(db_path: str) -> sqlite.Connection:
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


def create_database(db_path: str = str(BRIEFINGS_DB),
                    schema_path: str = str(SCHEMA_DB)) -> None:
    """Create the database file and tables if they don't already exist.

    Args:
        db_path (str): Path to the SQLite database file to create/open.
        schema_path (str): Path to the SQL schema of the database.
    """
    with open(schema_path, "r", encoding="utf-8") as f:
         sql_schema = f.read()

    with connect_db(db_path) as conn:
         conn.executescript(sql_schema)


# --- briefing ------------------------------------------------------------
def insert_briefing(
        conn: sqlite3.Connection,
        briefing_date: str,
        url: str,
        status: str,
        full_text: str,
        downloaded_at: str,
        processed_at: str,
        http_status: int | None = None,
        error: str | None = None,
        speaker_name: str | None = None,
        speaker_role: str | None = None,
) -> int:
    """Insert a briefing into the database, keyed on url.

    If a briefing with this url already exists, it is deleted first,
    then the new version is inserted.

    Args:
        conn (sqlite3.Connection): Open database connection.
        briefing_date (str): Briefing date, "YYYY-MM-DD".
        url (str): Source URL of the briefing (unique key).
        status (str): One of "available", "not_published", "failed".
        full_text (str): Full text of the briefing.
        downloaded_at (str): ISO timestamp of when it was downloaded.
        processed_at (str): ISO timestamp of when it was processed.
        http_status (int, optional): HTTP status code from the fetch.
        error (str, optional): Error message, if any.
        speaker_name (str, optional): Name of the briefing speaker.
        speaker_role (str, optional): Role/title of the speaker.

    Returns:
        int: The briefing_id of the inserted row.
    """
    existing = get_briefing_by_url(conn, url)
    if existing is not None:
        delete_briefing(conn, existing["briefing_id"])

    cur = conn.execute(
        """
        INSERT INTO briefing (
            briefing_date,
            url,
            status,
            http_status,
            error,
            speaker_name,
            speaker_role,
            full_text,
            downloaded_at,
            processed_at
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            briefing_date,
            url,
            status,
            http_status,
            error,
            speaker_name,
            speaker_role,
            full_text,
            downloaded_at,
            processed_at,
        ),
    )
    conn.commit()

    return cur.lastrowid


def get_briefing_by_id(conn, briefing_id):
    """Retrieve briefing by ID.

    Args:
        conn (sqlite3.Connection): Open database connection.
        briefing_id (int): Primary key of the briefing.

    Returns:
        sqlite3.Row | None: The matching row, or None if not found.
    """
    return conn.execute(
        """
        SELECT briefing_id, url, status, http_status, error, speaker_name, speaker_role, full_text, downloaded_at, processed_at
        FROM briefing
        WHERE briefing_id = ?
        """,
        (briefing_id,),
    ).fetchone()


def get_briefing_by_url(conn: sqlite3.Connection, url: str) -> sqlite3.Row | None:
    """Retrieve briefing by URL.

    Args:
        conn (sqlite3.Connection): Open database connection.
        url (str): URL of the briefing.

    Returns:
        sqlite3.Row | None: The matching row, or None if not found.
    """
    return conn.execute(
        """
        SELECT briefing_id, url, status, http_status, error, speaker_name, speaker_role, full_text, downloaded_at, processed_at
        FROM briefing
        WHERE url = ?
        """,
        (url,),
    ).fetchone()


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

def insert_section(conn: sqlite3.Connection, briefing_id: int, section_order: int, title: str, text: str) -> int:
    """Insert a section into the database.

    Args:
        conn (sqlite3.Connection): Open database connection.
        briefing_id (int): ID of the parent briefing.
        section_order (int): Position of the section within the briefing.
        title (str): Section title.
        text (str): Section body text.

    Returns:
        int: The section_id of the inserted row.
    """
    cur = conn.execute(
        """
        INSERT INTO section (
            briefing_id,
            section_order,
            title,
            text
        )
        VALUES (?, ?, ?, ?)
        """,
        (briefing_id, section_order, title, text),
    )

    conn.commit()
    return cur.lastrowid


def get_section_by_id(conn: sqlite3.Connection, section_id: int) -> sqlite3.Row | None:
    """Retrieve section by ID.

    Args:
        conn (sqlite3.Connection): Open database connection.
        section_id (int): Primary key of the section.

    Returns:
        sqlite3.Row | None: The matching row, or None if not found.
    """
    return conn.execute(
        """
        SELECT *
        FROM section
        WHERE section_id = ?
        """,
        (section_id,),
    ).fetchone()


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
    return cur.rowcount > 0

if __name__ == "__main__":
    # test functions with mock data in memory
    conn = connect_db(":memory:")
    conn.executescript(SCHEMA_DB)

    briefing_id = insert_briefing(
        conn,
        briefing_date="2026-09-09",
        url="https://example.com/briefing",
        status="available",
        full_text="This is some mock briefing text.",
        downloaded_at="2026-09-09T12:00:00+00:00",
        processed_at="2026-09-09T12:00:05+00:00",
    )

    print("Briefing ID:", briefing_id)

    briefing = get_briefing_by_id(conn, briefing_id)
    print("Briefing:", tuple(briefing))

    conn.close()