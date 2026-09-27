import ast
from datetime import datetime
from pathlib import Path
import sqlite3

from loguru import logger
import pandas as pd

from un_llm_analysis.config import BRIEFINGS_DB_PATH, SCHEMA_DB
from un_llm_analysis.extractor import ExtractedBriefing, ExtractedSection
from un_llm_analysis.scraper import FetchStatus


def create_database(db_path: str | Path = BRIEFINGS_DB_PATH, schema_path: str | Path = SCHEMA_DB):
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
    query = """select min(b.briefing_id) as min_briefing_id, max(b.briefing_id) as max_briefing_id from briefing b where b.status = ?;"""
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
# --- section analysis ---------------------------------------------------------------


def insert_into_analysisrun(
    conn: sqlite3.Connection,
    analysis_name: str,
    model_name: str,
    model_version: str,
    ollama_version: None | str,
    prompt_version: str,
    prompt: str,
    temperature: float,
) -> int:
    """Create one sentiment/tone analysis run and return analysis_id."""

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

    return int(cursor.lastrowid)


def get_analysis_run(
    conn: sqlite3.Connection,
    analysis_id: int,
):
    """Return metadata for one analysis run."""

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
) -> pd.DataFrame:
    """
    Get the existing briefing sections that will be analysed.

    Data comes from the project's existing briefing and section tables.
    """

    query = """
        SELECT
            s.section_id,
            s.briefing_id,
            b.briefing_date,
            s.section_order,
            s.title,
            s.text AS section_text
        FROM section AS s
        JOIN briefing AS b
            ON s.briefing_id = b.briefing_id
        WHERE s.text IS NOT NULL
          AND TRIM(s.text) != ''
        ORDER BY b.briefing_date, s.section_order
    """

    cursor = conn.execute(query)
    rows = cursor.fetchall()
    column_names = [column[0] for column in cursor.description]
    cursor.close()

    df = pd.DataFrame(rows, columns=column_names)

    if df.empty:
        return df

    df["briefing_date"] = pd.to_datetime(
        df["briefing_date"],
        errors="coerce",
    )

    return (
        df.drop_duplicates(
            ["briefing_id", "section_id"],
            keep="first",
        )
        .reset_index(drop=True)
    )


def get_completed_section_ids(
    conn: sqlite3.Connection,
    analysis_id: int,
) -> set[int]:
    """
    Return section IDs already successfully analysed
    for this analysis run.
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
    """
    Store one sentiment/tone result.

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
    """
    # Normalize briefing date for SQLite
    if briefing_date is not None:
        if hasattr(briefing_date, "strftime"):
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
    """
    Return sentiment/tone results together with the original
    briefing and section information.
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
    """Return sentiment counts for one analysis run."""

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
    """Return tone counts for one analysis run."""

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
def get_latest_analysis_run(conn, analysis_name):
    """
    Get the latest analysis run for the given analysis name.
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
def count_successful_sections(conn, analysis_id):
    """
    Count successfully analysed sections for an analysis run.
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
) -> list[str]:
    """Return the analysis tables currently present in the database."""

    required = {
        "analysis_run",
        "sentiment_analysis",
    }

    rows = conn.execute(
        """
        SELECT name
        FROM sqlite_master
        WHERE type = 'table'
        """
    ).fetchall()

    existing = {row["name"] for row in rows}

    return sorted(required.intersection(existing))

if __name__ == "__main__":
    # Run this file directly only to create/verify the two
    # sentiment-analysis tables in the existing project database.
    conn = sqlite3.connect(BRIEFINGS_DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")

    create_sentiment_tables(conn)

    print("Sentiment/tone database tables are ready.")
    print("Database:", BRIEFINGS_DB_PATH)
    print("Tables:", verify_sentiment_tables(conn))

    conn.close()