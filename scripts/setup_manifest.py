#!/usr/bin/env python3
from config import get_kuzu_connection
from datetime import datetime

def setup_kuzu_schema():
    """Initialize Kuzu graph schema for SDR data"""
    conn = get_kuzu_connection()
    
    # Drop existing tables (clean start)
    conn.execute("DROP TABLE IF EXISTS Capture;")
    conn.execute("DROP TABLE IF EXISTS Frequency;")
    conn.execute("DROP TABLE IF EXISTS Hardware;")
    conn.execute("DROP REL TABLE IF EXISTS AT_FREQUENCY;")
    conn.execute("DROP REL TABLE IF EXISTS USING_HARDWARE;")
    conn.execute("DROP REL TABLE IF EXISTS OCCURS_NEAR;")
    
    # Create node tables
    conn.execute("""
        CREATE NODE TABLE Capture(
            id STRING,
            timestamp TIMESTAMP,
            sample_rate_mhz DOUBLE,
            file_size_mb DOUBLE,
            data_sha256 STRING,
            raw_file_path STRING,
            PRIMARY KEY (id)
        )
    """)
    
    conn.execute("""
        CREATE NODE TABLE Frequency(
            mhz DOUBLE,
            band_name STRING,
            PRIMARY KEY (mhz)
        )
    """)
    
    conn.execute("""
        CREATE NODE TABLE Hardware(
            type STRING,
            serial_number STRING,
            PRIMARY KEY (type, serial_number)
        )
    """)
    
    # Create relationship tables
    conn.execute("""
        CREATE REL TABLE AT_FREQUENCY(
            FROM Capture TO Frequency,
            signal_strength DOUBLE
        )
    """)
    
    conn.execute("""
        CREATE REL TABLE USING_HARDWARE(
            FROM Capture TO Hardware
        )
    """)
    
    conn.execute("""
        CREATE REL TABLE OCCURS_NEAR(
            FROM Capture TO Capture,
            time_diff_ms INT64,
            freq_diff_mhz DOUBLE
        )
    """)
    
    print("✅ Kuzu graph schema created!")
    
    # Pre-populate frequency bands
    frequency_bands = [
        (88.0, "FM Radio"),
        (108.0, "FM Radio"),
        (144.0, "2m Ham"),
        (162.0, "Weather"),
        (433.0, "UHF"),
        (1090.0, "ADS-B")
    ]
    
    for freq, band in frequency_bands:
        conn.execute(
            "CREATE (f:Frequency {mhz: $mhz, band_name: $band})",
            {"mhz": freq, "band": band}
        )
    
    print("✅ Pre-populated frequency bands!")
    conn.close()

if __name__ == "__main__":
    setup_kuzu_schema()