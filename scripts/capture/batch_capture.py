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