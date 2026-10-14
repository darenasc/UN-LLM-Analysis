-- SQLite schema for UN LLM Analysis

PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS briefing (
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


CREATE TABLE IF NOT EXISTS section (
    section_id INTEGER PRIMARY KEY,
    briefing_id INTEGER NOT NULL,
    section_order INTEGER NOT NULL,
    title TEXT NOT NULL,
    text TEXT NOT NULL,

    FOREIGN KEY (briefing_id)
        REFERENCES briefing(briefing_id)
        ON DELETE CASCADE,

    UNIQUE (briefing_id, section_order)
);


CREATE TABLE IF NOT EXISTS sdg (
    briefing_id INTEGER NOT NULL,
    section_id INTEGER NOT NULL,
    sdg TEXT NOT NULL,
    model TEXT NOT NULL,
    created_at TEXT NOT NULL
);


CREATE TABLE IF NOT EXISTS issue (
    briefing_id INTEGER NOT NULL,
    section_id INTEGER NOT NULL,
    issue TEXT NOT NULL,
    model TEXT NOT NULL,
    created_at TEXT NOT NULL
);


CREATE TABLE IF NOT EXISTS country (
    briefing_id INTEGER NOT NULL,
    section_id INTEGER NOT NULL,
    country TEXT NOT NULL,
    iso_2 TEXT NOT NULL,
   	iso_3 TEXT NOT NULL,
    model TEXT NOT NULL,
    created_at TEXT NOT NULL
);


CREATE TABLE IF NOT EXISTS analysis_run (
    analysis_id INTEGER PRIMARY KEY AUTOINCREMENT,
    analysis_name TEXT NOT NULL,
    model_name TEXT NOT NULL,
    model_version TEXT,
    ollama_version TEXT,
    prompt_version TEXT NOT NULL,
    prompt TEXT NOT NULL,
    temperature REAL NOT NULL,
    created_at TEXT NOT NULL
);


CREATE TABLE IF NOT EXISTS sentiment_analysis (
    analysis_result_id INTEGER PRIMARY KEY AUTOINCREMENT,
    analysis_id INTEGER NOT NULL,
    briefing_id INTEGER NOT NULL,
    section_id INTEGER NOT NULL,
    briefing_date TEXT,
    sentiment TEXT,
    tone TEXT,
    status TEXT NOT NULL,
    error_message TEXT,
    created_at TEXT NOT NULL,

    FOREIGN KEY (analysis_id)
        REFERENCES analysis_run(analysis_id),

    UNIQUE (analysis_id, briefing_id, section_id)
);
