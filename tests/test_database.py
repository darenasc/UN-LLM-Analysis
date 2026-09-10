import sqlite3

import pytest

import database


@pytest.fixture
def conn():
    """In-memory database connection with the schema applied."""
    conn = database.connect_db(":memory:")
    conn.executescript(database.SCHEMA)
    yield conn
    conn.close()


def _insert_briefing(conn, **overrides):
    """Helper to insert a minimal valid briefing, with optional overrides."""
    kwargs = dict(
        briefing_date="2026-09-09",
        url="https://example.com/briefing",
        status="available",
        full_text="Some briefing text.",
        downloaded_at="2026-09-09T12:00:00+00:00",
        processed_at="2026-09-09T12:00:05+00:00",
    )
    kwargs.update(overrides)
    return database.insert_briefing(conn, **kwargs)


# --- schema / setup ---------------------------------------------------------

def test_create_database_creates_tables(tmp_path):
    """create_database should create a file with both tables present."""
    db_path = tmp_path / "test.db"
    database.create_database(str(db_path))

    conn = database.connect_db(str(db_path))
    tables = {
        row[0]
        for row in conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table'"
        ).fetchall()
    }
    conn.close()

    assert {"briefing", "section"} <= tables


def test_connect_db_enables_foreign_keys(conn):
    """connect_db should turn on foreign key enforcement."""
    assert conn.execute("PRAGMA foreign_keys").fetchone()[0] == 1


# --- briefing: insert / get -------------------------------------------------

def test_insert_and_get_briefing_by_id(conn):
    """Inserted briefing should be retrievable by its returned ID."""
    briefing_id = _insert_briefing(conn)
    row = database.get_briefing_by_id(conn, briefing_id)

    assert row is not None
    assert row[0] == briefing_id
    assert row[2] == "https://example.com/briefing"  # url
    assert row[3] == "available"  # status


def test_get_briefing_by_id_missing_returns_none(conn):
    """Non-existent ID should return None, not raise."""
    assert database.get_briefing_by_id(conn, 999) is None


def test_get_briefing_by_url(conn):
    """Briefing should be retrievable by its URL."""
    briefing_id = _insert_briefing(conn)
    row = database.get_briefing_by_url(conn, "https://example.com/briefing")

    assert row is not None
    assert row[0] == briefing_id


def test_get_briefing_id_by_url(conn):
    """get_briefing_id_by_url should return just the ID, or None."""
    briefing_id = _insert_briefing(conn)

    assert database.get_briefing_id_by_url(conn, "https://example.com/briefing") == briefing_id
    assert database.get_briefing_id_by_url(conn, "https://no-such.url") is None


def test_insert_briefing_optional_fields_default_none(conn):
    """http_status, error, speaker_name, speaker_role default to NULL."""
    briefing_id = _insert_briefing(conn)
    row = database.get_briefing_by_id(conn, briefing_id)

    # column order: id, date, url, status, http_status, error,
    # speaker_name, speaker_role, full_text, downloaded_at, processed_at
    assert row[4] is None  # http_status
    assert row[5] is None  # error
    assert row[6] is None  # speaker_name
    assert row[7] is None  # speaker_role


def test_insert_briefing_same_url_replaces_existing(conn):
    """Re-inserting a briefing with the same URL should replace, not duplicate."""
    _insert_briefing(conn, full_text="First version")
    _insert_briefing(conn, full_text="Second version")

    row = database.get_briefing_by_url(conn, "https://example.com/briefing")
    assert row is not None
    assert row["full_text"] == "Second version"

    count = conn.execute("SELECT COUNT(*) FROM briefing").fetchone()[0]
    assert count == 1


# --- briefing: constraints ---------------------------------------------------

def test_insert_briefing_invalid_status_raises(conn):
    """status must be one of the CHECK-constrained values."""
    with pytest.raises(sqlite3.IntegrityError):
        _insert_briefing(conn, status="bogus_status")


def test_insert_briefing_null_full_text_raises(conn):
    """full_text is NOT NULL in the schema."""
    with pytest.raises(sqlite3.IntegrityError):
        _insert_briefing(conn, full_text=None)


def test_insert_briefing_duplicate_date_raises(conn):
    """briefing_date is UNIQUE, independent of url."""
    _insert_briefing(conn, url="https://example.com/a")
    with pytest.raises(sqlite3.IntegrityError):
        _insert_briefing(conn, url="https://example.com/b")


# --- briefing: delete --------------------------------------------------------

def test_delete_briefing_returns_true_when_deleted(conn):
    """delete_briefing should return True and remove the row."""
    briefing_id = _insert_briefing(conn)
    assert database.delete_briefing(conn, briefing_id) is True
    assert database.get_briefing_by_id(conn, briefing_id) is None


def test_delete_briefing_returns_false_when_missing(conn):
    """delete_briefing should return False for a non-existent ID."""
    assert database.delete_briefing(conn, 999) is False


# --- section: insert / get / delete -----------------------------------------

def test_insert_and_get_section(conn):
    """Inserted section should be retrievable by its returned ID."""
    briefing_id = _insert_briefing(conn)
    section_id = database.insert_section(conn, briefing_id, 1, "Intro", "Some text.")

    row = database.get_section(conn, section_id)
    assert row is not None
    assert row[1] == briefing_id  # briefing_id
    assert row[2] == 1  # section_order
    assert row[3] == "Intro"  # title


def test_delete_section(conn):
    """delete_section should return True/False appropriately."""
    briefing_id = _insert_briefing(conn)
    section_id = database.insert_section(conn, briefing_id, 1, "Intro", "Some text.")

    assert database.delete_section(conn, section_id) is True
    assert database.get_section(conn, section_id) is None
    assert database.delete_section(conn, section_id) is False


# --- section: constraints ----------------------------------------------------

def test_insert_section_requires_valid_briefing_id(conn):
    """briefing_id must reference an existing briefing (FK enforced)."""
    with pytest.raises(sqlite3.IntegrityError):
        database.insert_section(conn, 999, 1, "Intro", "Some text.")


def test_insert_section_duplicate_order_raises(conn):
    """(briefing_id, section_order) must be unique."""
    briefing_id = _insert_briefing(conn)
    database.insert_section(conn, briefing_id, 1, "Intro", "Some text.")

    with pytest.raises(sqlite3.IntegrityError):
        database.insert_section(conn, briefing_id, 1, "Duplicate order", "Other text.")


def test_deleting_briefing_cascades_to_sections(conn):
    """ON DELETE CASCADE should remove sections when their briefing is deleted."""
    briefing_id = _insert_briefing(conn)
    section_id = database.insert_section(conn, briefing_id, 1, "Intro", "Some text.")

    database.delete_briefing(conn, briefing_id)

    assert database.get_section(conn, section_id) is None