-- SQLite schema for UN LLM Analysis

PRAGMA foreign_keys = ON;

CREATE TABLE briefing (
    briefing_id INTEGER PRIMARY KEY,
    briefing_date TEXT NOT NULL UNIQUE,
    url TEXT NOT NULL UNIQUE,
    status TEXT NOT NULL CHECK (
        status IN ('available', 'not_published', 'failed')
    ),
    http_status INTEGER,
    error TEXT,
    speaker_name TEXT,
    speaker_role TEXT,
    full_text TEXT NOT NULL,
    downloaded_at TEXT NOT NULL,
    processed_at TEXT NOT NULL
);


CREATE TABLE section (
    section_id INTEGER PRIMARY KEY,
    briefing_id INTEGER NOT NULL,
    section_order INTEGER NOT NULL,
    title TEXT NOT NULL,
    text TEXT NOT NULL,

    FOREIGN KEY (briefing_id)
        REFERENCES briefings(briefing_id)
        ON DELETE CASCADE,

    UNIQUE (briefing_id, section_order)
);
