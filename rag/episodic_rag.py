import uuid
import re
import aiosqlite
import sys
from pathlib import Path
import asyncio

MIN_TOKENS = 50
MAX_TOKENS = 1000

root_dir = Path(__file__).parent.parent
sys.path.append(str(root_dir))

from config.settings import MEMORY_DB
from utils.helper import setup_logger, count_tokens

logger = setup_logger(__name__)


class EpisodicRAG:
    def __init__(self, db_path=MEMORY_DB, past_summery_date=None):
        self.path = Path(db_path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.past_summery_date = past_summery_date

    PREFIX_PATTERN = re.compile(
        r"^(TALK TO USER:|FINAL ANSWER:|CLARIFICATION NEEDED:)\s*", re.IGNORECASE
    )
    DECORATOR_PATTERN = re.compile(r"[-=_*|]{3,}")
    LOG_HEADER_PATTERN = re.compile(r"^\[.*?\] \[.*?\]\s*")

    def clean_messages(self, text: str):
        if not text:
            return None

        if "<|channel|>" in text:
            return None
        if text.startswith("Routing to:"):
            return None

        text = self.LOG_HEADER_PATTERN.sub("", text)
        text = self.PREFIX_PATTERN.sub("", text)
        text = self.DECORATOR_PATTERN.sub(" ", text)

        text = re.sub(r"\n{3,}", "\n\n", text)
        text = re.sub(r" {2,}", " ", text)

        cleaned_text = text.strip()
        if not cleaned_text:
            return None

        return cleaned_text

    async def custom_text_splitters(self):
        if not self.past_summery_date:
            logger.warning("Past summary date is not set. No data will be retrieved.")
            return []

        query = """
            SELECT timestamp, actor, message 
            FROM human_logs 
            WHERE timestamp > ? 
            AND actor != 'supervisor_routing' 
            ORDER BY timestamp ASC
        """

        async with aiosqlite.connect(self.path) as db:
            async with db.execute(query, (self.past_summery_date,)) as cursor:
                rows = await cursor.fetchall()
                logger.info(f"Processing {len(rows)} raw logs...")

        episodes = []
        current_episode_lines = []
        current_start_ts = None

        for timestamp, actor, message in rows:
            if actor == "Human_node":
                if current_episode_lines:
                    episodes.append(
                        {"timestamp": current_start_ts, "lines": current_episode_lines}
                    )

                current_start_ts = timestamp
                current_episode_lines = [f"User: {message}"]

            elif actor == "supervisor_task_response":
                current_episode_lines.append(f"Assistant: {message}")

                if current_episode_lines:
                    episodes.append(
                        {"timestamp": current_start_ts, "lines": current_episode_lines}
                    )
                    current_episode_lines = []
                    current_start_ts = None

            else:
                if current_episode_lines:
                    if "tool_call" in str(message) or "__Tool Action__" in str(message):
                        current_episode_lines.append(f"{message}")
                    else:
                        current_episode_lines.append(f"{actor}: {message}")

        if current_episode_lines:
            episodes.append(
                {"timestamp": current_start_ts, "lines": current_episode_lines}
            )

        final_chunks = []

        for episode in episodes:
            task_uuid = str(uuid.uuid4())

            full_text = "\n".join(episode["lines"])
            cleaned_full_text = self.clean_messages(full_text)

            if not cleaned_full_text:
                continue

            total_tokens = count_tokens(cleaned_full_text)

            if total_tokens < MIN_TOKENS:
                continue

            if total_tokens <= MAX_TOKENS:
                final_chunks.append(
                    {
                        "id": str(uuid.uuid4()),
                        "content": cleaned_full_text,
                        "metadata": {
                            "timestamp": episode["timestamp"],
                            "task_id": task_uuid,
                            "part": 1,
                            "total_parts": 1,
                        },
                    }
                )

            else:
                current_chunk_lines = []
                current_chunk_tokens = 0
                part_counter = 1

                for line in episode["lines"]:
                    cleaned_line = self.clean_messages(line)
                    if not cleaned_line:
                        continue

                    line_tokens = count_tokens(cleaned_line)

                    if current_chunk_tokens + line_tokens > MAX_TOKENS:
                        chunk_content = "\n".join(current_chunk_lines)
                        final_chunks.append(
                            {
                                "id": str(uuid.uuid4()),
                                "content": chunk_content,
                                "metadata": {
                                    "timestamp": episode["timestamp"],
                                    "task_id": task_uuid,
                                    "part": part_counter,
                                },
                            }
                        )

                        part_counter += 1
                        current_chunk_lines = [cleaned_line]
                        current_chunk_tokens = line_tokens
                    else:
                        current_chunk_lines.append(cleaned_line)
                        current_chunk_tokens += line_tokens

                if current_chunk_lines:
                    final_chunks.append(
                        {
                            "id": str(uuid.uuid4()),
                            "content": "\n".join(current_chunk_lines),
                            "metadata": {
                                "timestamp": episode["timestamp"],
                                "task_id": task_uuid,
                                "part": part_counter,
                            },
                        }
                    )

        for i in range(len(final_chunks)):
            final_chunks[i]["metadata"]["prev_id"] = None
            final_chunks[i]["metadata"]["next_id"] = None

            if i > 0:
                final_chunks[i]["metadata"]["prev_id"] = final_chunks[i - 1]["id"]
            if i < len(final_chunks) - 1:
                final_chunks[i]["metadata"]["next_id"] = final_chunks[i + 1]["id"]

        logger.info(
            f"Chunking Complete. Generated {len(final_chunks)} chunks from {len(episodes)} episodes."
        )
        return final_chunks


if __name__ == "__main__":
    past_summery_date = "2024-01-01 00:00:00"
    rag = EpisodicRAG(past_summery_date=past_summery_date)
    asyncio.run(rag.custom_text_splitters())
