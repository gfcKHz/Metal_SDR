# Metal_SDR

RTL-SDR capture pipeline for FM broadcast monitoring and signal analysis.

## Current System Overview

**Purpose**: Capture IQ samples from RTL-SDR hardware, store in SigMF format, and maintain a SQLite manifest for tracking captures over time.

**Hardware**: RTL-SDR (R828D v4)

**Target Signals**: FM broadcast stations (87.5-108 MHz)

## Architecture

```
RTL-SDR Hardware
      ↓
rtl_sdr.exe (capture IQ samples)
      ↓
IQ Processing (uint8 → complex float32)
      ↓
SigMF Format (.sigmf-data + .sigmf-meta)
      ↓
SQLite Manifest (capture_manifest.db)
```

## Components

### Capture Scripts

**`capture_rtl_real.py`** - Single capture
- Captures IQ samples from RTL-SDR via `rtl_sdr.exe`
- Converts raw uint8 IQ to float32 complex format
- Stores as SigMF file pair (data + metadata)
- Logs capture metadata to SQLite database
- Default: 5 seconds at 100 MHz, 2.4 Msps, gain=20 dB

**`batch_capture.py`** - Batch time-series captures
- Runs multiple captures with configurable time intervals
- Useful for tracking station stability over time
- Default: 10 captures, 5-minute intervals, 105.9 MHz

### Data Pipeline

**`capture_sigmf.py`** - SigMF file handling
- Converts IQ samples to SigMF format (compliant with [SigMF specification](https://github.com/gnuradio/SigMF))
- Generates metadata JSON with capture parameters
- Computes BLAKE3 hash for data integrity
- File naming: `capture_YYYYMMDD_HHMMSS_<freq>Mhz.sigmf-{data,meta}`

**`sqlite_logger.py`** - Database manifest
- Initializes SQLite database schema
- Logs capture metadata: timestamp, frequency, sample rate, gain, duration, file path, hash
- Supports optional labeling (signal type, measured frequency)
- Database location: `data/captures/capture_manifest.db`

**`analyze_captures.py`** - Summary statistics
- Queries database for capture summaries by frequency
- Reports total captures, data size, time range per frequency

### Configuration

**`config.py`** - Path configuration
- Cross-platform base directory handling
- Defines capture storage location: `D:/dataset/sdr-pipeline/data/captures` (Windows)

**`models.py`** - Data structures
- `Capture` dataclass: immutable capture artifact with metadata

## Database Schema

### `captures` table
```sql
CREATE TABLE captures (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    timestamp TEXT NOT NULL,           -- ISO 8601 format
    center_freq_hz INTEGER NOT NULL,   -- Tuned frequency
    sample_rate_hz INTEGER NOT NULL,   -- Sample rate (typically 2.4 MHz)
    gain_db INTEGER NOT NULL,          -- Tuner gain
    duration_sec REAL NOT NULL,        -- Capture duration
    file_path TEXT NOT NULL,           -- Path to .sigmf-data file
    file_size_bytes INTEGER NOT NULL,
    data_hash TEXT NOT NULL,           -- BLAKE3 hash for integrity
    notes TEXT                         -- Optional annotations
);
```

### `labels` table
```sql
CREATE TABLE labels (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    capture_id INTEGER NOT NULL,
    signal_type TEXT,                  -- e.g., "FM broadcast"
    measured_freq_hz INTEGER,          -- Measured peak frequency
    notes TEXT,
    FOREIGN KEY (capture_id) REFERENCES captures(id)
);
```

## Usage

### Single Capture
```bash
python capture_rtl_real.py --freq 105.9e6 --duration 3 --gain 20
```

### Batch Capture
```bash
# Capture WQXR (105.9 MHz) every 5 minutes, 10 times
python batch_capture.py --freq 105.9e6 --num-captures 10 --interval 300
```

### Analyze Captured Data
```bash
python analyze_captures.py
```

Example output:
```
=== Capture Summary by Frequency ===
  105.9 MHz |  10 captures |   28.5 MB | 2025-01-15T10:00:00 → 2025-01-15T11:00:00

=== Total Statistics ===
Total captures: 10
Total data: 28.5 MB
Total duration: 0.01 hours
```

## Data Format

### IQ Sample Format
- **Raw**: Interleaved uint8 (I₀, Q₀, I₁, Q₁, ...)
- **Processed**: Complex64 (float32 I + j·Q), normalized to [-1, 1]
- **Conversion**: `(uint8 - 127.5) / 127.5`

### SigMF Metadata
```json
{
  "global": {
    "core:datatype": "cf32_le",
    "core:sample_rate": 2400000,
    "core:version": "1.0.0",
    "core:description": "RTL-SDR @105.9 MHz",
    "core:blake3": "<hash>",
    "core:author": "sp7der"
  },
  "captures": [
    {
      "core:sample_start": 0,
      "core:frequency": 105900000,
      "core:datetime": "2025-01-15T10:00:00Z"
    }
  ]
}
```

## Current Limitations

**No Signal Analysis**: System currently only captures and stores data. No feature extraction or signal characterization is performed.

**No Validation**: Captures are stored regardless of signal quality or whether the intended station was actually captured.

**Peak Frequency Instability**: Preliminary analysis shows ±0.5 MHz jitter when measuring peak frequency via FFT, making it difficult to confirm station identity across multiple captures.

**Manual Labeling**: Station identification and signal classification must be done manually after capture.

## Data Storage

- **Sample rate**: 2.4 MHz (2.4 million complex samples/second)
- **Data rate**: 19.2 MB/sec (2 × 4 bytes per complex sample)
- **3-second capture**: ~57.6 MB per file
- **Typical usage**: 300-400 captures = 17-23 GB

## Author

sp7der
