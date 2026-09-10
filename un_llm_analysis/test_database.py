"""Unit tests for db.py.

Run with: pytest test_db.py -v
"""

import json
import sqlite3

import pytest

from un_llm_analysis import database as db

# --- fixtures --------------------------------------------------------------

@pytest.fixture
def conn():
    """Fresh in-memory database for each test."""
    c = db.connect_db(":memory:")
    c.executescript(db.SCHEMA)
    yield c
    c.close()


@pytest.fixture
def briefing_id(conn):
    """A briefing already inserted, for tests that need one to exist."""
    return db.insert_briefing(
        conn, "2026-09-09", "https://example.com/b1", "Some briefing text."
    )


# --- schema / connection ----------------------------------------------------

def test_create_database_creates_tables(tmp_path):
    db_path = tmp_path / "test.db"
    db.create_database(db_path)

    c = sqlite3.connect(db_path)
    tables = {
        row[0] for row in c.execute(
            "SELECT name FROM sqlite_master WHERE type='table'"
        ).fetchall()
    }
    c.close()
    assert {"briefings", "sections"}.issubset(tables)


def test_foreign_keys_enabled(conn):
    assert conn.execute("PRAGMA foreign_keys").fetchone()[0] == 1


# --- briefings: insert / get / update / delete ------------------------------

def test_insert_and_get_briefing(conn):
    bid = db.insert_briefing(conn, "2026-09-09", "https://example.com/x", "text")
    row = db.get_briefing_by_id(conn, bid)
    assert row["briefing_date"] == "2026-09-09"
    assert row["url"] == "https://example.com/x"
    assert row["briefing_text"] == "text"


def test_insert_briefing_duplicate_url_replaces_row(conn):
    bid1 = db.insert_briefing(conn, "2026-09-09", "https://example.com/x", "first")
    bid2 = db.insert_briefing(conn, "2026-09-09", "https://example.com/x", "second")

    # old row is gone; url now points at the new content
    row = db.get_briefing_by_id(conn, bid2)
    assert row["briefing_text"] == "second"
    if bid1 != bid2:
        assert db.get_briefing_by_id(conn, bid1) is None


def test_insert_briefing_missing_url_raises(conn):
    with pytest.raises(sqlite3.IntegrityError):
        conn.execute(
            "INSERT INTO briefings (briefing_date, url, briefing_text) "
            "VALUES ('2026-09-09', NULL, 'text')"
        )


def test_update_briefing_single_field(conn, briefing_id):
    updated = db.update_briefing(conn, briefing_id, processing_date="2026-09-10T00:00:00Z")
    assert updated is True
    row = db.get_briefing_by_id(conn, briefing_id)
    assert row["processing_date"] == "2026-09-10T00:00:00Z"


def test_update_briefing_multiple_fields(conn, briefing_id):
    db.update_briefing(conn, briefing_id, briefing_text="new text", metadata='{"a": 1}')
    row = db.get_briefing_by_id(conn, briefing_id)
    assert row["briefing_text"] == "new text"
    assert row["metadata"] == '{"a": 1}'


def test_update_briefing_unknown_field_raises(conn, briefing_id):
    with pytest.raises(ValueError):
        db.update_briefing(conn, briefing_id, not_a_real_column="x")


def test_update_briefing_no_fields_raises(conn, briefing_id):
    with pytest.raises(ValueError):
        db.update_briefing(conn, briefing_id)


def test_update_briefing_nonexistent_id_returns_false(conn):
    assert db.update_briefing(conn, 9999, briefing_text="x") is False


def test_delete_briefing(conn, briefing_id):
    assert db.delete_briefing(conn, briefing_id) is True
    assert db.get_briefing_by_id(conn, briefing_id) is None


def test_delete_briefing_nonexistent_returns_false(conn):
    assert db.delete_briefing(conn, 9999) is False


def test_delete_briefing_cascades_to_sections(conn, briefing_id):
    db.insert_section(conn, briefing_id, "Topic", "text")
    db.delete_briefing(conn, briefing_id)
    remaining = db.get_sections_by_briefing_id(conn, briefing_id)
    assert remaining == []


# --- sections: insert / get / update / delete -------------------------------

def test_insert_and_get_section(conn, briefing_id):
    sid = db.insert_section(conn, briefing_id, "Middle East", "Some section text.")
    row = db.get_section(conn, sid)
    assert row["briefing_id"] == briefing_id
    assert row["title"] == "Middle East"
    assert row["section_text"] == "Some section text."


def test_insert_section_duplicate_key_replaces_row(conn, briefing_id):
    sid1 = db.insert_section(conn, briefing_id, "Intro", "v1")
    sid2 = db.insert_section(conn, briefing_id, "Intro", "v2")

    row = db.get_section(conn, sid2)
    assert row["section_text"] == "v2"
    if sid1 != sid2:
        assert db.get_section(conn, sid1) is None


def test_insert_section_invalid_briefing_id_raises(conn):
    with pytest.raises(sqlite3.IntegrityError):
        db.insert_section(conn, 9999, "Title", "text")


def test_get_sections_by_briefing_id_order(conn, briefing_id):
    db.insert_section(conn, briefing_id, "First", "a")
    db.insert_section(conn, briefing_id, "Second", "b")
    rows = db.get_sections_by_briefing_id(conn, briefing_id)
    assert [r["title"] for r in rows] == ["First", "Second"]


def test_update_section(conn, briefing_id):
    sid = db.insert_section(conn, briefing_id, "Title", "old text")
    updated = db.update_section(conn, sid, section_text="new text")
    assert updated is True
    assert db.get_section(conn, sid)["section_text"] == "new text"


