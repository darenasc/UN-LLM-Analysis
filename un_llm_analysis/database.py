import sqlite3

# Franz's schema.sql
SCHEMA = """
CREATE TABLE IF NOT EXISTS briefings (
    briefing_id INTEGER PRIMARY KEY,
    briefing_date DATE NOT NULL,
    url TEXT UNIQUE NOT NULL,
    briefing_text TEXT NOT NULL,
    download_date TIMESTAMP,
    processing_date TIMESTAMP,
    metadata TEXT
);

CREATE TABLE IF NOT EXISTS sections (
    section_id INTEGER PRIMARY KEY,
    briefing_id INTEGER NOT NULL,
    title TEXT NOT NULL,
    section_text TEXT NOT NULL,
    FOREIGN KEY (briefing_id)
        REFERENCES briefings(briefing_id)
        ON DELETE CASCADE
);
"""


def connect_db(db_path):
    """Connect to SQLite database with foreign keys enabled."""
    conn = sqlite3.connect(db_path)
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def create_database(db_path):
    """Create the database file and tables if they don't already exist."""
    with connect_db(db_path) as conn:
        conn.executescript(SCHEMA)


# --- briefings ---------------------------------------------------------

def insert_briefing(
    conn,
    briefing_date,
    url,
    briefing_text,
    download_date=None,
    processing_date=None,
    metadata=None,
):
    """Insert a briefing into the database."""
    cur = conn.execute(
        """
        INSERT INTO briefings (
            briefing_date,
            url,
            briefing_text,
            download_date,
            processing_date,
            metadata
        )
        VALUES (?, ?, ?, ?, ?, ?)
        """,
        (
            briefing_date,
            url,
            briefing_text,
            download_date,
            processing_date,
            metadata,
        ),
    )

    return cur.lastrowid


def get_briefing_by_id(conn, briefing_id):
    """Retrieve briefing by ID."""
    return conn.execute(
        """
        SELECT *
        FROM briefings
        WHERE briefing_id = ?
        """,
        (briefing_id,),
    ).fetchone()


def get_briefing_id_by_url(conn, url):
    """Get briefing ID by URL."""
    row = conn.execute(
        """
        SELECT briefing_id
        FROM briefings
        WHERE url = ?
        """,
        (url,),
    ).fetchone()

    if row is None:
        return None

    return row[0]


def delete_briefing(conn, briefing_id):
    """Delete briefing by ID. Returns True if deleted."""
    cur = conn.execute(
        """
        DELETE FROM briefings
        WHERE briefing_id = ?
        """,
        (briefing_id,),
    )

    return cur.rowcount > 0


# --- sections ----------------------------------------------------------

def insert_section(conn, briefing_id, title, section_text):
    """Insert a section into the database."""
    cur = conn.execute(
        """
        INSERT INTO sections (
            briefing_id,
            title,
            section_text
        )
        VALUES (?, ?, ?)
        """,
        (briefing_id, title, section_text),
    )

    return cur.lastrowid


def get_section(conn, section_id):
    """Retrieve section by ID."""
    return conn.execute(
        """
        SELECT *
        FROM sections
        WHERE section_id = ?
        """,
        (section_id,),
    ).fetchone()


def delete_section(conn, section_id):
    """Delete section by ID. Returns True if deleted."""
    cur = conn.execute(
        """
        DELETE FROM sections
        WHERE section_id = ?
        """,
        (section_id,),
    )

    return cur.rowcount > 0

if __name__ == "__main__":
    # test functions with mock data in memory
    conn = connect_db(":memory:")
    conn.executescript(SCHEMA)

    briefing_id = insert_briefing(
        conn,
        "2026-09-09",
        "https://example.com/briefing",
        "This is some mock briefing text."
    )

    print("Briefing ID:", briefing_id)

    briefing = get_briefing_by_id(conn, briefing_id)
    print("Briefing:", briefing)

    conn.close()