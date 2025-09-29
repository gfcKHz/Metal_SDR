#!/usr/bin/env python3
from config import get_kuzu_connection

def analyze_frequency_correlations():
    """Find frequencies that often appear together"""
    conn = get_kuzu_connection()
    
    print("📡 Frequency Co-occurrence Analysis")
    print("=" * 50)
    
    # find frequencies that appear within 5 minutes of each other
    result = conn.execute("""
        MATCH (c1:Capture)-[:AT_FREQUENCY]->(f1:Frequency),
              (c2:Capture)-[:AT_FREQUENCY]->(f2:Frequency),
              (c1)-[near:OCCURS_NEAR]-(c2)
        WHERE f1.mhz != f2.mhz AND near.time_diff_ms < 300000
        RETURN f1.mhz as freq1, f2.mhz as freq2, COUNT(*) as co_occurrences
        ORDER BY co_occurrences DESC
        LIMIT 10
    """)
    
    print("Top frequency co-occurrences:")
    for row in result:
        print(f"  {row['freq1']} MHz ↔ {row['freq2']} MHz: {row['co_occurrences']}x")
    
    # temporal patterns
    print("\n🕒 Temporal Activity Patterns:")
    result = conn.execute("""
        MATCH (f:Frequency)<-[:AT_FREQUENCY]-(c:Capture)
        RETURN f.mhz as frequency, 
               COUNT(*) as total_captures,
               MIN(c.timestamp) as first_seen,
               MAX(c.timestamp) as last_seen
        ORDER BY total_captures DESC
    """)
    
    for row in result:
        print(f"  {row['frequency']} MHz: {row['total_captures']} captures "
              f"({row['first_seen'].strftime('%m/%d')} - {row['last_seen'].strftime('%m/%d')})")
    
    conn.close()

def find_anomalies():
    """Find unusual patterns using graph traversal"""
    conn = get_kuzu_connection()
    
    print("\n🔍 Anomaly Detection:")
    
    # find isolated frequencies (few connections)
    result = conn.execute("""
        MATCH (f:Frequency)<-[:AT_FREQUENCY]-(c:Capture)
        WITH f, COUNT(c) as capture_count
        WHERE capture_count < 3
        RETURN f.mhz as isolated_freq, capture_count
        ORDER BY capture_count ASC
    """)
    
    print("Infrequent (possibly anomalous) frequencies:")
    for row in result:
        print(f"  {row['isolated_freq']} MHz: {row['capture_count']} captures")
    
    conn.close()

if __name__ == "__main__":
    analyze_frequency_correlations()
    find_anomalies()