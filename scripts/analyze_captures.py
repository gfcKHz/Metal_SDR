import duckdb
from config import DB_PATH

def main():
    con = duckdb.connect(str(DB_PATH))
    print(con.sql("""
        SELECT  center_freq_mhz,
                COUNT(*)        as n,
                MIN(timestamp)  as first,
                MAX(timestamp)  as last,
                SUM(file_size_mb) as total_mb
        FROM captures
        GROUP BY center_freq_mhz
        ORDER BY center_freq_mhz
    """).to_pandas())
    con.close()

if __name__ == "__main__":
    main()