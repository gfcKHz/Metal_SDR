# Hardware Abstraction Refactor Plan

## Overview

Refactor the capture system to support multiple SDR backends (RTL-SDR, BladeRF) through a common interface. This enables adding new hardware without changing downstream code.

## Current Status

- ✅ README updated with hardware-agnostic architecture
- ✅ Fingerprinting system (already hardware-agnostic)
- ⏳ Capture system (currently RTL-SDR specific)

## Goals

1. Create abstract `SDRBackend` interface
2. Implement `RTLSDRBackend` (refactor existing code)
3. Create `BladeRFBackend` skeleton (for future hardware)
4. Update `batch_capture.py` to use backends via CLI flag
5. Maintain backward compatibility

---

## Folder Structure

```
scripts/capture/
├── capture_manager.py          # NEW - Abstract interface + factory
├── backends/                   # NEW - Hardware implementations
│   ├── __init__.py
│   ├── rtl_sdr.py             # NEW - RTL-SDR backend
│   └── bladerf.py             # NEW - BladeRF backend (skeleton)
├── batch_capture.py           # UPDATE - Use new architecture
├── capture_rtl_real.py        # KEEP (legacy, for reference)
└── capture_sigmf.py           # KEEP (already generic)
```

---

## Implementation

### 1. Create `capture_manager.py`

**File**: `scripts/capture/capture_manager.py`

```python
#!/usr/bin/env python3
"""
Hardware-agnostic RF capture manager

Supports multiple SDR backends via plugin architecture.
"""

from abc import ABC, abstractmethod
from pathlib import Path
import numpy as np

class SDRBackend(ABC):
    """Abstract base class for SDR hardware backends"""

    @abstractmethod
    def capture(self, center_freq: float, sample_rate: float,
                duration: float, gain: float) -> np.ndarray:
        """
        Capture IQ samples

        Args:
            center_freq: Center frequency in Hz
            sample_rate: Sample rate in Hz
            duration: Capture duration in seconds
            gain: Gain in dB

        Returns:
            Complex numpy array of IQ samples (complex64)
        """
        pass

    @abstractmethod
    def get_supported_sample_rates(self) -> list:
        """Return list of supported sample rates in Hz"""
        pass

    @abstractmethod
    def get_frequency_range(self) -> tuple:
        """Return (min_freq, max_freq) in Hz"""
        pass

    @property
    @abstractmethod
    def name(self) -> str:
        """Return backend name (e.g., 'rtl-sdr', 'bladerf')"""
        pass

def get_backend(backend_name: str) -> SDRBackend:
    """
    Factory function to get SDR backend by name

    Args:
        backend_name: 'rtl-sdr', 'bladerf', etc.

    Returns:
        SDRBackend instance

    Raises:
        ValueError: If backend_name is unknown
        ImportError: If backend dependencies not installed
    """
    backend_name = backend_name.lower()

    if backend_name == "rtl-sdr":
        from backends.rtl_sdr import RTLSDRBackend
        return RTLSDRBackend()

    elif backend_name == "bladerf":
        from backends.bladerf import BladeRFBackend
        return BladeRFBackend()

    else:
        raise ValueError(
            f"Unknown backend: {backend_name}. "
            f"Supported: rtl-sdr, bladerf"
        )

def list_backends() -> dict:
    """
    List all available backends and their status

    Returns:
        dict mapping backend name to availability status
    """
    backends = {}

    # RTL-SDR
    try:
        from backends.rtl_sdr import RTLSDRBackend
        backends['rtl-sdr'] = 'available'
    except ImportError as e:
        backends['rtl-sdr'] = f'unavailable: {e}'

    # BladeRF
    try:
        from backends.bladerf import BladeRFBackend
        backends['bladerf'] = 'available'
    except ImportError as e:
        backends['bladerf'] = f'unavailable: {e}'

    return backends
```

---

### 2. Create `backends/__init__.py`

**File**: `scripts/capture/backends/__init__.py`

```python
"""SDR hardware backend implementations"""

__all__ = ['rtl_sdr', 'bladerf']
```

