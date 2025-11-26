from pathlib import Path
import tempfile
import platform
import os

# Project root (metal_sdr/)
PROJECT_ROOT = Path(__file__).parent.parent.parent

# RTL-SDR tools path configuration
# Priority: 1) local_config.py, 2) environment variable, 3) system PATH
RTL_SDR_PATH = None
try:
    from utils.local_config import RTL_SDR_PATH
except ImportError:
    # Fall back to environment variable
    if "RTL_SDR_PATH" in os.environ:
        RTL_SDR_PATH = Path(os.environ["RTL_SDR_PATH"])

# Dataset directory (persistent storage for captures and database)
# Can be synced to cloud storage - see dataset/README.md for setup
DATASET_DIR = PROJECT_ROOT / "dataset"
CAPTURES_DIR = DATASET_DIR / "captures"

# Local data directory (temporary files, not tracked by git)
DATA_DIR = PROJECT_ROOT / "data"
TEMP_DIR = DATA_DIR / "temp_iq"

# Ensure directories exist
CAPTURES_DIR.mkdir(parents=True, exist_ok=True)
TEMP_DIR.mkdir(parents=True, exist_ok=True)

# Set temp directory for tempfile module
tempfile.tempdir = str(TEMP_DIR)