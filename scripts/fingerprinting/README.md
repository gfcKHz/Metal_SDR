# FM Broadcast Fingerprinting

Automated spectral feature extraction for FM broadcast station identification and signal quality validation.

## Overview

This system extracts **Tier-1 spectral fingerprints** from captured IQ data to:
- Validate station identity across time
- Detect signal quality degradation
- Identify interference and multi-path
- Filter out low-quality captures before deeper analysis

## Architecture

```
┌─────────────────┐
│  .sigmf-data    │  Raw IQ captures (2.4 Msps, 3-5 sec)
└────────┬────────┘
         │
         ▼
┌───────────────────┐
│ fm_fingerprint.py │  Feature extraction (Welch PSD → 5 metrics):
└────────┬──────────┘   - Parabolic peak: ~50 Hz accuracy
         │              - CNR (MPA): quality gate 
         │              - 3dB BW: 180-220 kHz expected 
         ▼              - Adjacent rejection: ≥15 dB 
                        - Rolloff asymmetry: ~1.0x 
┌─────────────────┐
│   SQLite DB     │  fingerprints table (capture_id → features)
└─────────────────┘
         │
         ▼
┌─────────────────┐
│  Validation &   │  Score captures, flag outliers, track drift
│   Analytics     │
└─────────────────┘
```

## Components 

**`fm_fingerprint.py`** - Core feature extraction

**`process_fingerprints.py`** - Batch processor (.sigmf-data -> SQLite DB) 

## Quick Start

### 1. Extract fingerprints from all captures

```bash
cd scripts/fingerprinting
python process_fingerprints.py
```

### 2. Process specific file

```bash
python process_fingerprints.py --file "capture_20250122_*.sigmf-data"
```

### 3. Reprocess everything (overwrite existing)

```bash
python process_fingerprints.py --reprocess
```

### 4. Extract single fingerprint (standalone)

```bash
python fm_fingerprint.py ../data/captures/capture_20250122_143022.sigmf-data
```

## Features Extracted

### 1. Peak Frequency (Hz)
**What:** Interpolated carrier frequency using 3-point parabolic fit
**Why:** Raw FFT bins have ±293 Hz quantization at 2.4 Msps. Parabola gets ~50 Hz accuracy.
**Threshold:** ±20 kHz tolerance for same station across time

```python
# Before: 105.900586 MHz (bin center)
# After:  105.900123 MHz (interpolated)
```

### 2. CNR - Carrier-to-Noise Ratio (dB)
**What:** Signal quality using Minimum Power Averaging (MPA)
**Why:** Rejects spurious peaks, validates clean signal
**Threshold:**
- `CNR < 18 dB` → Don't trust fine features (BW, rolloff)
- `CNR ≥ 25 dB` → Excellent quality

**Algorithm:**
1. Exclude ±150 kHz guard around carrier
2. Average quietest 5% of out-of-band bins (noise floor)
3. Integrate carrier power over ±50 kHz
4. Match bandwidth for noise power
5. CNR = 10·log₁₀(P_carrier / P_noise)

### 3. 3dB Bandwidth (Hz)
**What:** Width of signal at half-power points
**Why:** FM broadcast should be 180-220 kHz (±75 kHz deviation + pilot/RDS)
**Threshold:**
- Too narrow (<150 kHz) → Capture issue or weak signal
- Too wide (>250 kHz) → Interference or wrong modulation

### 4. Adjacent Channel Rejection (dB)
**What:** Power ratio between carrier and ±200 kHz adjacent channels
**Why:** Detects filter quality and adjacent-channel bleed
**Threshold:**
- `< 10 dB` → Poor selectivity, interference risk
- `≥ 15 dB` → Good rejection

### 5. Rolloff Asymmetry (ratio)
**What:** Left vs right spectral slope (dB/100kHz from ±100 to ±150 kHz)
**Why:** Symmetric rolloff (~1.0x) is clean. Asymmetry (>2.0x) suggests Doppler, multipath, or transmitter issues.
**Threshold:**
- `< 1.5x` → Symmetric, clean signal
- `> 2.5x` → Investigate for interference

## Database Schema

```sql
CREATE TABLE fingerprints (
    id INTEGER PRIMARY KEY,
    capture_id INTEGER NOT NULL,            -- FK to captures table
    peak_freq_hz REAL NOT NULL,             -- Interpolated carrier peak (RF Hz)
    freq_error_hz REAL,                     -- Offset from tuner center
    cnr_db REAL NOT NULL,                   -- Carrier-to-noise ratio
    bandwidth_3db_hz REAL NOT NULL,         -- 3dB bandwidth
    adjacent_rejection_db REAL NOT NULL,    -- Adjacent channel rejection
    rolloff_left_slope REAL,                -- dB/100kHz on left side
    rolloff_right_slope REAL,               -- dB/100kHz on right side
    rolloff_asymmetry REAL,                 -- max(L,R) / min(L,R)
    processing_time_sec REAL,               -- Feature extraction time
    FOREIGN KEY(capture_id) REFERENCES captures(id) ON DELETE CASCADE
);
```

## Usage Examples

### Example 1: Validate station consistency

```python
import sqlite3
from database.sqlite_logger import DB_PATH

conn = sqlite3.connect(DB_PATH)
cursor = conn.execute("""
    SELECT peak_freq_hz, cnr_db, bandwidth_3db_hz
    FROM fingerprints
    WHERE capture_id IN (
        SELECT id FROM captures WHERE center_freq_hz = 105900000
    )
""")

for row in cursor:
    peak_mhz = row[0] / 1e6
    cnr = row[1]
    bw_khz = row[2] / 1e3
    print(f"Peak: {peak_mhz:.6f} MHz, CNR: {cnr:.1f} dB, BW: {bw_khz:.1f} kHz")
```

