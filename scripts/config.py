from pathlib import Path
import tempfile
import platform

# Cross-platform base directory
if platform.system() == "Windows":
    BASE_DIR = Path("D:/dataset/sdr-pipeline")
    DATA_DIR = BASE_DIR / "data"
else:
    # Use project root's data directory on Unix systems
    BASE_DIR = Path(__file__).parent.parent
    DATA_DIR = BASE_DIR / "data"

CAPTURES_DIR = DATA_DIR / "captures"

# temp IQ buffer
TEMP_DIR      = DATA_DIR / "temp_iq"
TEMP_DIR.mkdir(parents=True, exist_ok=True)
tempfile.tempdir = str(TEMP_DIR)