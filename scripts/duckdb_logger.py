import duckdb
from datetime import datetime
from pathlib import Path

DDL = """
CREATE TABLE IF NOT EXISTS captures (
    id               VARCHAR PRIMARY KEY,
    timestamp        TIMESTAMP,
    center_freq_mhz  DOUBLE,
    sample_rate_mhz  DOUBLE,
    file_size_mb     DOUBLE,
    data_sha256      VARCHAR,
    raw_file_path    VARCHAR
);
"""

def log_to_duckdb(capture: dict, db_path: Path) -> None:
    conn = duckdb.connect(str(db_path))
    conn.execute(DDL)
    conn.execute("""
        INSERT INTO captures
        VALUES (?, ?, ?, ?, ?, ?, ?)
    """, (
        capture["id"],
        capture["timestamp"],
        capture["center_freq"] / 1e6,
        capture["sample_rate"] / 1e6,
        capture["file_size_mb"],
        capture["data_hash"],
        str(capture["data_path"])
    ))
    conn.commit()
    conn.close()
    print(f"[DB] logged  {capture['data_path'].name}")