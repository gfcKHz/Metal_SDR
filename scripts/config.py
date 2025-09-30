from pathlib import Path
import tempfile

BASE_DIR      = Path("D:/dataset/sdr-pipeline")
DATA_DIR      = BASE_DIR / "data"
CAPTURES_DIR  = DATA_DIR / "captures"
MANIFESTS_DIR = DATA_DIR / "manifests"
DB_PATH       = MANIFESTS_DIR / "capture_manifest.duckdb"

# temp IQ buffer
TEMP_DIR      = DATA_DIR / "temp_iq"
TEMP_DIR.mkdir(parents=True, exist_ok=True)
tempfile.tempdir = str(TEMP_DIR)

print(f"[CONFIG] DuckDB mode - DB at {DB_PATH}")