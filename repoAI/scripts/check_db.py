"""
check_db.py - Inspect OpenCode SQLite database structure
Usage: python scripts/check_db.py
"""
import sqlite3

conn = sqlite3.connect(r'C:\Users\hp\.local\share\opencode\opencode.db')
cursor = conn.cursor()

# List tables
cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
tables = [r[0] for r in cursor.fetchall()]
print("Tables:", tables)

# Check each table for conversation data
for table in tables:
    try:
        cursor.execute(f"SELECT COUNT(*) FROM [{table}]")
        count = cursor.fetchone()[0]
        print(f"\n{table}: {count} rows")

        # Get column names
        cursor.execute(f"PRAGMA table_info([{table}])")
        cols = [r[1] for r in cursor.fetchall()]
        print(f"  Columns: {cols}")

        # Show first 2 rows
        if count > 0:
            cursor.execute(f"SELECT * FROM [{table}] LIMIT 2")
            for i, row in enumerate(cursor.fetchall()):
                print(f"  Row {i}: {str(row)[:200]}")
    except Exception as e:
        print(f"  Error: {e}")

conn.close()
