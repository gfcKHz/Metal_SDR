#!/usr/bin/env python3
import time
from capture_rtl_real import capture_rtl_sdr

def batch_capture(
    num_captures: int = 10,
    interval_sec: int = 300,  # 5 minutes
    center_freq: float = 105.9e6,
    sample_rate: float = 1.2e6,
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
        print(f"\n=== Capture {i+1}/{num_captures} ===")

        data, meta = capture_rtl_sdr(
            duration=duration,
            center_freq=center_freq,
            sample_rate=sample_rate,
            notes=f"Batch {i+1}/{num_captures}"
        )

        if data:
            print(f"✓ Capture {i+1} complete: {data.name}")
        else:
            print(f"✗ Capture {i+1} failed")

        # Wait before next capture (except after last one)
        if i < num_captures - 1:
            print(f"Waiting {interval_sec}s until next capture...")
            time.sleep(interval_sec)

    print(f"\n✓ Batch complete: {num_captures} captures done")

if __name__ == "__main__":
    import sys

    # CLI: python batch_capture.py [num_captures] [interval_sec] [freq_mhz] [rate_msps] [duration]
    num = int(sys.argv[1]) if len(sys.argv) > 1 else 10
    interval = int(sys.argv[2]) if len(sys.argv) > 2 else 300
    freq = float(sys.argv[3]) if len(sys.argv) > 3 else 105.9
    rate = float(sys.argv[4]) if len(sys.argv) > 4 else 1.2
    dur = int(sys.argv[5]) if len(sys.argv) > 5 else 3

    batch_capture(
        num_captures=num,
        interval_sec=interval,
        center_freq=freq * 1e6,
        sample_rate=rate * 1e6,
        duration=dur
    )
