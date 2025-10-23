# Testing Guide

## Hardware Abstraction Layer Testing

Verify that the hardware abstraction layer works correctly across backends and handles edge cases.

---

## Phase 1: Basic Functionality

### Test 1: Backend Listing

```bash
cd scripts/capture
python batch_capture.py --list-backends
```

**Expected output**:
```
Available SDR backends:
  rtl-sdr: available
  bladerf: unavailable: bladeRF Python library not installed
```

**Pass criteria**:
- Shows rtl-sdr as available
- Shows bladerf as unavailable (until hardware acquired)
- No errors or exceptions

---

### Test 2: RTL-SDR Capture

```bash
python batch_capture.py --backend rtl-sdr --freq 105.9e6 --num-captures 1
```

**Pass criteria**:
- Capture completes successfully
- Creates `.sigmf-data` and `.sigmf-meta` files in `data/captures/`
- Logs entry to SQLite database
- Console shows:
  - `[RTL-SDR] Command: rtl_sdr -f ...`
  - `[RTL-SDR] Captured X bytes`
  - `[RTL-SDR] Converted Y complex samples`
  - `Capture 1 complete: capture_YYYYMMDD_HHMMSS.sigmf-data (ID: N)`

**Verification**:
```bash
# Check files created
ls -lh ../../data/captures/*.sigmf-*

# Check database entry
sqlite3 ../../data/captures/capture_manifest.db \
  "SELECT id, center_freq_hz, sample_rate_hz, file_path FROM captures ORDER BY id DESC LIMIT 1;"
```

---

### Test 3: BladeRF Error Handling

```bash
python batch_capture.py --backend bladerf --freq 2.4e9 --num-captures 1
```

**Expected output**:
```
ERROR: bladeRF Python library not installed. Install with: pip install bladerf

Available backends:
  rtl-sdr: available
  bladerf: unavailable: bladeRF Python library not installed
```

**Pass criteria**:
- Raises ImportError with helpful installation message
- Lists available backends
- Exits gracefully (no crash)

---

## Phase 2: Edge Cases

### Test 4: Invalid Backend

```bash
python batch_capture.py --backend invalid --freq 105.9e6
```

**Expected output**:
```
ERROR: Unknown backend: invalid. Supported: rtl-sdr, bladerf

Available backends:
  rtl-sdr: available
  bladerf: unavailable: ...
```

**Pass criteria**:
- Shows clear error message
- Lists supported backends
- Exits gracefully

---

### Test 5: Out of Range Frequency (RTL-SDR)

```bash
# Too high (RTL-SDR max is 1.766 GHz)
python batch_capture.py --backend rtl-sdr --freq 10e9
```

**Expected output**:
```
ERROR: Frequency 10000.0 MHz out of range for rtl-sdr
       Supported range: 24.0 - 1766.0 MHz
```

**Pass criteria**:
- Catches frequency out of range before attempting capture
- Shows valid frequency range for backend
- Exits gracefully

---

### Test 6: Backward Compatibility

**Test existing captures still work**:

```bash
# Process old captures with fingerprinting
cd ../fingerprinting
python process_fingerprints.py
```

**Pass criteria**:
- Old .sigmf-data files load successfully
- Fingerprinting extracts features without errors
- Database queries work unchanged

**Test database schema**:

```bash
sqlite3 ../../data/captures/capture_manifest.db \
  ".schema captures"
```

**Pass criteria**:
- Schema unchanged from before refactor
- All columns present: id, timestamp, center_freq_hz, sample_rate_hz, etc.

---

## Phase 3: Integration Testing

### Test 7: End-to-End Pipeline

```bash
# Capture → Process → Fingerprint
cd scripts/capture
python batch_capture.py --backend rtl-sdr --freq 105.9e6 --num-captures 1

cd ../fingerprinting
python process_fingerprints.py
```

**Pass criteria**:
- Capture creates .sigmf-data file
- Database logs capture
- Fingerprinting extracts features
- Database contains fingerprint entry

**Verification**:
```bash
sqlite3 ../../data/captures/capture_manifest.db <<EOF
SELECT
  c.id,
  c.center_freq_hz/1e6 as freq_mhz,
  f.peak_freq_hz/1e6 as peak_mhz,
  f.cnr_db
FROM captures c
LEFT JOIN fingerprints f ON c.id = f.capture_id
ORDER BY c.id DESC
LIMIT 1;
EOF
```

**Expected**: Shows capture with associated fingerprint

---

## Phase 4: Stress Testing

### Test 8: Multi-Capture Batch

```bash
# Small batch to verify stability
python batch_capture.py \
  --backend rtl-sdr \
  --freq 105.9e6 \
  --num-captures 5 \
  --interval 10
```

**Pass criteria**:
- All 5 captures complete successfully
- No memory leaks (monitor with `top` or `htop`)
- Temp files cleaned up after each capture
- Database contains 5 new entries

---

## Test Summary Checklist

- [ ] Backend listing shows correct availability
- [ ] RTL-SDR capture works (creates files, logs to DB)
- [ ] BladeRF raises helpful error (until hardware available)
- [ ] Invalid backend shows clear error message
- [ ] Out-of-range frequency caught before capture
- [ ] Old captures still work with fingerprinting
- [ ] Database schema unchanged
- [ ] End-to-end pipeline works (capture → fingerprint)
- [ ] Multi-capture batch completes successfully
- [ ] No memory leaks or temp file buildup

---

## Regression Testing

Before any commit that modifies capture code, run:

```bash
# Quick regression test
cd scripts/capture
python batch_capture.py --list-backends
python batch_capture.py --backend rtl-sdr --freq 105.9e6 --num-captures 1

cd ../fingerprinting
python process_fingerprints.py --file "../../data/captures/capture_*.sigmf-data"
```

All tests should pass with no errors.