---

### 3. Create `backends/rtl_sdr.py`

**File**: `scripts/capture/backends/rtl_sdr.py`

```python
#!/usr/bin/env python3
"""RTL-SDR hardware backend"""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from capture.capture_manager import SDRBackend
import subprocess
import numpy as np
import tempfile
import platform
from pathlib import Path

class RTLSDRBackend(SDRBackend):
    """RTL-SDR backend using rtl_sdr binary"""

    @property
    def name(self) -> str:
        return "rtl-sdr"

    def get_frequency_range(self) -> tuple:
        """RTL-SDR frequency range"""
        return (24e6, 1766e6)  # 24 MHz - 1.766 GHz

    def get_supported_sample_rates(self) -> list:
        """RTL-SDR supports flexible rates, 2.4 Msps is standard"""
        return [2.4e6, 2.048e6, 1.024e6]

    def capture(self, center_freq: float, sample_rate: float,
                duration: float, gain: float) -> np.ndarray:
        """
        Capture using rtl_sdr binary

        Args:
            center_freq: Center frequency in Hz
            sample_rate: Sample rate in Hz
            duration: Capture duration in seconds
            gain: Gain in dB

        Returns:
            Complex IQ samples as complex64 numpy array

        Raises:
            RuntimeError: If rtl_sdr binary fails
        """
        # Validate frequency range
        min_freq, max_freq = self.get_frequency_range()
        if not (min_freq <= center_freq <= max_freq):
            raise ValueError(
                f"Frequency {center_freq/1e6:.1f} MHz out of range "
                f"for RTL-SDR: {min_freq/1e6:.1f} - {max_freq/1e6:.1f} MHz"
            )

        samples_needed = int(duration * sample_rate)

        # Create temporary file for raw I/Q data
        with tempfile.NamedTemporaryFile(suffix='.iq', delete=False) as tmp:
            temp_path = tmp.name

        try:
            # Build rtl_sdr command (cross-platform)
            rtl_sdr_binary = "rtl_sdr.exe" if platform.system() == "Windows" else "rtl_sdr"
            cmd = [
                rtl_sdr_binary,
                "-f", str(int(center_freq)),
                "-s", str(int(sample_rate)),
                "-n", str(samples_needed),
                "-g", str(int(gain)),
                temp_path
            ]

            print(f"[RTL-SDR] Command: {' '.join(cmd)}")

            # Execute capture
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=duration + 10
            )

            if result.returncode != 0:
                raise RuntimeError(f"rtl_sdr failed: {result.stderr}")

            # Verify temp file exists and has data
            temp_file = Path(temp_path)
            if not temp_file.exists():
                raise RuntimeError(f"Temp file not created at {temp_path}")

            file_size = temp_file.stat().st_size
            if file_size == 0:
                raise RuntimeError("Temp file is empty")

            print(f"[RTL-SDR] Captured {file_size:,} bytes")

            # Convert uint8 to complex IQ
            # RTL-SDR outputs interleaved I/Q as uint8 [I, Q, I, Q, ...]
            raw = np.fromfile(temp_path, dtype=np.uint8)

            # Normalize to [-1.0, 1.0]
            iq_float = (raw.astype(np.float32) - 127.5) / 127.5

            # De-interleave: I = even indices, Q = odd indices
            iq = iq_float[0::2] + 1j * iq_float[1::2]

            print(f"[RTL-SDR] Converted {len(iq):,} complex samples")

            return iq.astype(np.complex64)

        finally:
            # Clean up temp file
            try:
                Path(temp_path).unlink(missing_ok=True)
            except Exception as e:
                print(f"[RTL-SDR] Warning: Could not delete temp file: {e}")
```

---

### 4. Create `backends/bladerf.py`

**File**: `scripts/capture/backends/bladerf.py`

