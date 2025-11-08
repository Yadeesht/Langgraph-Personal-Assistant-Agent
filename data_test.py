import sqlite3
import msgpack
import json

DB_PATH = "D:/Agentic AI/data/memory.db"


def safe_json_default(obj):
    if isinstance(obj, bytes):
        try:
            return obj.decode("utf-8")
        except Exception:
            return f"<{len(obj)} bytes binary data>"
    return str(obj)


conn = sqlite3.connect(DB_PATH)
cur = conn.cursor()

cur.execute("SELECT checkpoint_id, checkpoint FROM checkpoints")
rows = cur.fetchall()
conn.close()

for i, (cp_id, blob) in enumerate(rows, start=1):
    print(f"\n==================== CHECKPOINT #{i} ====================")
    try:
        data = msgpack.unpackb(blob, raw=False)
        print(json.dumps(data, indent=2, default=safe_json_default))
    except Exception as e:
        print(f"❌ Failed to decode checkpoint {cp_id}: {e}")
