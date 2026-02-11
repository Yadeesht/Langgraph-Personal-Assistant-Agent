import uuid
import re
import aiosqlite
import sys
from pathlib import Path
import asyncio
from datetime import datetime

MIN_MESSAGE_TOKENS = 25
MIN_CHUNK_TOKENS = 200
MAX_CHUNK_TOKENS = (
    1000  # this threshold need to optimize based on performance now done heeeee
)
MAX_TIME_GAP_SECONDS = 3600

root_dir = Path(__file__).parent.parent
sys.path.append(str(root_dir))

from config.settings import MEMORY_DB
from utils.helper import setup_logger, count_tokens

logger = setup_logger(__name__)


class EpisodicRAG:
    def __init__(self, past_summery_date=None, db_path=MEMORY_DB):
        self.path = Path(db_path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.past_summery_date = past_summery_date

    PREFIX_PATTERN = re.compile(
        r"^(TALK TO USER:|FINAL ANSWER:|CLARIFICATION NEEDED:)\s*", re.IGNORECASE
    )
    DECORATOR_PATTERN = re.compile(r"[-=_*|]{3,}")
    LOG_HEADER_PATTERN = re.compile(r"^\[.*?\] \[.*?\]\s*")

    def clean_messages_for_chunk(self, text: str):
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

    def _split_text_to_chunks(self, text_lines, timestamp, actors):
        task_uuid = str(uuid.uuid4())
        generated_chunks = []

        cleaned_lines = []
        for line in text_lines:
            clean = self.clean_messages_for_chunk(line)
            if clean:
                cleaned_lines.append(clean)

        if not cleaned_lines:
            return []

        full_text = "\n".join(cleaned_lines)
        if count_tokens(full_text) <= MAX_CHUNK_TOKENS:
            return [
                {
                    "id": str(uuid.uuid4()),
                    "content": full_text,
                    "metadata": {
                        "timestamp": timestamp,
                        "task_id": task_uuid,
                        "part": 1,
                        "total_parts": 1,
                        "actors": actors,
                    },
                }
            ]

        current_lines = []
        current_tokens = 0
        part = 1

        for line in text_lines:
            clean_line = self.clean_messages_for_chunk(line)
            if not clean_line:
                continue

            line_tokens = count_tokens(clean_line)

            if current_tokens + line_tokens > MAX_CHUNK_TOKENS:
                generated_chunks.append(
                    {
                        "id": str(uuid.uuid4()),
                        "content": "\n".join(current_lines),
                        "metadata": {
                            "timestamp": timestamp,
                            "task_id": task_uuid,
                            "part": part,
                            "actors": actors,
                        },
                    }
                )
                current_lines = [clean_line]
                current_tokens = line_tokens
                part += 1
            else:
                current_lines.append(clean_line)
                current_tokens += line_tokens

        if current_lines:
            generated_chunks.append(
                {
                    "id": str(uuid.uuid4()),
                    "content": "\n".join(current_lines),
                    "metadata": {
                        "timestamp": timestamp,
                        "task_id": task_uuid,
                        "part": part,
                        "actors": actors,
                    },
                }
            )

        return generated_chunks

    async def custom_text_splitters(self):
        if not self.past_summery_date:
            logger.warning("Past summary date is not set. No data will be retrieved.")
            return []

        query = """
            SELECT timestamp, actor, message
            FROM human_logs 
            WHERE timestamp > ? 
            AND actor != 'supervisor_routing' 
            AND actor != 'summerizer_node'
            ORDER BY timestamp ASC
        """

        async with aiosqlite.connect(self.path) as db:
            async with db.execute(query, (self.past_summery_date,)) as cursor:
                rows = await cursor.fetchall()
                logger.info(f"Processing {len(rows)} raw logs...")

        episodes = []
        current_lines = []
        current_start_ts = None
        current_ts_obj = None
        actors = set()

        for timestamp, actor, message in rows:
            try:
                ts_obj = datetime.fromisoformat(timestamp)
            except ValueError:
                continue

            if actor == "Human_node":
                if current_lines:
                    episodes.append(
                        {
                            "ts_obj": current_ts_obj,
                            "timestamp": current_start_ts,
                            "lines": current_lines,
                            "actors": list(actors),
                        }
                    )
                current_lines = [f"User: {message}"]
                current_start_ts = timestamp
                current_ts_obj = ts_obj
                actors = set()

            elif actor == "supervisor_task_response":
                current_lines.append(f"Assistant: {message}")
                actors.add("supervisor")
                if current_lines:
                    episodes.append(
                        {
                            "ts_obj": current_ts_obj,
                            "timestamp": current_start_ts,
                            "lines": current_lines,
                            "actors": list(actors),
                        }
                    )
                    current_lines = []
                    current_start_ts = None
                    actors = set()
            else:
                if current_lines:
                    current_lines.append(f"{actor}: {message}")
                    actors.add(actor)

        if current_lines:
            episodes.append(
                {
                    "ts_obj": current_ts_obj,
                    "timestamp": current_start_ts,
                    "lines": current_lines,
                    "actors": list(actors),
                }
            )

        final_chunks = []

        for episode in episodes:
            ep_text = "\n".join(episode["lines"])
            ep_clean = self.clean_messages_for_chunk(ep_text)

            current_actors = episode.get("actors")
            if not current_actors:
                current_actors = set("supervisor")

            if not ep_clean:
                continue

            ep_tokens = count_tokens(ep_clean)
            has_tool = any(
                "__Tool Action__" in l or "Using tools" in l for l in episode["lines"]
            )

            if ep_tokens < MIN_MESSAGE_TOKENS and not has_tool:
                continue

            elif (
                ep_tokens < MIN_CHUNK_TOKENS
            ):  # Why backward? Because a small follow-up usually relates to the previous big thought.
                merged = False
                if final_chunks:
                    last_chunk = final_chunks[-1]

                try:
                    last_ts = datetime.fromisoformat(
                        last_chunk["metadata"]["timestamp"]
                    )
                    time_gap = (episode["ts_obj"] - last_ts).total_seconds()
                except:
                    time_gap = 999999

                if time_gap < MAX_TIME_GAP_SECONDS:
                    current_last_tokens = count_tokens(last_chunk["content"])

                    if current_last_tokens + ep_tokens <= MAX_CHUNK_TOKENS:
                        last_chunk["content"] += "\n" + ep_clean

                        existing_actors = set(last_chunk["metadata"]["actors"])
                        existing_actors.update(current_actors)
                        last_chunk["metadata"]["actors"] = list(existing_actors)

                        merged = True

                if not merged:
                    task_uuid = str(uuid.uuid4())
                    final_chunks.append(
                        {
                            "id": str(uuid.uuid4()),
                            "content": ep_clean,
                            "metadata": {
                                "timestamp": episode["timestamp"],
                                "task_id": task_uuid,
                                "part": 1,
                                "actors": current_actors,
                            },
                        }
                    )

            else:
                if ep_tokens > MAX_CHUNK_TOKENS:
                    chunks = self._split_text_to_chunks(
                        episode["lines"], episode["timestamp"], current_actors
                    )
                    final_chunks.extend(chunks)
                else:
                    task_uuid = str(uuid.uuid4())
                    final_chunks.append(
                        {
                            "id": str(uuid.uuid4()),
                            "content": ep_clean,
                            "metadata": {
                                "timestamp": episode["timestamp"],
                                "task_id": task_uuid,
                                "part": 1,
                                "actors": current_actors,
                            },
                        }
                    )

        for i in range(len(final_chunks)):
            final_chunks[i]["metadata"]["prev_id"] = None
            final_chunks[i]["metadata"]["next_id"] = None

            try:
                curr_ts = datetime.fromisoformat(
                    final_chunks[i]["metadata"]["timestamp"]
                )
            except (ValueError, TypeError):
                continue

            if i > 0:
                try:
                    prev_ts = datetime.fromisoformat(
                        final_chunks[i - 1]["metadata"]["timestamp"]
                    )
                    if (curr_ts - prev_ts).total_seconds() < MAX_TIME_GAP_SECONDS:
                        final_chunks[i]["metadata"]["prev_id"] = final_chunks[i - 1][
                            "id"
                        ]
                except (ValueError, TypeError):
                    pass

            if i < len(final_chunks) - 1:
                try:
                    next_ts = datetime.fromisoformat(
                        final_chunks[i + 1]["metadata"]["timestamp"]
                    )
                    if (next_ts - curr_ts).total_seconds() < MAX_TIME_GAP_SECONDS:
                        final_chunks[i]["metadata"]["next_id"] = final_chunks[i + 1][
                            "id"
                        ]
                except (ValueError, TypeError):
                    pass

        logger.info(f"Chunking Complete. Generated {len(final_chunks)} linked chunks.")
        return final_chunks

    def retrieve_chunks(self):

        pass
