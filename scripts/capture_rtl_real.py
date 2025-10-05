#!/usr/bin/env python3
import subprocess
import numpy as np
from pathlib import Path
import time
import tempfile

from config import CAPTURES_DIR
from capture_sigmf import process_capture
from sqlite_logger import log_to_sqlite

def capture_rtl_sdr(
    duration: int = 5,
    center_freq: int = 142.0e6,
    sample_rate: int = 2.4e6,
    gain: int = 20,
    notes: str = "",
):
    """
    Capture IQ via rtl_sdr.exe, convert to SigMF, log to SQLite
    """
    print(f"Capturing {duration}s at {center_freq/1e6:.1f} MHz")
    
    # calculate samples needed
    samples_needed = int(duration * sample_rate)
    
    # create temporary file for raw I/Q data
    with tempfile.NamedTemporaryFile(suffix='.iq', delete=False) as tmp:
        temp_path = tmp.name
    
    try:
        # build rtl_sdr command
        cmd = [
            "rtl_sdr.exe",
            "-f", str(int(center_freq)),
            "-s", str(int(sample_rate)), 
            "-n", str(samples_needed),
            "-g", str(gain),
            temp_path
        ]
        print("Cmd:", " ".join(cmd))
        
        # time the real capture for throughput and hang detection  
        t0 = time.time()
        result = subprocess.run(
            cmd, capture_output=False, timeout=duration + 10
        )
        capture_time = time.time() - t0
         
        if result.returncode != 0:
            print(f"Capture failed: {result.stderr}")
            return None, None
        
        # verify the temp file was created and has data
        temp_file = Path(temp_path)
        if not temp_file.exists():
            print(f"ERROR: Temp file not created at {temp_path}")
            return None, None
    
        file_size = temp_file.stat().st_size
        if file_size == 0:
            print(f"ERROR: Temp file is empty")
            return None, None
        
        print(f"Temp file created: {file_size:,} bytes")
        
        # [🌀]: we de-interleave (un-shuffle) with stride slicing. this is the same step gnu radio's
        # interleaved_char_to_complex block performs internally
        raw = np.fromfile(temp_path, dtype=np.uint8)

        iq_float = (raw.astype(np.float32) - 127.5) / 127.5
        iq = iq_float[0::2] + 1j * iq_float[1::2]
        
        print(f"Converted {len(iq):,} complex samples in {capture_time:.2f}s")

        # SigMF artefact
        capture_info = process_capture(
            iq_data=iq,
            center_freq=center_freq,
            sample_rate=sample_rate,
            output_dir=CAPTURES_DIR
        )

        # Add capture parameters for SQLite logging
        capture_info["gain_db"] = gain
        capture_info["duration_sec"] = duration
        capture_info["notes"] = notes

        # SQLite manifest
        capture_id = log_to_sqlite(capture_info)

        return capture_info["data_path"], capture_info["meta_path"]
    
    except subprocess.TimeoutExpired:
        print("Capture timed out")
        return None, None
    except Exception as e:
        print(f"Capture error: {e}")
        import traceback
        traceback.print_exc()
        return None, None
    finally:
        try:
            Path(temp_path).unlink(missing_ok=True)
        except Exception as e:
            print(f"Warning: Could not delete temp file: {e}")

if __name__ == "__main__":
    data, meta = capture_rtl_sdr(duration=3, center_freq=100e6, sample_rate=2.4e6)
    if data:
        print("Success -> data:", data.name, "meta:", meta.name)
