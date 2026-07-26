"""
extract_messages.py - Extract all user messages from OpenCode SQLite database
Usage: python scripts/extract_messages.py
"""
import sqlite3
import json

conn = sqlite3.connect(r'C:\Users\hp\.local\share\opencode\opencode.db')
cursor = conn.cursor()

# Get all sessions
cursor.execute("SELECT id, slug, title, directory, time_created FROM session ORDER BY time_created")
sessions = cursor.fetchall()
print("=== SESSIONS ===")
for s in sessions:
    print(f"  {s[0]} | slug={s[1]} | dir={s[3]} | {s[4]}")

# Get all user messages with their text content
print("\n=== ALL USER MESSAGES (your exact commands) ===\n")

cursor.execute("""
    SELECT m.id, m.session_id, m.time_created, p.data
    FROM message m
    JOIN part p ON p.message_id = m.id
    WHERE m.data LIKE '%"role":"user"%'
    ORDER BY m.time_created
""")

rows = cursor.fetchall()
count = 0
for row in rows:
    msg_id, session_id, timestamp, part_data = row
    try:
        part = json.loads(part_data)
        if part.get('type') == 'text':
            text = part.get('text', '').strip()
            if text:
                count += 1
                # Find session slug
                slug = 'unknown'
                for s in sessions:
                    if s[0] == session_id:
                        slug = s[1]
                        break
                print(f"[{count}] session={slug} | {text[:200]}")
    except:
        pass

print(f"\nTotal user messages found: {count}")
conn.close()
