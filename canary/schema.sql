-- Canary's local database. Created by canary/db.py inside CANARY_HOME.

CREATE TABLE IF NOT EXISTS exams (
    id INTEGER PRIMARY KEY,
    title TEXT NOT NULL,
    is_synthetic INTEGER NOT NULL DEFAULT 1,
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS questions (
    id TEXT PRIMARY KEY,                    -- same ids as the bank, e.g. P001
    exam_id INTEGER NOT NULL REFERENCES exams(id),
    position INTEGER,                       -- NULL for traps and reserves
    subject TEXT NOT NULL,
    kind TEXT NOT NULL CHECK (kind IN ('numeric', 'fixed', 'trap')),
    difficulty TEXT NOT NULL,
    body TEXT NOT NULL,                     -- JSON
    is_reserve INTEGER NOT NULL DEFAULT 0
);

CREATE TABLE IF NOT EXISTS people (
    id INTEGER PRIMARY KEY,
    display_name TEXT NOT NULL,
    role TEXT NOT NULL,
    organisation TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS copies (
    id INTEGER PRIMARY KEY,
    exam_id INTEGER NOT NULL REFERENCES exams(id),
    stage TEXT NOT NULL CHECK (stage IN ('translation', 'print')),
    copy_no INTEGER NOT NULL,
    holder_id INTEGER REFERENCES people(id),
    UNIQUE (exam_id, stage, copy_no)
);

CREATE TABLE IF NOT EXISTS custody_events (
    id INTEGER PRIMARY KEY,
    copy_id INTEGER NOT NULL REFERENCES copies(id),
    from_id INTEGER REFERENCES people(id),
    to_id INTEGER REFERENCES people(id),
    at TEXT NOT NULL,
    note TEXT,
    prev_hash TEXT NOT NULL,
    event_hash TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS custody_by_copy ON custody_events (copy_id, at);

CREATE TABLE IF NOT EXISTS watched_chats (
    username TEXT PRIMARY KEY,
    title TEXT,
    added_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS leaks (
    id INTEGER PRIMARY KEY,
    exam_id INTEGER REFERENCES exams(id),
    source TEXT NOT NULL CHECK (source IN ('telegram', 'manual')),
    chat_id INTEGER,
    chat_title TEXT,
    chat_username TEXT,
    message_id INTEGER,
    message_url TEXT,
    sender_id INTEGER,
    sender_username TEXT,
    sender_name TEXT,
    image_path TEXT,
    image_sha256 TEXT,
    raw_text TEXT,
    posted_at TEXT,
    received_at TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'queued'
        CHECK (status IN ('queued', 'reading', 'done', 'unreadable', 'failed')),
    error TEXT,
    UNIQUE (chat_id, message_id)
);
CREATE INDEX IF NOT EXISTS leaks_by_status ON leaks (status, id);

CREATE TABLE IF NOT EXISTS leak_questions (
    id INTEGER PRIMARY KEY,
    leak_id INTEGER NOT NULL REFERENCES leaks(id) ON DELETE CASCADE,
    question_id TEXT REFERENCES questions(id),
    clue_type TEXT CHECK (clue_type IN ('value', 'trap', 'order')),
    clue TEXT,                              -- JSON
    match_score REAL,
    read_ok INTEGER NOT NULL DEFAULT 1
);

CREATE TABLE IF NOT EXISTS cases (
    id INTEGER PRIMARY KEY,
    leak_id INTEGER NOT NULL UNIQUE REFERENCES leaks(id) ON DELETE CASCADE,
    verdict TEXT NOT NULL CHECK (verdict IN ('traced', 'strong_lead', 'inconclusive', 'not_our_paper')),
    stage TEXT CHECK (stage IN ('translation', 'print')),
    copy_id INTEGER REFERENCES copies(id),  -- NULL unless traced or strong_lead
    clues_read INTEGER NOT NULL DEFAULT 0,
    clues_matched INTEGER NOT NULL DEFAULT 0,
    expected_false_matches REAL,
    steps TEXT,                             -- JSON, the funnel the dashboard animates
    reader TEXT,
    elapsed_ms INTEGER,
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS audit_log (
    id INTEGER PRIMARY KEY,
    at TEXT NOT NULL,
    action TEXT NOT NULL,
    detail TEXT NOT NULL,                   -- JSON
    prev_hash TEXT NOT NULL,
    event_hash TEXT NOT NULL
);
