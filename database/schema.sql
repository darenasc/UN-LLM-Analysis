

-- SQLite schema for UN LLM Analysis

CREATE TABLE briefings (
    briefing_id INTEGER PRIMARY KEY,
    briefing_date DATE NOT NULL,
    url TEXT UNIQUE NOT NULL,
    briefing_text TEXT NOT NULL,
    download_date TIMESTAMP,
    processing_date TIMESTAMP,
    metadata TEXT
);
    
   

CREATE TABLE sections (

    section_id INTEGER PRIMARY KEY,
    briefing_id INTEGER NOT NULL,
    title TEXT NOT NULL,
    section_text TEXT NOT NULL,
    FOREIGN KEY (briefing_id) REFERENCES briefings(briefing_id)
);