```python
#!/usr/bin/env python3
"""BladeRF 2.0 hardware backend (skeleton for future implementation)"""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from capture.capture_manager import SDRBackend
import numpy as np

class BladeRFBackend(SDRBackend):
    """BladeRF 2.0 backend using bladeRF Python API"""

    def __init__(self):
        """Initialize BladeRF backend"""
        try:
            import bladerf
            self.bladerf = bladerf
            print("[BladeRF] Python library loaded")
        except ImportError:
            raise ImportError(
                "bladeRF Python library not installed. "
                "Install with: pip install bladerf"
            )

    @property
    def name(self) -> str:
        return "bladerf"

    def get_frequency_range(self) -> tuple:
        """BladeRF 2.0 xA9 frequency range"""
        return (47e6, 6e9)  # 47 MHz - 6 GHz

    def get_supported_sample_rates(self) -> list:
        """BladeRF 2.0 supports up to 61.44 Msps"""
        return [
            2.4e6,    # Compatible with RTL-SDR captures
            5e6,
            10e6,
            20e6,
            40e6,
            61.44e6   # Max sample rate
        ]

    def capture(self, center_freq: float, sample_rate: float,
                duration: float, gain: float) -> np.ndarray:
        """
        Capture using bladeRF Python API

        NOTE: This is a skeleton implementation. Actual implementation
        will be completed when hardware is acquired.

        Args:
            center_freq: Center frequency in Hz
            sample_rate: Sample rate in Hz
            duration: Capture duration in seconds
            gain: Gain in dB

        Returns:
            Complex IQ samples as complex64 numpy array

        Raises:
            NotImplementedError: Until hardware is available
        """
        raise NotImplementedError(
            "BladeRF backend not yet implemented. "
            "Waiting for hardware acquisition. "
            "\n\n"
            "Future implementation will:\n"
            "  1. Open bladeRF device: dev = bladerf.BladeRF()\n"
            "  2. Configure RX channel: dev.sample_rate = sample_rate\n"
            "  3. Set frequency: dev.frequency = center_freq\n"
            "  4. Set gain: dev.gain = gain\n"
            "  5. Capture samples: samples = dev.sync_rx(num_samples)\n"
            "  6. Return normalized complex64 array\n"
        )

        # Placeholder for future implementation:
        #
        # # Validate frequency range
        # min_freq, max_freq = self.get_frequency_range()
        # if not (min_freq <= center_freq <= max_freq):
        #     raise ValueError(f"Frequency out of range")
        #
        # # Open device
        # dev = self.bladerf.BladeRF()
        #
        # # Configure RX channel
        # ch = dev.Channel(self.bladerf.CHANNEL_RX(0))
        # ch.sample_rate = sample_rate
        # ch.frequency = center_freq
        # ch.gain = gain
        # ch.bandwidth = sample_rate  # Set filter to sample rate
        #
        # # Calculate samples needed
        # num_samples = int(duration * sample_rate)
        #
        # # Capture
        # samples = dev.sync_rx(num_samples, timeout_ms=int(duration * 1000 + 5000))
        #
        # # BladeRF returns int16, normalize to complex64
        # # (exact normalization depends on bladeRF output format)
        # iq = samples.astype(np.complex64) / 2048.0  # Typical for 12-bit ADC
        #
        # return iq
```

---

### 5. Update `batch_capture.py`

**File**: `scripts/capture/batch_capture.py` (UPDATE)

**Changes needed**:
1. Import `get_backend` instead of `capture_rtl_sdr`
2. Add `--backend` CLI argument
3. Use backend to capture instead of direct function call

