#!/usr/bin/env python3
import hashlib
import uuid
from datetime import datetime
from pathlib import Path

import numpy as np
import sigmf 
from sigmf import SigMFFile 

def calculate_file_hash(file_path):
    """calculate SHA-256 hash of file content"""
    hasher = hashlib.sha256()
    # ensure the path is treated as an absolute path string when opening
    with open(file_path, 'rb') as f:
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
    """Write IQ as SigMF pair, return metadata dict for DuckDB"""
    output_dir.mkdir(parents=True, exist_ok=True)
    
    stem = output_dir / f"capture_{datetime.now():%Y%m%d_%H%M%S}_{int(center_freq/1e6)}Mhz"

    # 1. build metadata
    sig = SigMFFile(
        data_file=f"{stem.name}.sigmf-data",
        global_info={
            "core:datatype": "cf32_le",
            "core:sample_rate": sample_rate,
            "core:version": "1.0.0",
            "core:description": f"RTL-SDR @{center_freq/1e6:.1f} MHz",
            "core:author": "sp7der",
            "core:license": "CC0",
        },
    )
    sig.add_capture(0, metadata={"core:frequency": center_freq, "core:datetime": datetime.now().isoformat() + "Z"})

    # 2. write data file
    sig.tofile(str(stem), data_array=iq_data)   # stem -> adds .sigmf-data
    
    # 3. final paths
    data_path = stem.with_suffix(".sigmf-data")
    meta_path = stem.with_suffix(".sigmf-meta")
    
    # 4. hash *after* disk write
    data_hash = _sha256(data_path)
    sig.global_info["core:sha256"] = data_hash
    sig.write_to_file(str(meta_path))           # overwrite meta with hash
    
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