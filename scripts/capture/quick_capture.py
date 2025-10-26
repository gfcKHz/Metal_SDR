#!/usr/bin/env python3
import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from capture.capture_manager import get_backend
from capture.capture_sigmf import process_capture
from database.sqlite_logger import init_db, log_to_sqlite
from utils.config import CAPTURES_DIR


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Capture a single SigMF recording using an SDR backend."
    )
    parser.add_argument(
        "--backend",
        default="rtl_sdr",
        help="Backend identifier (default: rtl_sdr).",
    )
    parser.add_argument(
        "--freq",
        type=float,
        default=105.9,
        help="Center frequency in MHz (default: 105.9).",
    )
    parser.add_argument(
        "--sample-rate",
        type=float,
        default=2.4,
        help="Sample rate in Msps (default: 2.4).",
    )
    parser.add_argument(
        "--duration",
        type=float,
        default=3.0,
        help="Capture duration in seconds (default: 3).",
    )
    parser.add_argument(
        "--gain",
        type=float,
        default=20.0,
        help="Frontend gain in dB (default: 20).",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=CAPTURES_DIR,
        help=f"Directory for SigMF files (default: {CAPTURES_DIR}).",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()

    backend = get_backend(args.backend)

    center_freq_hz = args.freq * 1e6
    sample_rate_hz = args.sample_rate * 1e6
    duration_sec = args.duration
    gain_db = args.gain

    # Validate frequency range before capturing
    min_freq, max_freq = backend.get_frequency_range()
    if not (min_freq <= center_freq_hz <= max_freq):
        raise ValueError(
            f"Frequency {center_freq_hz/1e6:.3f} MHz out of range for {backend.name} "
            f"({min_freq/1e6:.3f} - {max_freq/1e6:.3f} MHz)"
        )

    print(
        f"[QuickCapture] Backend={backend.name}, "
        f"Freq={center_freq_hz/1e6:.3f} MHz, "
        f"Rate={sample_rate_hz/1e6:.3f} Msps, "
        f"Duration={duration_sec:.2f} s, Gain={gain_db} dB"
    )

    iq_data = backend.capture(
        center_freq=center_freq_hz,
        sample_rate=sample_rate_hz,
        duration=duration_sec,
        gain=gain_db,
    )

    # Ensure manifest database is ready
    init_db()

    capture_info = process_capture(
        iq_data=iq_data,
        center_freq=center_freq_hz,
        sample_rate=sample_rate_hz,
        output_dir=args.output_dir,
    )

    capture_info["gain_db"] = gain_db
    capture_info["duration_sec"] = duration_sec
    capture_info["notes"] = f"Quick capture via {backend.name}"

    capture_id = log_to_sqlite(capture_info)

    print(
        f"[QuickCapture] Saved capture #{capture_id}: "
        f"{capture_info['data_path'].name} ({capture_info['file_size_mb']:.2f} MB)"
    )


if __name__ == "__main__":
    main()
