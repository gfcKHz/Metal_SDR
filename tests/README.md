# Metal_SDR Validation Framework

Regression tests for RF fingerprinting validation as specified in the blog post requirements.

## Installation

Install test dependencies:

```bash
pip install pytest
# or with uv
uv pip install pytest
```

## Running Tests

Run all tests:
```bash
pytest tests/ -v
```

Run specific test class:
```bash
pytest tests/test_fm_fingerprint.py::TestCNRAccuracy -v
```

Run with coverage:
```bash
pytest tests/ --cov=scripts/fingerprinting -v
```

## Test Coverage

### CNR Accuracy (`TestCNRAccuracy`)
- **Requirement**: CNR extraction accuracy within ±2 dB tolerance
- Tests synthetic signals with known SNR (10, 20, 30, 40 dB)
- Validates dimensional consistency across FFT lengths

### Frequency Accuracy (`TestFrequencyAccuracy`)
- **Requirement**: Frequency precision within ±100 Hz
- Tests parabolic peak interpolation at various frequency offsets
- High SNR signals for sub-bin accuracy validation

### Adjacent-Channel Rejection (`TestAdjacentChannelRejection`)
- Validates correct left/right channel measurement (bug fix: right_center)
- Tests dimensional consistency (mean vs sum)
- Verifies ≥15 dB rejection threshold

### PSD Bin-Width Scaling (`TestPSDBinWidthScaling`)
- Validates correct conversion from PSD (W/Hz) to total power
- Tests formula: P = (∑ S[k]) × Δf

### Bandwidth Measurement (`TestBandwidthMeasurement`)
- Validates deterministic 3dB bandwidth measurement
- Ensures consistency across multiple runs

## Expected Results

All tests should pass with the corrected implementations:
- CNR calculation uses mean power density (not sum vs mean)
- Welch noverlap = 2048 (50% of nperseg=4096)
- Adjacent rejection uses + for right channel (not -)
- RTL-SDR normalization divides by 128.0 (not 127.5)

## Continuous Integration

To integrate with CI/CD:

```yaml
# .github/workflows/test.yml
name: Tests
on: [push, pull_request]
jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3
      - uses: actions/setup-python@v4
        with:
          python-version: '3.10'
      - run: pip install -e .[dev]
      - run: pytest tests/ -v
```
