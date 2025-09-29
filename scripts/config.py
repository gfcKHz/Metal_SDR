# config.py
from pathlib import Path
import kuzu
import tempfile

# --- Centralized Pipeline Paths ---
BASE_DIR = Path("D:/dataset/sdr-pipeline")
DATA_DIR = BASE_DIR / "data"
CAPTURES_DIR = DATA_DIR / "captures"
KUZU_DIR = DATA_DIR / "kuzu_db"

# kuzu Database
KUZU_DB_PATH = KUZU_DIR / "sdr_graph"
KUZU_DB_PATH.mkdir(parents=True, exist_ok=True)

# set global temp directory to a folder on drive
TEMP_DIR = DATA_DIR / "temp_iq"
TEMP_DIR.mkdir(parents=True, exist_ok=True)
tempfile.tempdir = str(TEMP_DIR)

# Create kuzu connection
def get_kuzu_connection():
    return kuzu.Connection(KUZU_DB_PATH)

print(f"✅ kuzu config loaded: {BASE_DIR}")