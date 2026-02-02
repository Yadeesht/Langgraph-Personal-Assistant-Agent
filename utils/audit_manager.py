import aiosqlite
from datetime import datetime
import sqlite3
import os

import sys
from pathlib import Path

root_dir = Path(__file__).parent.parent
sys.path.insert(0, str(root_dir))

from config.settings import MEMORY_DB
from utils.helper import setup_logger

logger = setup_logger(__name__)


async def log_event(thread_id: str, actor: str, message: str, metadata: dict = None):
    """Saves a human-readable log entry to a separate table."""
    async with aiosqlite.connect(MEMORY_DB) as db:
        await db.execute("""
            CREATE TABLE IF NOT EXISTS human_logs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                thread_id TEXT,
                timestamp TEXT,
                actor TEXT,
                message TEXT,
                metadata TEXT
            )
        """)
        await db.execute(
            "INSERT INTO human_logs (thread_id, timestamp, actor, message, metadata) VALUES (?, ?, ?, ?, ?)",
            (
                thread_id,
                datetime.now().isoformat(),
                actor,
                message,
                str(metadata or {}),
            ),
        )
        await db.commit()


def analyze_human_logs(
    db_path="D:\\Agentic AI\\data\\memory.db",
    output_file="utils/log_details.txt",
):
    try:
        # 1. Connect to your local SQLite file
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()

        # 2. Query your new human-readable table
        # We select the columns defined in your log_event function
        query = """
            SELECT thread_id, timestamp, actor, message, metadata 
            FROM human_logs 
            ORDER BY timestamp DESC;
        """
        cursor.execute(query)
        rows = cursor.fetchall()

        if not rows:
            message = "🕒 No human-readable logs found yet. Start a conversation first!"
            with open(output_file, "w", encoding="utf-8") as f:
                f.write(message + "\n")
            conn.close()
            return

        # 3. Open file for writing the clear-text report
        with open(output_file, "w", encoding="utf-8") as f:
            f.write("=" * 100 + "\n")
            f.write("📊 AGENTIC AI - HUMAN READABLE AUDIT LOG\n")
            f.write(f"Generated at: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
            f.write("=" * 100 + "\n\n")

            for thread_id, timestamp, actor, message, metadata in rows:
                f.write(
                    f"[{timestamp}] | THREAD: {thread_id[:8]}... | ACTOR: {actor.upper()}\n"
                )
                f.write(f"MESSAGE: {message}\n")

                # Metadata is stored as a stringified dict in your log_event code
                if metadata and metadata != "{}":
                    f.write(f"METADATA: {metadata}\n")

                f.write("-" * 100 + "\n")

            # 4. Summary Stats
            unique_threads = len(set(row[0] for row in rows))
            summary = "\nSUMMARY:\n"
            summary += f"Total Events Logged: {len(rows)}\n"
            summary += f"Active Threads: {unique_threads}\n"
            f.write(summary)

        print(f"✅ Audit report successfully written to {output_file}")
        conn.close()

    except sqlite3.OperationalError:
        logger.error(
            "❌ Table 'human_logs' does not exist yet. Ensure an event has been logged first."
        )
    except Exception as e:
        logger.error(f"❌ An unexpected error occurred: {e}")


if __name__ == "__main__":
    # Ensure the directory for the output file exists
    os.makedirs("utils", exist_ok=True)
    analyze_human_logs()
