#!/usr/bin/env python3
import numpy as np
import hashlib
import sigmf
from sigmf import SigMFFile
from datetime import datetime
from pathlib import Path
from config import get_kuzu_connection
import uuid

def calculate_file_hash(file_path):
    """calculate SHA-256 hash of file content"""
    hasher = hashlib.sha256()
    # ensure the path is treated as an absolute path string when opening
    with open(file_path, 'rb') as f:
        for chunk in iter(lambda: f.read(4096), b""):
            hasher.update(chunk)
    return hasher.hexdigest()

def process_capture(iq_data, center_freq, sample_rate, output_dir):
    """
    save as SigMF and return capture info for graph (storage)
    """
    output_dir.mkdir(parents=True, exist_ok=True)
    
    timestamp_str = datetime.now().strftime("%Y%m%d_%H%M%S")
    freq_mhz = int(center_freq / 1e6)
    unique_name = f"capture_{timestamp_str}_{freq_mhz}Mhz"

    # define the STEM path (dir, unique_name, NO extension)
    full_path_stem = output_dir / unique_name
    
    # global metadata
    global_info = {
        "core:datatype": "cf32_le",
        "core:sample_rate": sample_rate,
        "core:version": "1.0.0",
        "core:description": f"RTL-SDR capture at {center_freq/1e6:.1f} Mhz",
        "core:author": "sp7der",
        "core:recorder": "RTL-SDR",
        "core:license": "CC0",
    }
  
    """
    # create full paths for both data and meta files
    data_filename = f"{unique_name}.sigmf-data"
    data_path = output_dir / data_filename
    
    # pass the full path to SigMFFile constructor
    sigmf_file = SigMFFile(
        data_file=str(data_path),    # FIX: use full path here 
        global_info=global_info
    )
    """
    # 1. instantiate SigMFFile. data_file is ONLY the relative name
    # we must ensure this matches the name the file will be saved under
    sigmf_file = SigMFFile(
        data_file=f"{unique_name}.sigmf-data",
        global_info=global_info
    )
    
    # add capture remains
    sigmf_file.add_capture(
        sample_start=0, 
        metadata={
            "core:frequency": center_freq,
            "core:datetime": datetime.now().isoformat() + "Z"
        }
    )
    
    # 2. write the file: pass the stem to tofile(). this library adds the extension
    sigmf_file.tofile(str(full_path_stem), data_array=iq_data) # CRITICAL FIX 1: pass stem 

    # 3. define the final, absolute paths after writing
    data_path = full_path_stem.with_suffix('.sigmf-data')
    meta_path = full_path_stem.with_suffix('.sigmf-data')
    
    # 4. calculate hash and update metadata: CRITICAL FIX 2: ensure we hash the file that
    # was just written. the absolute path string should now work
    data_hash = calculate_file_hash(str(data_path.resolve()))
    sigmf_file.global_info["core:sha256"] = data_hash

    # 5. write metadata file: use SigMFFile's write_to_file to save the meta file
    # with the hash. this overwrites the meta file written to tofile()
    sigmf_file.write_to_file(str(meta_path)) # CRITICAL FIX 3: use final path
    
    print(f"✓ SigMF capture: {data_path.name}")

    # return capture info for graph
    return {
        "id": str(uuid.uuid4()),
        "timestamp": datetime.now(),
        "center_freq": center_freq,
        "sample_rate": sample_rate,
        "data_path": data_path,
        "meta_path": meta_path,
        "data_hash": data_hash,
        "file_size_mb": data_path.stat().st_size / (1024 * 1024)
    }

def log_to_kuzu(capture_info):
    """Log capture to kuzu graph database (indexing and processing)"""
    conn = get_kuzu_connection()
    
    # create capture node
    conn.execute("""
        CREATE (c:Capture {
            id: $id,
            timestamp: $timestamp,
            sample_rate_mhz: $sample_rate_mhz,
            file_size_mb: $file_size_mb,
            data_sha256: $data_sha256,
            raw_file_path: $raw_file_path
        })
    """, {
        "id": capture_info["id"],
        "timestamp": capture_info["timestamp"],
        "sample_rate_mhz": capture_info["sample_rate"] / 1e6,
        "file_size_mb": capture_info["file_size_mb"],
        "data_sha256": capture_info["data_hash"],
        "raw_file_path": str(capture_info["data_path"])
    })
    
    # connect to frequency node
    conn.execute("""
        MATCH (c:Capture {id: $capture_id}), (f:Frequency {mhz: $freq_mhz})
        CREATE (c)-[r:AT_FREQUENCY {signal_strength: $strength}]->(f)
    """, {
        "capture_id": capture_info["id"],
        "freq_mhz": capture_info["center_freq"] / 1e6,
        "strength": 1.0  # placeholder for actual signal analysis
    })
    
    # connect to hardware node
    conn.execute("""
        MATCH (c:Capture {id: $capture_id})
        CREATE (c)-[r:USING_HARDWARE]->(h:Hardware {type: $hw_type, serial_number: $serial})
    """, {
        "capture_id": capture_info["id"],
        "hw_type": "RTL-SDR",
        "serial": "default"
    })
    
    # create temporal relationships with recent captures
    conn.execute("""
        MATCH (current:Capture {id: $current_id})
        MATCH (recent:Capture) 
        WHERE recent.id != $current_id 
          AND abs(recent.timestamp - current.timestamp) < 300000  // 5 minutes
        CREATE (current)-[r:OCCURS_NEAR {
            time_diff_ms: abs(recent.timestamp - current.timestamp),
            freq_diff_mhz: abs($current_freq - recent.sample_rate_mhz)
        }]->(recent)
    """, {
        "current_id": capture_info["id"],
        "current_freq": capture_info["center_freq"] / 1e6
    })
    
    print(f"✓ Logged to kuzu graph: {capture_info['data_path'].name}")
    conn.close()