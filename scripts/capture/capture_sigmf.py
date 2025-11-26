#!/usr/bin/env python3
import blake3 
import uuid
from datetime import datetime
from pathlib import Path

import numpy as np
import sigmf 
from sigmf import SigMFFile 

def calculate_file_hash(file_path):
    """calculate BLAKE3 hash of file content"""
    hasher = blake3.blake3()
    # explicitly convert Path to string
    with open(str(file_path), 'rb') as f:
        for chunk in iter(lambda: f.read(4096), b""):
            hasher.update(chunk)
    return hasher.hexdigest()

# public API
def process_capture(
    iq_data: np.ndarray,
    center_freq: float, 
    sample_rate: float, 
    output_dir: Path,
) -> dict:
    """Write IQ as SigMF pair, return metadata dict for SQLite"""
    output_dir.mkdir(parents=True, exist_ok=True)
    
    stem = output_dir / f"capture_{datetime.now():%Y%m%d_%H%M%S}_{int(center_freq/1e6)}Mhz"

    # 1. build metadata - do not pass data_file to constructor
    sig = SigMFFile(
        global_info={
            "core:datatype": "cf32_le",
            "core:sample_rate": sample_rate,
            "core:version": "1.0.0",
            "core:description": f"RTL-SDR @{center_freq/1e6:.1f} MHz",
            "core:author": "sp7der",
            "core:license": "CC0",
        },
    )
    sig.add_capture(0, metadata={
        "core:frequency": center_freq,
        "core:datetime": datetime.now().isoformat() + "Z"
    })

    # 2. define final paths first 
    data_path = stem.with_suffix(".sigmf-data")
    meta_path = stem.with_suffix(".sigmf-meta")

    # 3. write IQ data directly to file
    iq_data.tofile(str(data_path))
    
    # 4. calculate hash *after* disk write
    data_hash = calculate_file_hash(data_path)

    # 5. update metadata with hash and write meta file
    sig.set_global_field("core:blake3", data_hash)

    # 6. link the data file and write meta file
    sig.set_data_file(str(data_path))
    sig.tofile(str(meta_path))
    
    print(f"[SigMF]  {data_path.name}  ({data_path.stat().st_size/1e6:.1f} MB)")
    return {
        "id": str(uuid.uuid4()),
        "timestamp": datetime.now(),
        "center_freq": center_freq,
        "sample_rate": sample_rate,
        "data_path": data_path,
        "meta_path": meta_path,
        "data_hash": data_hash,
        "file_size_mb": data_path.stat().st_size / (1024 * 1024),
    }