### Example 2: Flag low-quality captures

```python
# Find captures with CNR < 18 dB (unreliable fine features)
cursor = conn.execute("""
    SELECT c.file_path, f.cnr_db
    FROM captures c
    JOIN fingerprints f ON c.id = f.capture_id
    WHERE f.cnr_db < 18.0
    ORDER BY f.cnr_db ASC
""")

print("Low-quality captures (CNR < 18 dB):")
for path, cnr in cursor:
    print(f"  {path}: {cnr:.1f} dB")
```

### Example 3: Detect frequency drift

```python
# Track peak frequency over time for station stability
cursor = conn.execute("""
    SELECT c.timestamp, f.peak_freq_hz
    FROM captures c
    JOIN fingerprints f ON c.id = f.capture_id
    WHERE c.center_freq_hz = 105900000
    ORDER BY c.timestamp ASC
""")

import numpy as np
freqs = [row[1] for row in cursor]
drift_hz = np.std(freqs)
print(f"Frequency drift (std dev): {drift_hz:.1f} Hz")
# Good: < 100 Hz, Investigate: > 500 Hz
```

## Implementation Details

### PSD Computation (Welch's Method)

```python
from scipy.signal import welch

f, P = welch(
    iq_data,
    fs=sample_rate,
    nperseg=4096,      # 586 Hz/bin at 2.4 Msps
    noverlap=2048,     # 50% overlap for variance reduction
    window='hann',     # Sidelobe suppression
    return_onesided=False,
    scaling='density'  # Power per Hz (not power per bin)
)
```

**Why these parameters?**
- `nperseg=4096`: Balance between frequency resolution (586 Hz/bin) and noise averaging
- `noverlap=2048`: Reduces variance without excessive computation
- `return_onesided=False`: Keeps full spectrum for baseband IQ data
- `scaling='density'`: Required for consistent CNR math (power per Hz)

### Parabolic Peak Interpolation

```python
p = np.log(psd + 1e-30)  # Work in log domain
k = np.argmax(p)         # Max bin index

# 3-point quadratic vertex offset (lines 86-90: fm_fingerprint.py)
delta = 0.5 * (p[k-1] - p[k+1]) / (p[k-1] - 2*p[k] + p[k+1])

# Convert bin offset to Hz
bin_hz = freqs[1] - freqs[0]
peak_hz = freqs[k] + delta * bin_hz
```

**Why log domain?**
PSD spans 40+ dB. Linear fit would be dominated by peak bin. Log space treats bins equally.

### CNR: Why Match Bandwidth?

```python
# WRONG: Different bandwidths
carrier_power = sum(psd[±50kHz])      # 100 kHz window
noise_density = mean(psd[quiet_bins]) # per-Hz
cnr = carrier_power / noise_density   # Mixed units!

# CORRECT: Matched bandwidth
carrier_power = sum(psd[±50kHz])                    # 100 kHz window
noise_power = noise_density * (100e3 / df)          # Scale to 100 kHz
cnr = 10 * log10(carrier_power / noise_power)       # Valid ratio
```

## Practical Thresholds

| Metric                | Good          | Marginal       | Bad              |
|-----------------------|---------------|----------------|------------------|
| **CNR**               | ≥25 dB        | 18-25 dB       | <18 dB           |
| **3dB BW**            | 180-220 kHz   | 150-250 kHz    | <150 or >250 kHz |
| **Adj. Rejection**    | ≥20 dB        | 15-20 dB       | <15 dB           |
| **Rolloff Asymmetry** | <1.5x         | 1.5-2.5x       | >2.5x            |
| **Freq. Drift (σ)**   | <100 Hz       | 100-500 Hz     | >500 Hz          |

## Troubleshooting

### "CNR is always 100 dB"
- Check if you're using `scaling='spectrum'` instead of `scaling='density'`
- Verify noise bins aren't all zero (increase `noise_keep_pct`)

### "Peak frequency jumps by ±586 Hz"
- Parabolic interpolation failed (check edge cases)
- Verify you're using log domain for fit, not linear

### "Bandwidth always 0.0 Hz"
- Peak power too close to noise floor (low CNR)
- Try longer captures (5 sec vs 3 sec) for better SNR

### "Adjacent rejection is negative"
- Adjacent channels are stronger than carrier (wrong frequency tuned)
- Or massive interference from neighboring station

## Next Steps: Tier 2 Features

- **Pilot tone stability**: 19 kHz deviation over time
- **Stereo separation**: L-R channel power ratio
- **RDS bit error rate**: Decode and validate RDS data
- **Instantaneous frequency**: Phase derivative for FM deviation histogram

## References
- [Welch's Method (OG)](https://ieeexplore.ieee.org/stamp/stamp.jsp?tp=&arnumber=1161901)
- [Parabolic Interpolation](https://ccrma.stanford.edu/STANM/stanms/stanm43/stanm43.pdf)
- [Minimum Statistics](https://ieeexplore.ieee.org/stamp/stamp.jsp?arnumber=928915)
- [Spectrum Sensing for Cognitive Radio](https://ieeexplore.ieee.org/stamp/stamp.jsp?tp=&arnumber=8125907)