def test_update_section_unknown_field_raises(conn, briefing_id):
    sid = db.insert_section(conn, briefing_id, "Title", "text")
    with pytest.raises(ValueError):
        db.update_section(conn, sid, not_a_column="x")


def test_delete_section(conn, briefing_id):
    sid = db.insert_section(conn, briefing_id, "Title", "text")
    assert db.delete_section(conn, sid) is True
    assert db.get_section(conn, sid) is None


def test_delete_section_nonexistent_returns_false(conn):
    assert db.delete_section(conn, 9999) is False


# --- bulk loading ------------------------------------------------------------

def _write_briefing_json(path, date_str, status="available", html="<p>text</p>"):
    path.write_text(json.dumps({
        "date": date_str,
        "url": f"https://example.com/{date_str}.html",
        "status": status,
        "http_status": 200 if status == "available" else 404,
        "html": html,
        "error": None,
        "downloaded_at": f"{date_str}T12:00:00+00:00",
    }))


def test_bulk_load_inserts_available_briefings(conn, tmp_path):
    _write_briefing_json(tmp_path / "2026-01-01.json", "2026-01-01")
    _write_briefing_json(tmp_path / "2026-01-02.json", "2026-01-02")

    result = db.bulk_load_briefings(conn, tmp_path)

    assert result == {"inserted": 2, "skipped": 0, "errors": 0}
    count = conn.execute("SELECT COUNT(*) FROM briefings").fetchone()[0]
    assert count == 2


def test_bulk_load_skips_not_published(conn, tmp_path):
    _write_briefing_json(tmp_path / "2026-01-01.json", "2026-01-01", status="not_published", html=None)
    _write_briefing_json(tmp_path / "2026-01-02.json", "2026-01-02")

    result = db.bulk_load_briefings(conn, tmp_path)

    assert result == {"inserted": 1, "skipped": 1, "errors": 0}


def test_bulk_load_handles_malformed_json(conn, tmp_path):
    (tmp_path / "bad.json").write_text("{not valid json")
    _write_briefing_json(tmp_path / "2026-01-01.json", "2026-01-01")

    result = db.bulk_load_briefings(conn, tmp_path)

    assert result == {"inserted": 1, "skipped": 0, "errors": 1}


def test_bulk_load_rerun_replaces_existing(conn, tmp_path):
    path = tmp_path / "2026-01-01.json"
    _write_briefing_json(path, "2026-01-01", html="<p>version 1</p>")
    db.bulk_load_briefings(conn, tmp_path)

    _write_briefing_json(path, "2026-01-01", html="<p>version 2</p>")
    db.bulk_load_briefings(conn, tmp_path)

    count = conn.execute("SELECT COUNT(*) FROM briefings").fetchone()[0]
    assert count == 1
    row = conn.execute("SELECT briefing_text FROM briefings").fetchone()
    assert "version 2" in row[0]


def test_bulk_load_scans_nested_directories(conn, tmp_path):
    nested = tmp_path / "2026" / "2026-01"
    nested.mkdir(parents=True)
    _write_briefing_json(nested / "2026-01-01.json", "2026-01-01")

    result = db.bulk_load_briefings(conn, tmp_path)
    assert result["inserted"] == 1


# --- section splitting preprocessing ----------------------------------------

SAMPLE_HTML = """
<p>Good afternoon.</p>
<p><strong>Ukraine</strong></p>
<p>The Secretary-General condemned the attacks.</p>
<p>Humanitarian access remains a concern.</p>
<p><strong>Middle East</strong></p>
<p>The situation remains tense in Gaza.</p>
"""


def test_split_into_sections_basic():
    sections = db.split_into_sections(SAMPLE_HTML)
    titles = [title for title, _ in sections]
    assert titles == ["Ukraine", "Middle East"]


def test_split_into_sections_groups_text_under_correct_header():
    sections = db.split_into_sections(SAMPLE_HTML)
    ukraine_text = dict(sections)["Ukraine"]
    assert "condemned the attacks" in ukraine_text
    assert "Humanitarian access" in ukraine_text
    assert "Gaza" not in ukraine_text


def test_split_into_sections_no_headers_returns_empty():
    html = "<p>Just some plain text with no bold headers at all.</p>"
    assert db.split_into_sections(html) == []


def test_split_into_sections_ignores_leading_intro_text():
    sections = db.split_into_sections(SAMPLE_HTML)
    all_text = " ".join(text for _, text in sections)
    assert "Good afternoon" not in all_text


def test_process_briefing_sections_inserts_rows(conn, briefing_id):
    db.update_briefing(conn, briefing_id, briefing_text=SAMPLE_HTML)
    count = db.process_briefing_sections(conn, briefing_id)

    assert count == 2
    rows = db.get_sections_by_briefing_id(conn, briefing_id)
    assert [r["title"] for r in rows] == ["Ukraine", "Middle East"]


def test_process_briefing_sections_unknown_briefing_raises(conn):
    with pytest.raises(ValueError):
        db.process_briefing_sections(conn, 9999)


def test_process_briefing_sections_rerun_replaces_sections(conn, briefing_id):
    db.update_briefing(conn, briefing_id, briefing_text=SAMPLE_HTML)
    db.process_briefing_sections(conn, briefing_id)
    db.process_briefing_sections(conn, briefing_id)  # run twice

    rows = db.get_sections_by_briefing_id(conn, briefing_id)
    assert len(rows) == 2  # not duplicated


def test_process_all_briefings(conn):
    b1 = db.insert_briefing(conn, "2026-01-01", "https://x.com/1", SAMPLE_HTML)
    b2 = db.insert_briefing(conn, "2026-01-02", "https://x.com/2", "<p>No headers here.</p>")

    result = db.process_all_briefings(conn)

    assert result[b1] == 2
    assert result[b2] == 0