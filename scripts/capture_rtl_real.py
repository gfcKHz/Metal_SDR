#!/usr/bin/env python3
import subprocess
import numpy as np
from pathlib import Path
import time
import tempfile
from config import CAPTURES_DIR 
from capture_sigmf import process_capture, log_to_kuzu 

def capture_rtl_sdr(duration=5, center_freq=142.0e6, sample_rate=2.4e6, gain=20):
    """
    Capture using stable rtl_sdr.exe binary via subprocess
    """
    print(f"🎯 Capturing {duration}s at {center_freq/1e6:.1f} MHz via rtl_sdr.exe...")
    
    # calculate samples needed
    samples_needed = int(duration * sample_rate)
    
    # create temporary file for raw I/Q data
    with tempfile.NamedTemporaryFile(suffix='.iq', delete=False) as temp_file:
        temp_path = temp_file.name
    
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
        
        print(f"   Command: {' '.join(cmd)}")
        print(f"   Samples: {samples_needed:,}")
        
        # execute capture
        start_time = time.time()
        
        # increase timeout buffer from 5 to 10 seconds
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=duration + 10)
        capture_time = time.time() - start_time
        
        if result.returncode != 0:
            print(f"❌ Capture failed: {result.stderr}")
            return None, None
        
        """
        We de-interleave (un-shuffle) with stride slicing. This is the same step gnu radio's
        interleaved_char_to_complex block performs internally
        """ 
        # [🌀]: I/Q conversion(zero-copy, O(2) memory)
        print("   Converting raw bytes to complex64...")
        raw = np.fromfile(temp_path, dtype=np.uint8)           # flat [I0, Q0, I1, Q1,...]
        
        # [🌀]: correct conversion logic: uint8 -> float32 [-1, 1] -> complex64
        iq_float = (raw.astype(np.float32) - 127.5) / 127.5
        I = iq_float[0::2]
        Q = iq_float[1::2]
        iq = I + 1j * Q 

        """
        # I/Q conversion(zero-copy, O(2) memory)
        print("   Converting raw bytes to complex64...")
        raw = np.fromfile(temp_path, dtype=np.uint8)           # flat [I0, Q0, I1, Q1,...]
        iq = raw.astype(np.float32).view(np.complex64)         # zero-copy reinterpret
        iq -= 127.5 + 127.5j                                   # remove DC in complex form  
        iq /= 127.5                                            # normalize to [-1, 1]
        """ 
        
        print(f"✅ Capture successful: {len(iq):,} samples in {capture_time:.2f}s")
        
        # save as SigMF
        capture_info = process_capture(
            iq_data=iq,
            center_freq=center_freq,
            sample_rate=sample_rate,
            output_dir=CAPTURES_DIR
        )
        
        # log to kuzu 
        log_to_kuzu(capture_info)
        
        return capture_info["data_path"], capture_info["meta_path"] 
        
    except subprocess.TimeoutExpired:
        print("❌ Capture timed out")
        return None, None
    except Exception as e:
        print(f"❌ Capture failed: {e}")
        return None, None
    finally:
        # clean up temp file
        if Path(temp_path).exists():
            Path(temp_path).unlink()

if __name__ == "__main__":
    # test the stable capture
    data_path, meta_path = capture_rtl_sdr(
        duration=3,
        center_freq=100e6,
        sample_rate=2.4e6,
        gain=20
    )
    
    if data_path:
        print(f"✅ Stable capture working!")
        print(f"   Data: {data_path}")
        print(f"   Meta: {meta_path}")