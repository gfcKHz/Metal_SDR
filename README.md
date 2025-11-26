# Metal_SDR

Hardware-agnostic RF signal fingerprinting, classification, spectrum sensing, and cognitive radio pipeline.

## Current System Overview

**Purpose**: Capture, fingerprint, sense, and classify RF signals using modular SDR backends. Store captures in SigMF format with SQLite manifest. Support modulation classification, spectrum sensing, and cognitive radio applications like dynamic spectrum access.

**Hardware**:
- RTL-SDR: FM broadcast, ADS-B, LoRa (24 MHz - 1.7 GHz, 2.4 Msps)
- BladeRF 2.0: LTE, WiFi, wideband signals (47 MHz - 6 GHz, up to 61.44 Msps)

**Signals**: FM broadcast (current), LTE/WiFi (extensible via fingerprinting modules)

## Architecture

(Updated architecture diagram here, incorporating sensing and cognitive layers)

## Components

### Capture Scripts
- `batch_capture.py`: Hardware-agnostic batch captures with --backend flag (rtl-sdr or bladerf).

### Fingerprinting
- Generalized with `base_fingerprint.py`.
- `fm_fingerprint.py`: FM-specific features.
- `lte_fingerprint.py`: LTE features (skeleton).

### Database and Utils
- `sqlite_logger.py`: Log captures.
- `analyze_captures.py`: Summary statistics.

## Usage

See `docs/PIPELINE.md` for detailed workflows.

### Example: BladeRF Capture and Fingerprint
```bash
python scripts/capture/batch_capture.py --backend bladerf --freq 1.8e9 --sample-rate 20e6
python scripts/fingerprinting/lte_fingerprint.py path/to/capture.sigmf-meta
```

(Rest of the original content, updated as needed for limitations, data format, etc.)
