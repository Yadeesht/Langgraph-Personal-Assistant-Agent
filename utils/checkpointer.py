from langgraph.checkpoint.sqlite.aio import AsyncSqliteSaver
import aiosqlite
import json
from datetime import datetime
from langchain_core.messages import BaseMessage

from config.settings import MEMORY_DB


class AsyncSqliteSaver(AsyncSqliteSaver):
    async def aput(self, config, checkpoint, metadata, new_versions):
        """Save checkpoint with cleaned messages"""

        return await super().aput(config, checkpoint, metadata, new_versions)


async def init_archive_db():
    async with aiosqlite.connect(str(MEMORY_DB)) as connection:
        await connection.execute("""
            CREATE TABLE IF NOT EXISTS message_logs (
                id TEXT PRIMARY KEY,
                thread_id TEXT,
                role TEXT,
                content TEXT,
                timestamp TEXT,
                metadata TEXT
            )
        """)
        await connection.commit()


async def archive_to_permanent_db(messages: list[BaseMessage], thread_id: str):
    """
    Safely pushes messages to a permanent store.
    Uses INSERT OR IGNORE to prevent duplicates.
    """
    async with aiosqlite.connect(str(MEMORY_DB)) as connection:
        for msg in messages:
            content = (
                msg.content if isinstance(msg.content, str) else json.dumps(msg.content)
            )

            await connection.execute(
                """
                INSERT OR IGNORE INTO message_logs 
                (id, thread_id, role, content, timestamp, metadata)
                VALUES (?, ?, ?, ?, ?, ?)
            """,
                (
                    msg.id,
                    thread_id,
                    msg.type,
                    content,
                    datetime.now().isoformat(),
                    json.dumps(getattr(msg, "additional_kwargs", {})),
                ),
            )
        await connection.commit()
