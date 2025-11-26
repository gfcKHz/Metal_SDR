#!/usr/bin/env python3
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

import sqlite3
from database.sqlite_logger import DB_PATH

def main():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row  # Access columns by name

    print("\n=== Capture Summary by Frequency ===")
    cursor = conn.execute("""
        SELECT  center_freq_hz / 1e6 as center_freq_mhz,
                COUNT(*) as n,
                MIN(timestamp) as first,
                MAX(timestamp) as last,
                SUM(file_size_bytes) / 1e6 as total_mb
        FROM captures
        GROUP BY center_freq_hz
        ORDER BY center_freq_hz
    """)

    for row in cursor:
        print(f"{row['center_freq_mhz']:8.1f} MHz | {row['n']:3d} captures | "
              f"{row['total_mb']:6.1f} MB | {row['first']} → {row['last']}")

    print("\n=== Total Statistics ===")
    cursor = conn.execute("""
        SELECT COUNT(*) as total_captures,
               SUM(file_size_bytes) / 1e6 as total_mb,
               SUM(duration_sec) / 3600.0 as total_hours
        FROM captures
    """)
    row = cursor.fetchone()
    print(f"Total captures: {row['total_captures']}")
    print(f"Total data: {row['total_mb']:.1f} MB")
    print(f"Total duration: {row['total_hours']:.2f} hours")

    conn.close()

if __name__ == "__main__":
    main()