#!/usr/bin/env python3
""" 
Process SigMF captures and extract FM fingerprints to database

Batch processes .sigmf-data files from the captures directory, extracts Tier-1
spectral features using fm_validator.py, and stores results in the fingerprints table

Usage:
    # Process all unprocessed captures
    python process_fingerprints.py

    # Process specific file
    python process_fingerprints.py --file data/captures/capture_202050122_*.sigmf-data

    # Reprocess all (overwrite existing fingerprints)
    python process_fingerprints.py --reprocess
"""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

import argparse
import sqlite3
from typing import Optional
import traceback

from scripts.fingerprinting.fm_fingerprint import load_sigmf, extract_fingerprint
from database.sqlite_logger import DB_PATH

def get_capture_id(conn: sqlite3.Connection, sigmf_path: Path) -> Optional[int]:
    """ 
    Look up capture_id from file path in database

    Args:
        conn: SQLite connection
        sigmf_path: Path to .sigmf-data file

    Returns:
        capture_id or None if not found
    """
    # Convert .sigmf-data to just the base path stored in DB
    file_path_str = str(sigmf_path)

    cursor = conn.execute(
        "SELECT id FROM captures WHERE file_path = ?",
        (file_path_str,)
    )
    row = cursor.fetchone()
    return row[0] if row else None

def fingerprint_exists(conn: sqlite3.Connection, capture_id: int) -> bool:
    """ 
    Check if fingerprint already exists for this capture

    Args:
        conn: SQLite connection
        capture_id: Capture ID to check

    Returns:
        True if fingerprint exists
    """
    cursor = conn.execute(
        "SELECT COUNT(*) FROM fingerprints WHERE capture_id = ?",
        (capture_id,)
    )
    count = cursor.fetchone()[0]
    return count > 0