```python
#!/usr/bin/env python3
"""
Hardware-agnostic batch capture

Supports multiple SDR backends via --backend flag
"""

import argparse
import time
from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).parent.parent))

from capture.capture_manager import get_backend, list_backends
from capture.capture_sigmf import process_capture
from database.sqlite_logger import log_to_sqlite
from utils.config import CAPTURES_DIR

def batch_capture(
    backend: str = "rtl-sdr",
    num_captures: int = 10,
    interval_sec: int = 300,
    center_freq: float = 105.9e6,
    sample_rate: float = 2.4e6,
    duration: int = 3,
    gain: int = 20
):
    """
    Run multiple captures with time intervals

    Args:
        backend: SDR backend ('rtl-sdr', 'bladerf')
        num_captures: Number of captures
        interval_sec: Seconds between captures
        center_freq: Center frequency in Hz
        sample_rate: Sample rate in Hz
        duration: Capture duration in seconds
        gain: Gain in dB
    """
    print(f"Starting batch capture: {num_captures} captures, {interval_sec}s interval")
    print(f"Backend: {backend}")
    print(f"Frequency: {center_freq/1e6:.1f} MHz, Rate: {sample_rate/1e6:.1f} Msps")
    print()

    # Get SDR backend
    try:
        sdr = get_backend(backend)
    except (ValueError, ImportError) as e:
        print(f"ERROR: {e}")
        print("\nAvailable backends:")
        for name, status in list_backends().items():
            print(f"  {name}: {status}")
        return

    # Validate parameters
    min_freq, max_freq = sdr.get_frequency_range()
    if not (min_freq <= center_freq <= max_freq):
        print(f"ERROR: Frequency {center_freq/1e6:.1f} MHz out of range for {backend}")
        print(f"       Supported range: {min_freq/1e6:.1f} - {max_freq/1e6:.1f} MHz")
        return

    for i in range(num_captures):
        print(f"=== Capture {i+1}/{num_captures} ===")

        try:
            # Capture IQ data using backend
            iq_data = sdr.capture(center_freq, sample_rate, duration, gain)

            # Save as SigMF
            capture_info = process_capture(
                iq_data=iq_data,
                center_freq=center_freq,
                sample_rate=sample_rate,
                output_dir=CAPTURES_DIR
            )

            # Add metadata
            capture_info["gain_db"] = gain
            capture_info["duration_sec"] = duration
            capture_info["notes"] = f"Batch {i+1}/{num_captures} via {sdr.name}"

            # Log to database
            capture_id = log_to_sqlite(capture_info)
            print(f"Capture {i+1} complete: {capture_info['data_path'].name} (ID: {capture_id})")

        except Exception as e:
            print(f"Capture {i+1} failed: {e}")
            import traceback
            traceback.print_exc()

        # Wait before next capture
        if i < num_captures - 1:
            print(f"Waiting {interval_sec}s until next capture...\n")
            time.sleep(interval_sec)

    print(f"\nBatch complete: {num_captures} captures done")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Batch capture from SDR hardware",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # RTL-SDR: Capture FM station
  python batch_capture.py --backend rtl-sdr --freq 105.9e6 --sample-rate 2.4e6

  # BladeRF: Capture LTE band (future)
  python batch_capture.py --backend bladerf --freq 1.8e9 --sample-rate 20e6

  # List available backends
  python batch_capture.py --list-backends
        """
    )

    parser.add_argument(
        "--backend",
        type=str,
        default="rtl-sdr",
        help="SDR backend to use (default: rtl-sdr)"
    )
    parser.add_argument(
        "--list-backends",
        action="store_true",
        help="List available backends and exit"
    )
    parser.add_argument("--num-captures", type=int, default=10,
                       help="Number of captures (default: 10)")
    parser.add_argument("--interval", type=int, default=300,
                       help="Interval between captures in seconds (default: 300)")
    parser.add_argument("--freq", type=float, default=105.9e6,
                       help="Center frequency in Hz (default: 105.9 MHz)")
    parser.add_argument("--sample-rate", type=float, default=2.4e6,
                       help="Sample rate in Hz (default: 2.4 Msps)")
    parser.add_argument("--duration", type=int, default=3,
                       help="Capture duration in seconds (default: 3)")
    parser.add_argument("--gain", type=int, default=20,
                       help="Gain in dB (default: 20)")

    args = parser.parse_args()

    # Handle --list-backends
    if args.list_backends:
        print("Available SDR backends:")
        for name, status in list_backends().items():
            print(f"  {name}: {status}")
        sys.exit(0)

    batch_capture(
        backend=args.backend,
        num_captures=args.num_captures,
        interval_sec=args.interval,
        center_freq=args.freq,
        sample_rate=args.sample_rate,
        duration=args.duration,
        gain=args.gain
    )
```

