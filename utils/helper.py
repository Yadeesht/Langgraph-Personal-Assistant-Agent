import logging
import sqlite3
import tiktoken
from datetime import datetime
from langgraph.checkpoint.sqlite.aio import AsyncSqliteSaver
import pytz

import re
import html
import asyncio
import aiosqlite
import sys
from pathlib import Path
import json

root = Path(__file__).parent.parent
sys.path.insert(0, str(root))

from config.settings import CHECKPOINT_DB
from config.settings import DEFAULT_THREAD_ID


def clean_email_body(text: str) -> str:
    # 1. Decode HTML entities (e.g., convert &#39; to ')
    text = html.unescape(text)

    # 2. Strip ZWNJ and other invisible junk
    text = re.sub(r"[^\x20-\x7e]", r"", text)

    # 3. Remove repeated special characters (like those divider lines -----)
    text = re.sub(r"[-*=_]{3,}", " ", text)

    # 4. Normalize whitespace
    text = " ".join(text.split())

    text = re.sub(r"\(mailto:[^)]*\)", "", text)

    # Optional: Clean up the [Awesome], [Decent] text left behind
    text = re.sub(r"\[Awesome\]|\[Decent\]|\[Not Great\]", "", text)

    return text


# This class does the short-term memory thing by adding ad summerizing the context in real-time
class AsyncSqliteSaver(AsyncSqliteSaver):
    async def aput(self, config, checkpoint, metadata, new_versions):
        """Save checkpoint with cleaned messages"""

        return await super().aput(config, checkpoint, metadata, new_versions)


mock_tool_sets = {"communication": [], "planning": [], "content": [], "supervisor": []}


async def get_agent_state(thread_id: str):
    async with aiosqlite.connect(str(CHECKPOINT_DB)) as conn:
        checkpointer = AsyncSqliteSaver(conn)

        from core.graph import build_graph

        graph = build_graph(mock_tool_sets, checkpointer)

        config = {"configurable": {"thread_id": thread_id}}

        snapshot = await graph.aget_state(config)

        if not snapshot.values:
            print("❌ No state found for this thread ID.")
            return

        values = snapshot.values
        print("=" * 40)
        print(f"📊 STATE FOR THREAD: {thread_id}")
        print("=" * 40)
        print(
            f"🕒 Last Memory Timestamp: {datetime.fromtimestamp(values.get('last_memory_timestamp')) if values.get('last_memory_timestamp') else 'N/A'}"
        )
        print(f"🧠 Summary: {values.get('summary')}")
        print(f"📨 Total Messages: {len(values.get('messages', []))}")
        print(f"🔜 Next Step: {snapshot.next}")
        print("=" * 40)


def count_tokens(messages):
    """
    Count tokens for messages. Handles both:
    - List of message objects with .content attribute
    - List of plain strings
    - Single string
    """
    try:
        encoding = tiktoken.encoding_for_model("gpt-4")
    except KeyError:
        encoding = tiktoken.get_encoding("cl100k_base")

    # Handle single string input
    if isinstance(messages, str):
        return len(encoding.encode(messages))

    # Handle list of messages
    num_tokens = 0
    for message in messages:
        if isinstance(message, str):
            # Plain string - just encode it
            num_tokens += len(encoding.encode(message))
        elif hasattr(message, "content"):
            # Message object with content attribute
            num_tokens += 4  # Message formatting overhead
            num_tokens += len(encoding.encode(str(message.content)))
        else:
            # Unknown type, try to convert to string
            num_tokens += len(encoding.encode(str(message)))

    # Add reply priming tokens only for message objects (not plain strings)
    if messages and not isinstance(messages[0], str):
        num_tokens += 2

    return num_tokens


def setup_logger(name: str = __name__) -> logging.Logger:
    """Configure and return a logger instance"""
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s | %(levelname)-8s | %(name)-20s | %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )
    return logging.getLogger(name)


request_counter = {"supervisor": 0, "sub_agents": 0}


def delete_thread_from_db(thread_id: str):
    """Clear memory for a specific thread"""

    conn = sqlite3.connect(CHECKPOINT_DB)
    cursor = conn.cursor()
    cursor.execute("DELETE FROM messages WHERE thread_id = ?", (thread_id,))
    deleted = cursor.rowcount
    conn.commit()
    conn.close()
    print(f"✅ Deleted {deleted} messages from thread: {thread_id}")


def get_current_time():
    now = datetime.now(pytz.timezone("Asia/Kolkata"))
    return now.strftime("%Y-%m-%d %H:%M:%S IST")


def format_tool_to_text(tool_name, tool_args_str):
    try:
        args = json.loads(tool_args_str)
    except:
        return f"[Action: {tool_name}] (Args: {tool_args_str})"

    arg_summary = ", ".join([f"{k}={v}" for k, v in args.items()])
    return f"__Tool Action__: Used {tool_name} with inputs: {arg_summary}"


def clean_text_for_tts(text):
    # 1. Remove code blocks (content between triple backticks)
    text = re.sub(r"```.*?```", " ", text, flags=re.DOTALL)

    # 2. Remove inline code (content between single backticks)
    text = re.sub(r"`.*?`", " ", text)

    # 3. Remove Markdown formatting (*, **, #, >, etc.)
    text = re.sub(
        r"[\*\#_>~\-]{2,}", "", text
    )  # Remove multi-char markers like **, ##, --
    text = re.sub(
        r"(?<!\w)\*|\*(?!\w)", "", text
    )  # Remove single * if it's not part of a math equation

    # 4. Remove Links [Text](URL) -> Text
    text = re.sub(r"\[([^\]]+)\]\([^\)]+\)", r"\1", text)

    # 5. Clean up extra whitespace created by removals
    text = re.sub(r"\s+", " ", text).strip()

    if text.strip() == "You":
        return ""

    return text


if __name__ == "__main__":
    asyncio.run(get_agent_state(DEFAULT_THREAD_ID))