def insert_fingerprint(conn: sqlite3.Connection, capture_id: int, features: dict):
    """
    Insert fingerprint features into database

    Args:
        conn: SQLite connection
        capture_id: ID of the capture
        features: Dict of features from extract_fingerprint()
    """
    conn.execute(""" 
        INSERT INTO fingerprints (
            capture_id,
            peak_freq_hz,
            freq_error_hz,
            cnr_db,
            bandwidth_3db_hz,
            adjacent_rejection_db,
            rolloff_left_slope,
            rolloff_right_slope,
            rolloff_asymmetry,
            processing_time_sec
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        capture_id,
        features['peak_freq_hz'],
        features['freq_error_hz'],
        features['cnr_db'],
        features['bandwidth_3db_hz'],
        features['adjacent_rejection_db'],
        features['rolloff_left_slope'],
        features['rolloff_right_slope'],
        features['rolloff_asymmetry'],
        features['processing_time_sec']
    ))

def update_fingerprint(conn: sqlite3.Connection, capture_id: int, features: dict):
    """
    Update existing fingerprint with new features

    Args:
        conn: SQLite connection
        capture_id: ID of the capture
        features: Dict of features from extract_fingerprint()
    """
    conn.execute("""
        UPDATE fingerprints SET
            peak_freq_hz = ?
            freq_error_hz = ?
            cnr_db = ?
            bandwidth_3db_hz = ?
            adjacent_rejection_db = ?
            rolloff_left_slope = ?
            rolloff_right_slope = ?
            rolloff_asymmetry = ?
            processing_time_sec = ?
        WHERE capture_id = ?
    """, (
        features['peak_freq_hz'],
        features['freq_error_hz'],
        features['cnr_db'],
        features['bandwidth_3db_hz'],
        features['adjacent_rejection_db'],
        features['rolloff_left_slope'],
        features['rolloff_right_slope'],
        features['rolloff_asymmetry'],
        features['processing_time_sec'],
        capture_id
    )) 

def process_one_capture(conn: sqlite3.Connection, sigmf_path: Path,
                        reprocess: bool = False) -> bool:
    """
    Process a single SigMF capture and store fingerprint

    Args:
        conn: SQLite connection
        sigmf_path: Path to .sigmf-data file
        reprocess: If True, overwrite existing fingerprints

    Returns:
        True if successful, False otherwise
    """
    try:
        # Look up capture_id
        capture_id = get_capture_id(conn, sigmf_path)
        if capture_id is None:
            print(f"  WARNING: {sigmf_path.name} not found in database, skipping")
            return False
        
        # Check if already processed
        if not reprocess and fingerprint_exists(conn, capture_id):
             print(f" SKIP: {sigmf_path.name} already processed (use --reprocess to overwrite)")
             return True

        # Load IQ data and metadata
        print(f"  Loading {sigmf_path.name}...")
        iq_data, metadata = load_sigmf(sigmf_path)

        # Extract fingerprint
        print(f"    Extracting fingerprint from {len(iq_data):,} samples...")
        features = extract_fingerprint(
            iq_data,
            metadata['sample_rate'],
            metadata['center_freq']
        )

        # Store or update in database
        if fingerprint_exists(conn, capture_id):
            update_fingerprint(conn, capture_id, features)
            print(f"    UPDATED fingerprint for capture #{capture_id}")
        else:
            insert_fingerprint(conn, capture_id, features)
            print(f"    INSERTED fingerprint for capture #{capture_id}")

        # Print key metrics
        print(f"    Peak: {features['peak_freq_hz']/1e6:.6f} MHz, "
              f"CNS: {features['cnr_db']:.1f} dB, "
              f"BW: {features['bandwidth_3db_hz']/1e3:.1f} kHz")
        
        return True
    
    except Exception as e:
        print(f"  ERROR processing {sigmf_path.name}: {e}")
        traceback.print_exc()
        return False
    
def main(file_pattern: Optional[str] = None, reprocess: bool = False):
    """ 
    Main processing loop

    Args:
        file_patten: Glob pattern for specific files (None = all)
        reprocess: If True, reprocess files that already have fingerprints
    """
    # Find all .sigmf-data files
    captures_dir = DB_PATH.parent

    if file_pattern:
        # Use specific pattern
        sigmf_files = sorted(captures_dir.glob(file_pattern))
    else:
        # Default: all .sigmf-data files
        sigmf_files = sorted(captures_dir.glob("*.sigmf-data"))

    if not sigmf_files:
        print(f"No .sigmf-data files found in {captures_dir}")
        return
    
    print(f"Found {len(sigmf_files)} capture(s) to process")
    print(f"Database: {DB_PATH}")
    print(f"Reprocess mode: {reprocess}")
    print()

    # Connect to database
    conn = sqlite3.connect(DB_PATH)

    success_count = 0
    skip_count = 0
    error_count = 0

    try:
        for i, sigmf_path in enumerate(sigmf_files, 1):
            print(f"[{i}/{len(sigmf_files)}] Processing {sigmf_path.name}")

            result = process_one_capture(conn, sigmf_path, reprocess)

            if result:
                success_count += 1
            else:
                # Check if it was a skip or an error
                capture_id = get_capture_id(conn, sigmf_path)
                if capture_id and not reprocess and fingerprint_exists(conn, capture_id):
                    skip_count += 1
                else:
                    error_count += 1
            
            print()
        
        # Commit all changes
        conn.commit()
        print("=" * 60)
        print(f"Processing complete:")
        print(f"  Success: {success_count}")
        print(f"  Skipped: {skip_count}")
        print(f"  Errors:  {error_count}")
        print(f"  Total:   {len(sigmf_files)}")

    finally:
        conn.close()

if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Process SigMF captures and extract FM fingerprints"
    )
    parser.add_argument(
        "--file",
        type=str,
        help="Glob pattern for specific files (e.g., 'capture_20250122_*.sigmf-data')"
    )
    parser.add_argument(
        "--reprocess",
        action="store_true",
        help="Reprocess files that already have fingerprints"
    )

    args = parser.parse_args()

    main(file_pattern=args.file, reprocess=args.reprocess)