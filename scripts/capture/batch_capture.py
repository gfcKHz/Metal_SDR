#!/usr/bin/env python3
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

import time
from capture.capture_rtl_real import capture_rtl_sdr

def batch_capture(
    num_captures: int = 10,
    interval_sec: int = 300,  # 5 minutes
    center_freq: float = 105.9e6,
    sample_rate: float = 2.4e6,
    duration: int = 3
):
    """
    Run multiple captures with time intervals between them.

    Args:
        num_captures: Number of captures to perform
        interval_sec: Seconds to wait between captures
        center_freq: Center frequency in Hz
        sample_rate: Sample rate in Hz
        duration: Capture duration in seconds
    """
    print(f"Starting batch capture: {num_captures} captures, {interval_sec}s interval")
    print(f"Frequency: {center_freq/1e6:.1f} MHz, Rate: {sample_rate/1e6:.1f} Msps")

    for i in range(num_captures):
        print(f"\nCapture {i+1}/{num_captures} ===")

        data, meta = capture_rtl_sdr(
            duration=duration,
            center_freq=center_freq,
            sample_rate=sample_rate,
            notes=f"Batch {i+1}/{num_captures}"
        )

        if data:
            print(f"Capture {i+1} complete: {data.name}")
        else:
            print(f"Capture {i+1} failed")

        # Wait before next capture (except after last one)
        if i < num_captures - 1:
            print(f"Waiting {interval_sec}s until next capture...")
            time.sleep(interval_sec)

    print(f"\nBatch complete: {num_captures} captures done")

if __name__ == "__main__":
      import argparse

      parser = argparse.ArgumentParser(description="Batch capture IQ samples from RTL-SDR")
      parser.add_argument("--num-captures", type=int, default=10, help="Number of captures (default: 10)")
      parser.add_argument("--interval", type=int, default=300, help="Interval between captures in seconds (default: 300)")
      parser.add_argument("--freq", type=float, default=105.9e6, help="Center frequency in Hz (default: 105.9 MHz)")
      parser.add_argument("--sample-rate", type=float, default=2.4e6, help="Sample rate in Hz (default: 2.4 MHz)")
      parser.add_argument("--duration", type=int, default=3, help="Capture duration in seconds (default: 3)")

      args = parser.parse_args()

      batch_capture(
          num_captures=args.num_captures,
          interval_sec=args.interval,
          center_freq=args.freq,
          sample_rate=args.sample_rate,
          duration=args.duration
      )