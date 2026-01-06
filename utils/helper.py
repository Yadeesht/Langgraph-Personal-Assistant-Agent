import logging
import sqlite3
from config.settings import DB_PATH
import tiktoken


def count_tokens(messages):
    try:
        encoding = tiktoken.encoding_for_model("gpt-4")
    except KeyError:
        encoding = tiktoken.get_encoding("cl100k_base")

    num_tokens = 0
    for message in messages:
        # Every message follows <im_start>{role/name}\n{content}<im_end>\n
        num_tokens += 4
        if hasattr(message, "content"):
            num_tokens += len(encoding.encode(str(message.content)))
    num_tokens += 2  # Every reply is primed with <im_start>assistant
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

    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("DELETE FROM messages WHERE thread_id = ?", (thread_id,))
    deleted = cursor.rowcount
    conn.commit()
    conn.close()
    print(f"✅ Deleted {deleted} messages from thread: {thread_id}")
