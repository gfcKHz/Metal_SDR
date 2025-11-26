# Usage Guide

Unified workflows for capture, fingerprinting, and testing.

---

## Pipeline Overview

1. **Capture**  
   `scripts/capture/batch_capture.py --backend {rtl-sdr,bladerf}` → SigMF pairs in `data/captures/`.
2. **Fingerprinting**  
   `scripts/fingerprinting/process_fingerprints.py` (or `fm_fingerprint.py`, `lte_fingerprint.py`) → features stored in DB.
3. **(WIP) Sensing / Cognitive**  
   Energy/cyclostationary detectors and `dynamic_access.py` for spectrum allocation experiments.

### Example end-to-end

```bash
# Capture with BladeRF
python scripts/capture/batch_capture.py --backend bladerf --freq 1.8e9 --sample-rate 20e6

# Fingerprint
python scripts/fingerprinting/fm_fingerprint.py path/to/capture.sigmf-meta
```

---

## Capture Usage

### List available backends

```bash
cd scripts/capture
python batch_capture.py --list-backends
```

### RTL-SDR examples

Single capture:
```bash
python batch_capture.py --backend rtl-sdr --freq 105.9e6 --sample-rate 2.4e6 --duration 3 --gain 20 --num-captures 1
```

Batch captures:
```bash
python batch_capture.py --backend rtl-sdr --freq 105.9e6 --num-captures 10 --interval 300
```

Common RTL-SDR frequencies:
| Signal | Frequency | Flag |
|--------|-----------|------|
| FM Broadcast | 88–108 MHz | `--freq 105.9e6` |
| ADS-B | 1090 MHz | `--freq 1090e6` |
| LoRa ISM (US) | 915 MHz | `--freq 915e6` |
| Pagers | 929 MHz | `--freq 929e6` |

### BladeRF examples

LTE capture:
```bash
python batch_capture.py --backend bladerf --freq 1.8e9 --sample-rate 20e6 --duration 5 --gain 30
```

WiFi (2.4 GHz):
```bash
python batch_capture.py --backend bladerf --freq 2.437e9 --sample-rate 40e6 --duration 2
```

WiFi (5 GHz):
```bash
python batch_capture.py --backend bladerf --freq 5.18e9 --sample-rate 40e6 --duration 2
```

### Command reference

Required:
| Flag | Description | Example |
|------|-------------|---------|
| `--freq` | Center frequency (Hz) | `105.9e6` |

Optional:
| Flag | Default | Description |
|------|---------|-------------|
| `--backend` | `rtl-sdr` | SDR hardware to use |
| `--sample-rate` | `2.4e6` | Sample rate (Hz) |
| `--duration` | `3` | Capture duration (seconds) |
| `--gain` | `20` | Gain (dB) |
| `--num-captures` | `10` | Number of captures |
| `--interval` | `300` | Interval between captures (seconds) |
| `--list-backends` | - | List available backends and exit |

---

## Testing Guide

### Phase 1: Basic functionality

- **Backend listing**
  ```bash
  cd scripts/capture
  python batch_capture.py --list-backends
  ```
  Expect rtl-sdr available; bladerf unavailable until installed.

- **RTL-SDR capture**
  ```bash
  python batch_capture.py --backend rtl-sdr --freq 105.9e6 --num-captures 1
  ```
  Expect SigMF files in `data/captures/` and DB entry.

- **BladeRF error handling (pre-driver)**
  ```bash
  python batch_capture.py --backend bladerf --freq 2.4e9 --num-captures 1
  ```
  Expect clear Install/driver message.

### Phase 2: Edge cases

- Invalid backend:
  ```bash
  python batch_capture.py --backend invalid --freq 105.9e6
  ```
- Out-of-range RTL-SDR frequency:
  ```bash
  python batch_capture.py --backend rtl-sdr --freq 10e9
  ```
- Backward compatibility: process existing captures
  ```bash
  cd scripts/fingerprinting
  python process_fingerprints.py
  ```
  And confirm schema:
  ```bash
  sqlite3 ../../data/captures/capture_manifest.db ".schema captures"
  ```

### Phase 3: Integration

End-to-end:
```bash
cd scripts/capture
python batch_capture.py --backend rtl-sdr --freq 105.9e6 --num-captures 1

cd ../fingerprinting
python process_fingerprints.py
```
Verify latest capture+fingerprint via SQLite:
```bash
sqlite3 ../../data/captures/capture_manifest.db <<EOF
SELECT c.id,
       c.center_freq_hz/1e6 AS freq_mhz,
       f.peak_freq_hz/1e6 AS peak_mhz,
       f.cnr_db
FROM captures c
LEFT JOIN fingerprints f ON c.id = f.capture_id
ORDER BY c.id DESC
LIMIT 1;
EOF
```