---

## Usage Examples

### List available backends

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

### Capture with RTL-SDR (current)

```bash
# Single FM station capture
python batch_capture.py \
    --backend rtl-sdr \
    --freq 105.9e6 \
    --sample-rate 2.4e6 \
    --duration 3 \
    --gain 20 \
    --num-captures 1

# Batch capture (10 captures, 5 min intervals)
python batch_capture.py \
    --backend rtl-sdr \
    --freq 105.9e6 \
    --num-captures 10 \
    --interval 300
```

### Capture with BladeRF (future)

```bash
# LTE capture (when hardware available)
python batch_capture.py \
    --backend bladerf \
    --freq 1.8e9 \
    --sample-rate 20e6 \
    --duration 5 \
    --gain 30

# WiFi 2.4 GHz capture
python batch_capture.py \
    --backend bladerf \
    --freq 2.437e9 \
    --sample-rate 40e6 \
    --duration 2
```

---

## Testing Plan

### Phase 1: Basic Functionality

1. **Test backend listing**:
   ```bash
   python batch_capture.py --list-backends
   ```
   - Should show rtl-sdr as available
   - Should show bladerf as unavailable (until hardware acquired)

2. **Test RTL-SDR capture** (existing functionality):
   ```bash
   python batch_capture.py --backend rtl-sdr --freq 105.9e6 --num-captures 1
   ```
   - Should capture successfully
   - Should create .sigmf-data/.sigmf-meta files
   - Should log to database

3. **Test BladeRF error handling**:
   ```bash
   python batch_capture.py --backend bladerf --freq 2.4e9 --num-captures 1
   ```
   - Should raise NotImplementedError with helpful message

### Phase 2: Edge Cases

1. **Invalid backend**:
   ```bash
   python batch_capture.py --backend invalid --freq 105.9e6
   ```
   - Should error with list of available backends

2. **Out of range frequency**:
   ```bash
   python batch_capture.py --backend rtl-sdr --freq 10e9
   ```
   - Should error: "Frequency out of range for RTL-SDR"

3. **Backward compatibility**:
   - Old captures should still work
   - Database schema unchanged
   - Fingerprinting pipeline unaffected

---

## Migration Notes

### Backward Compatibility

- `capture_rtl_real.py` kept for reference (not deleted)
- All existing .sigmf-data files work unchanged
- Database schema unchanged
- No changes needed to fingerprinting scripts

### Future Hardware Addition

To add new SDR hardware (e.g., HackRF, USRP):

1. Create `backends/hackrf.py`
2. Implement `SDRBackend` interface
3. Add to `get_backend()` factory in `capture_manager.py`
4. Update `list_backends()`
5. **No other code changes needed**

---

## Quick Start for Next Session

```bash
# 1. Create directory structure
cd scripts/capture
mkdir -p backends

# 2. Create files in this order:
# - capture_manager.py
# - backends/__init__.py
# - backends/rtl_sdr.py
# - backends/bladerf.py
# - Update batch_capture.py

# 3. Test
python batch_capture.py --list-backends
python batch_capture.py --backend rtl-sdr --freq 105.9e6 --num-captures 1

# 4. Verify
# - Check .sigmf-data files created
# - Check database entry added
# - Run fingerprinting on new capture
cd ../fingerprinting
python process_fingerprints.py
```

---

## Success Criteria

- ✅ `batch_capture.py --backend rtl-sdr` works exactly like before
- ✅ New captures are bit-identical to old captures
- ✅ `--list-backends` shows available hardware
- ✅ BladeRF skeleton exists with helpful NotImplementedError
- ✅ All existing scripts (fingerprinting, database) work unchanged
- ✅ README architecture matches implementation

---

## Notes

- All code uses absolute imports from project root
- Type hints used throughout for clarity
- Error messages are helpful and actionable
- Cross-platform support (Windows/macOS/Linux)
- No breaking changes to existing functionality
