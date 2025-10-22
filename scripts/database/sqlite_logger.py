#!/usr/bin/env python3
import sqlite3
from pathlib import Path
from datetime import datetime

# Database lives alongside captures
DB_PATH = Path(__file__).parent.parent / "data" / "captures" / "capture_manifest.db"

DDL_CAPTURES = """
CREATE TABLE IF NOT EXISTS captures (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    timestamp TEXT NOT NULL,
    center_freq_hz INTEGER NOT NULL,
    sample_rate_hz INTEGER NOT NULL,
    gain_db INTEGER NOT NULL,
    duration_sec REAL NOT NULL,
    file_path TEXT NOT NULL,
    file_size_bytes INTEGER NOT NULL,
    data_hash TEXT NOT NULL,
    notes TEXT,
    validated INTEGER DEFAULT 0,
    validation_confidence REAL,
    validation_score INTEGER
);
"""

DDL_LABELS = """
CREATE TABLE IF NOT EXISTS labels (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    capture_id INTEGER NOT NULL,
    signal_type TEXT,
    measured_freq_hz INTEGER,
    notes TEXT,
    FOREIGN KEY (capture_id) REFERENCES captures(id)
);
"""

DDL_FINGERPRINTS = """
CREATE TABLE IF NOT EXISTS fingerprints (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    capture_id INTEGER NOT NULL,
    peak_freq_hz REAL NOT NULL,
    freq_error_hz REAL,
    cnr_db REAL NOT NULL,
    bandwidth_3db_hz REAL NOT NULL,
    adjacent_rejection_db REAL NOT NULL,
    rolloff_left_slope REAL,
    rolloff_right_slope REAL,
    rolloff_asymmetry REAL,
    processing_time_sec REAL,
    FOREIGN KEY(capture_id) REFERENCES captures(id) ON DELETE CASCADE
);
"""

def init_db():
    """Initialize SQLite database with schema"""
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)

    conn = sqlite3.connect(DB_PATH)
    conn.execute(DDL_CAPTURES)
    conn.execute(DDL_LABELS)
    conn.execute(DDL_FINGERPRINTS)
    conn.commit()
    conn.close()
    print(f"[DB] Initialized SQLite at {DB_PATH}")

def log_to_sqlite(capture: dict) -> int:
    """
    Log capture to SQLite manifest.

    Args:
        capture: dict from process_capture() containing:
            - timestamp: datetime
            - center_freq: Hz
            - sample_rate: Hz
            - data_path: Path to .sigmf-data
            - data_hash: SHA-256 hash
            - file_size_mb: Size in MB

    Returns:
        capture_id: Integer primary key for this capture
    """
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()

    # Extract duration if provided, otherwise estimate from file size
    # 2 bytes per sample (I+Q uint8), sample_rate samples/sec
    duration = capture.get("duration_sec", 0.0)
    gain = capture.get("gain_db", 0)

    c.execute('''
        INSERT INTO captures (timestamp, center_freq_hz, sample_rate_hz, gain_db,
                            duration_sec, file_path, file_size_bytes, data_hash, notes)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
    ''', (
        capture["timestamp"].isoformat(),
        int(capture["center_freq"]),
        int(capture["sample_rate"]),
        gain,
        duration,
        str(capture["data_path"]),
        int(capture["file_size_mb"] * 1024 * 1024),
        capture["data_hash"],
        capture.get("notes", "")
    ))

    capture_id = c.lastrowid
    conn.commit()
    conn.close()

    print(f"[DB] Logged capture #{capture_id}: {capture['data_path'].name}")
    return capture_id

if __name__ == "__main__":
    init_db()
