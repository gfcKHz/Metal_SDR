# Metal_SDR

RTL-SDR capture pipeline for FM broadcast monitoring and signal analysis.

## Current System Overview

**Purpose**: Capture IQ samples from RTL-SDR hardware, store in SigMF format, and maintain a SQLite manifest for tracking captures over time.

**Hardware**: RTL-SDR (R828D v4)

**Target Signals**: FM broadcast stations (87.5-108 MHz)

## Architecture

```
┌─────────────────────────────────────────────────────────────────────────┐
│                            METAL-SDR PIPELINE                           │
└─────────────────────────────────────────────────────────────────────────┘

    ┌──────────────────┐
    │  RTL-SDR R828D   │  ← Hardware (Production: Hades Canyon NUC)
    │   915 MHz ISM    │    Development: M2 MacBook + portable SDR
    └────────┬─────────┘    Future: Ettus B210 (Jan 2025)
             │
             │ USB 2.0
             ▼
    ┌──────────────────────────────────────────────────────────────────────┐
    │                       rtl_sdr.exe CAPTURE                            │
    │  ┌────────────────────────────────────────────────────────────────┐  │
    │  │  Command: rtl_sdr -f <freq> -s 2.4e6 -n <samples> output.bin   │  │
    │  │  Output: Raw IQ samples (uint8, interleaved I/Q)               │  │
    │  └────────────────────────────────────────────────────────────────┘  │
    └────────┬─────────────────────────────────────────────────────────────┘
             │
             │ .bin file (uint8 I/Q)
             ▼
    ┌─────────────────────────────────────────────────────────────────────────────┐
    │                      IQ PROCESSING LAYER                                    │
    │  ┌───────────────────────────────────────────────────────────────────────┐  │
    │  │  1. Convert uint8 → complex float32 (line 74: capture_rtl_real.py)    │  │
    │  │     scale = (iq_u8 - 127.5) / 127.5                                   │  │
    │  │                                                                       │  │
    │  │  2. DC offset removal (optional)                                      │  │
    │  │     iq_centered = iq - mean(iq)                                       │  │
    │  │                                                                       │  │
    │  │  3. IQ imbalance correction (future)                                  │  │
    │  │     α = amplitude_factor, θ = phase_offset                            │  │
    │  └───────────────────────────────────────────────────────────────────────┘  │
    └────────┬────────────────────────────────────────────────────────────────────┘
             │
             │ complex64 array
             ▼
    ┌──────────────────────────────────────────────────────────────────────┐
    │                        SIGMF FORMATTER                               │
    │  ┌────────────────────────────────────────────────────────────────┐  │
    │  │  .sigmf-data:  Binary IQ samples (complex64, little-endian)    │  │
    │  │  .sigmf-meta:  JSON metadata                                   │  │
    │  │    {                                                           │  │
    │  │      "global": {                                               │  │
    │  │        "core:datatype": "cf32_le",                             │  │
    │  │        "core:sample_rate": 2400000,                            │  │
    │  │        "core:version": "1.0.0",                                │  │
    │  │        "core:sha512": "<hash>"                                 │  │
    │  │      },                                                        │  │
    │  │      "captures": [{                                            │  │
    │  │        "core:frequency": 915000000,                            │  │
    │  │        "core:datetime": "2025-01-15T14:30:00Z"                 │  │
    │  │      }],                                                       │  │
    │  │      "annotations": []                                         │  │
    │  │    }                                                           │  │
    │  └────────────────────────────────────────────────────────────────┘  │
    └────────┬─────────────────────────────────────────────────────────────┘
             │
             │ .sigmf-data + .sigmf-meta
             ▼
    ┌──────────────────────────────────────────────────────────────────────┐
    │                    SQLITE MANIFEST DATABASE                          │
    │  ┌────────────────────────────────────────────────────────────────┐  │
    │  │  TABLE: captures                                               │  │
    │  │  ┌──────────┬─────────────┬──────────────┬──────────────────┐  │  │
    │  │  │ id (PK)  │ file_path   │ center_freq  │ sample_rate      │  │  │
    │  │  ├──────────┼─────────────┼──────────────┼──────────────────┤  │  │
    │  │  │ 1        │ cap001.sigmf│ 915000000    │ 2400000          │  │  │
    │  │  │ 2        │ cap002.sigmf│ 105900000    │ 2400000          │  │  │
    │  │  └──────────┴─────────────┴──────────────┴──────────────────┘  │  │
    │  │                                                                │  │
    │  │  TABLE: fingerprints (NEXT PHASE)                              │  │
    │  │  ┌──────────┬──────────────┬───────┬────────────────────────┐  │  │
    │  │  │ cap_id   │ peak_freq_hz │ cnr_db│ bandwidth_3db_hz       │  │  │
    │  │  ├──────────┼──────────────┼───────┼────────────────────────┤  │  │
    │  │  │ 1        │ 915234567    │ 28.3  │ 195000                 │  │  │
    │  │  └──────────┴──────────────┴───────┴────────────────────────┘  │  │
    │  │                                                                │  │
    │  │  Integrity: BLAKE3 hashes verify .sigmf-data hasn't changed    │  │
    │  └────────────────────────────────────────────────────────────────┘  │
    └────────┬─────────────────────────────────────────────────────────────┘
             │
             │ Query captures
             ▼
    ┌──────────────────────────────────────────────────────────────────────┐
    │                    FEATURE EXTRACTION (extract_fingerprints.py)      │
    │  ┌────────────────────────────────────────────────────────────────┐  │
    │  │  FOR EACH .sigmf-data file:                                    │  │
    │  │                                                                │  │
    │  │  1. Load IQ samples                                            │  │
    │  │  2. Compute Welch PSD (4096-pt FFT, 50% overlap, Hann window)  │  │
    │  │  3. Extract Tier-1 Features:                                   │  │
    │  │     ┌──────────────────────────────────────────────────────┐   │  │
    │  │     │ • Peak Frequency (parabolic interpolation, ±50 Hz)   │   │  │
    │  │     │ • CNR via MPA noise floor (quietest 5% of bins)      │   │  │
    │  │     │ • 3dB Bandwidth (interpolate -3dB points)            │   │  │
    │  │     │ • Adjacent Rejection (power ratio @ ±200 kHz)        │   │  │
    │  │     │ • Spectral Rolloff (dB/100kHz, asymmetry)            │   │  │
    │  │     └──────────────────────────────────────────────────────┘   │  │
    │  │  4. Validate against expected station parameters               │  │
    │  │  5. INSERT INTO fingerprints table                             │  │
    │  └────────────────────────────────────────────────────────────────┘  │
    └────────┬─────────────────────────────────────────────────────────────┘
             │
             │ Validated features
             ▼
    ┌──────────────────────────────────────────────────────────────────────┐
    │                      ML TRAINING PIPELINE (FUTURE)                   │
    │  ┌────────────────────────────────────────────────────────────────┐  │
    │  │  • Graph Neural Network (GNN) for spectral topology            │  │
    │  │  • Transformer for temporal patterns                           │  │
    │  │  • Few-shot learning (300-400 captures, small dataset)         │  │
    │  │  • Metal acceleration on Apple Silicon (M2 MacBook)            │  │
    │  └────────────────────────────────────────────────────────────────┘  │
    └──────────────────────────────────────────────────────────────────────┘

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
- Converts IQ samples to SigMF format (compliant with [SigMF specification](https://sigmf.org/index.html))
- Generates metadata JSON with capture parameters
- Computes BLAKE3 hash for data integrity
- File naming: `capture_YYYYMMDD_HHMMSS_<freq>Mhz.sigmf-{data,meta}`

**`sqlite_logger.py`** - Database manifest
- Initializes SQLite database schema
- Logs capture metadata: timestamp, frequency, sample rate, gain, duration, file path, hash. 

  - Naively, I thought these hardware settings were the actual representation of the signal I was trying to capture but these are merely intentions (what you asked the SDR to do), this doesn't tell you what station you actually captured, if the signal is even present, or whether you're on-frequency or drifted
  
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

## Measurement Error History


### Wide-Bandwidth Source Ambiguity

**The Problem**: Initial captures used 2.4 MHz bandwidth centered at varying frequencies (100-142 MHz), creating a capture window that spanned multiple FM stations simultaneously. "Find the loudest peak" would identify different stations as they varied in power throughout the day.

**Symptom**: ±0.8 MHz frequency jumps between captures of supposedly the same target.

**Root Cause**: Algorithm correctly found peaks, but peaks came from different FM stations within the wide capture window. FM stations have time-varying transmit power (programming changes, transmitter adjustments), so "loudest" changed identity.

**The Fix**: Switched to narrow targeting with validation captures. Wide-bandwidth "find anything" approaches introduce source ambiguity. Target specific frequencies, validate systematically.


### Single-Feature Validation Fallacy

**The Problem**: After fixing source ambiguity with narrow targeting, captures still showed ±0.5 MHz peak frequency instability across time-series captures of the same station. Relying solely on peak frequency detection via FFT bin maximum was insufficient to validate station identity.

**Symptom**: Captures logged as "105.9 Mhz" could actually contain signals from 105.4 MHz, or 106.3 MHz. Metadata (tuner settings) became unreliable ground truth. What you see is not what you capture. Tuner settings document intention, not reality. Hardware lies, you must validate.

**Root Causes**:
- SDR Hardware Drift: RTL-SDR tuners exhibit frequency drift due to temperature, clock instability, and DC offset.
- Single Metric Fragility: Peak frequency alone can't distinguish between:
  - Same station with slight tuning drift
  - Different station at nearby frequency 
  - Weak signal vs. strong signal quality
  - Clean capture vs. adjacent channel interference

**The Fix**: Multi-feature FM fingerprinting with:
- Parabolic peak interpolation (sub-bin accuracy)
- Carrier-to-Noise Ratio (signal quality gate)
- 3dB bandwidth measurement (validates FM signal shape)
- Adjacent channel rejection (confirms frequency lock)
- Spectral rolloff analysis (detects interference)

**Expected Outcome**: Score-based validation where captures must achieve ≥70% confidence across multiple independent features to be considered valid.

**References**:
- [A Comprehensive Survey on Radio Frequency (RF) Fingerprinting](https://arxiv.org/abs/2201.00680)
- [Quadratic Interpolation of Spectral Peaks](https://ccrma.stanford.edu/~jos/sasp/Quadratic_Interpolation_Spectral_Peaks.html)
- [Welch's Method](https://ccrma.stanford.edu/~jos/sasp/Welch_s_Method.html)
- [Improving FFT Frequency Measurement Resolution by Parabolic and Gaussian Interpolation](https://mgasior.web.cern.ch/pap/FFT_resol_note.pdf)
- [Stanford EE179](https://web.stanford.edu/class/ee179/labs/Lab5.html)
- [Automatic noise level estimation and occupied bandwidth detection](https://dsp.stackexchange.com/questions/98190/automatic-noise-level-estimation-and-occupied-bandwidth-detection)
- [Frequency Modulation, FM Sidebands & Bandwidth](https://www.electronics-notes.com/articles/radio/modulation/frequency-modulation-fm-sidebands-bandwidth.php)
- [Frequency Modulation (FM) Tutorial](https://wwwqa.silabs.com/documents/public/white-papers/FMTutorial.pdf)
- [Spectral leakage and windowing](https://brianmcfee.net/dstbook-site/content/ch06-dft-properties/Leakage.html)
- [FFT Spectral Leakage and Windowing](http://saadahmad.ca/fft-spectral-leakage-and-windowing/)
- [WYSINWYX: What You See Is Not What You eXecute](https://research.cs.wisc.edu/wpis/papers/wysinwyx05.pdf)


## Current Limitations

**Limited to FM Broadcast**: Currently fingerprinting features are optimized for FM broadcast signals (180-220 kHz bandwidth). Other modulation types (AM, digital, etc.) would require different feature extractors.

**Windows-Centric Paths**: Configuration hardcoded for Windows paths. Cross-platform deployment requires manual config changes.

**No Real-Time Validation**: Multi-feature fingerprinting currently runs as post-processing. Captures are stored first, then validated in batch. Future work could integrate validation into the capture loop

**Tier 2 Features Not Implemented**: Stereo pilot tone (19 kHz) and RDS subcarrier (57 kHz) detection would require FM demodulation.

**Manual Station Configuration**: Expected station frequencies and characteristics must ber manually specified. No automatic station discovery or frequency scanning.


## Data Storage

- **Sample rate**: 2.4 MHz (2.4 million complex samples/second)
- **Data rate**: 19.2 MB/sec (2 × 4 bytes per complex sample)
- **3-second capture**: ~57.6 MB per file
- **Typical usage**: 300-400 captures = 17-23 GB