# Usage Guide

## Hardware Abstraction Layer

The capture system supports multiple SDR backends through a common interface. Switch between hardware using the `--backend` flag.

---

## Listing Available Backends

```bash
cd scripts/capture
python batch_capture.py --list-backends
```

**Output**:
```
Available SDR backends:
  rtl-sdr: available
  bladerf: unavailable: bladeRF Python library not installed
```

---

## RTL-SDR Usage

### Single Capture

```bash
python batch_capture.py \
    --backend rtl-sdr \
    --freq 105.9e6 \
    --sample-rate 2.4e6 \
    --duration 3 \
    --gain 20 \
    --num-captures 1
```

### Batch Capture

```bash
# 10 captures, 5 minute intervals
python batch_capture.py \
    --backend rtl-sdr \
    --freq 105.9e6 \
    --num-captures 10 \
    --interval 300
```

### Common RTL-SDR Frequencies

| Signal Type | Frequency | Command |
|-------------|-----------|---------|
| FM Broadcast | 88-108 MHz | `--freq 105.9e6` |
| ADS-B Aircraft | 1090 MHz | `--freq 1090e6` |
| LoRa ISM (US) | 915 MHz | `--freq 915e6` |
| Pagers | 929 MHz | `--freq 929e6` |

---

## BladeRF Usage (Future)

### LTE Capture

```bash
python batch_capture.py \
    --backend bladerf \
    --freq 1.8e9 \
    --sample-rate 20e6 \
    --duration 5 \
    --gain 30
```

### WiFi 2.4 GHz Capture

```bash
python batch_capture.py \
    --backend bladerf \
    --freq 2.437e9 \
    --sample-rate 40e6 \
    --duration 2
```

### WiFi 5 GHz Capture

```bash
python batch_capture.py \
    --backend bladerf \
    --freq 5.18e9 \
    --sample-rate 40e6 \
    --duration 2
```

---

## Command Reference

### Required Arguments

| Flag | Description | Example |
|------|-------------|---------|
| `--freq` | Center frequency (Hz) | `105.9e6` |

### Optional Arguments

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