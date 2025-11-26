#!/usr/bin/env python3
"""Dedicated BladeRF Capture Script"""

import argparse
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent))

from backends.bladerf import BladeRFBackend
from capture_sigmf import process_capture
from database.sqlite_logger import log_to_sqlite
from utils.config import CAPTURES_DIR

def capture_blade(
    duration: int = 5,
    center_freq: int = 1.8e9,
    sample_rate: int = 20e6,
    gain: int = 30,
    notes: str = "",
):
    """
    Capture IQ via BladeRF, convert to SigMF, log to SQLite
    """
    print(f"Capturing {duration}s at {center_freq/1e6:.1f} MHz with BladeRF")
    
    backend = BladeRFBackend()
    iq_data = backend.capture(center_freq, sample_rate, duration, gain)
    
    capture_info = process_capture(
        iq_data=iq_data,
        center_freq=center_freq,
        sample_rate=sample_rate,
        output_dir=CAPTURES_DIR
    )

    capture_info["gain_db"] = gain
    capture_info["duration_sec"] = duration
    capture_info["notes"] = notes

    capture_id = log_to_sqlite(capture_info)

    return capture_info["data_path"], capture_info["meta_path"]

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Capture IQ samples from BladeRF")
    parser.add_argument("--freq", type=float, default=1.8e9, help="Center frequency in Hz (default: 1.8 GHz)")
    parser.add_argument("--duration", type=int, default=5, help="Capture duration in seconds (default: 5)")
    parser.add_argument("--sample-rate", type=float, default=20e6, help="Sample rate in Hz (default: 20 MHz)")
    parser.add_argument("--gain", type=int, default=30, help="Gain in dB (default: 30)")
    parser.add_argument("--notes", type=str, default="", help="Notes for this capture")

    args = parser.parse_args()
    
    data, meta = capture_blade(
        duration=args.duration,
        center_freq=args.freq,
        sample_rate=args.sample_rate,
        gain=args.gain,
        notes=args.notes
    )
    if data:
        print("Success -> data: ", data.name, "meta:", meta.name)
