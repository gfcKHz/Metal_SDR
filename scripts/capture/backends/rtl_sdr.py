#!/usr/bin/env python3
"""RTL-SDR hardware backend"""

import platform
import subprocess
import tempfile
from pathlib import Path

import numpy as np

from ..capture_manager import SDRBackend

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

        # create temp file for raw IQ data
        with tempfile.NamedTemporaryFile(suffix='.iq', delete=False) as tmp:
            temp_path = tmp.name

        try:
            # Build rtl_sdr command (cross-platform)
            rtl_sdr_binary = "rtl_sdr.exe" if platform.system() == "Windows" else "rtl_sdr"
            cmd = [
                rtl_sdr_binary,
                "-f", str(int(center_freq)),
                "-s", str(int(sample_rate)),
                "-n", str(int(samples_needed)),
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

            # Convert uint to complex IQ
            # RTL-SDR outputs interleaved IQ as uint8 [I, Q, I, Q, ...]
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
