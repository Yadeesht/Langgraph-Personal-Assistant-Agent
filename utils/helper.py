import logging
import sqlite3
from config.settings import CHECKPOINT_DB
import tiktoken
from datetime import datetime
import pytz


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


request_counter = {"count": 0}


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
