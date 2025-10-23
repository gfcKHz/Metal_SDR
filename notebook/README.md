# Measurement Validation 

This directory contains notebooks documenting measurement issues discovered during development and their solutions.

## fm_repeatability_test.ipynb

**Problem**: Wide-bandwidth captures (2.4 MHz) show unstable peak frequency measurements.

**Cause**: Multiple FM stations within capture bandwidth. Different signals dominate at different times, causing peak frequency to drift by ±0.8 MHz across repeated captures.

**Solution**:
- Use narrower capture bandwidth focused on single station
- OR implement multi-peak tracking to identify all stations in bandwidth
- This discovery led to the parabolic peak interpolation feature (±50 Hz accuracy) in `fm_fingerprint.py`

**Key Finding**: Even for captures of the same station, peak frequency shows ±0.005-0.007 MHz variation due to FFT bin quantization. This validated the need for sub-bin interpolation (parabolic fit on log-power spectrum).

**Impact**:
- Demonstrated that raw FFT bin centers are insufficient for frequency tracking
- Informed the design of the CNR estimation (MPA) to reject spurious peaks
- Validated temporal consistency requirements for fingerprinting system

