# Metal_SDR Pipeline Documentation

## Overview

This document describes the end-to-end pipeline for RF signal capture, fingerprinting, spectrum sensing, and cognitive radio applications in Metal_SDR.

## Pipeline Stages

1. **Capture**
   - Use `batch_capture.py` with --backend (rtl-sdr or bladerf).
   - Outputs SigMF files in data/captures/.

2. **Fingerprinting**
   - Use `process_fingerprints.py` or specific extractors (e.g., fm_fingerprint.py).
   - Features stored in database.

## Example Workflow

```bash
# Capture with BladeRF
python scripts/capture/batch_capture.py --backend bladerf --freq 1.8e9 --sample-rate 20e6

# Fingerprint
python scripts/fingerprinting/fm_fingerprint.py path/to/capture.sigmf-meta