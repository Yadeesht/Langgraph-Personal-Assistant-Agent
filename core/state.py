from typing import Annotated, Literal, Optional, List, Dict, Any
from langgraph.graph.message import add_messages
from pydantic import BaseModel, Field
from typing_extensions import TypedDict
from utils.helper import setup_logger, count_tokens
import time
import aiosqlite
from datetime import datetime

from config.settings import DEFAULT_THREAD_ID, MEMORY_DB

logger = setup_logger(__name__)


class State(TypedDict):
    messages: Annotated[list, add_messages]
    summary: Optional[str]
    last_memory_timestamp: Optional[float] = 1770195927.8211298  # random time
    next: Optional[str]


class TaskSpec(BaseModel):
    """Structured task specification for code execution"""

    primary_goal: str
    required_tools_hint: List[str]
    context_variables: Dict[str, Any]
    last_error: Optional[str] = None


class Route(BaseModel):
    """Routing decision for the supervisor"""

    step: Literal[
        "communication_agent",
        "planning_agent",
        "content_agent",
        "code_agent",
        "FINISH",
    ] = Field(
        description="The next agent to route to, or FINISH if done no other response other than these is allowed"
    )


def route_after_supervisor(state: State):
    return state["next"]


def internal_agent_route(state: State) -> str:
    """Route from agent node to tools, supervisor, or human clarification"""
    last_message = state["messages"][-1]

    if hasattr(last_message, "tool_calls") and last_message.tool_calls:
        logger.info(f"🔧 Agent requesting {len(last_message.tool_calls)} tool(s)")
        return "tools"

    if hasattr(last_message, "content") and isinstance(last_message.content, str):
        if "FINAL ANSWER:" in last_message.content.upper():
            logger.info("✅ Detected FINAL ANSWER - returning to supervisor")
            return "supervisor"

    if hasattr(last_message, "content") and isinstance(last_message.content, str):
        if "CLARIFICATION NEEDED:" in last_message.content.upper():
            logger.info("❓ Clarification needed - routing to human")
            return "END"

        if "TALK TO USER:" in last_message.content.upper():
            logger.info("💬 Agent wants to talk to user - routing to human")
            return "END"
    logger.info("📤 No tools/clarification - returning to supervisor")
    return "supervisor"


async def route_start(state: State) -> str:

    last_memory_ts = state.get("last_memory_timestamp")

    if isinstance(last_memory_ts, float):
        query_ts = datetime.fromtimestamp(last_memory_ts).isoformat()

    elif isinstance(last_memory_ts, datetime):
        query_ts = last_memory_ts.isoformat()

    else:
        query_ts = str(last_memory_ts)

    should_update_memory = False

    if last_memory_ts is None:
        logger.info("🆕 New Thread Detected: Initializing memory timestamp.")
        should_update_memory = True
    else:
        now_float = time.time()
        SECONDS_IN_DAY = 86400
        IST_OFFSET = 19800

        current_day_ist = int((now_float + IST_OFFSET) // SECONDS_IN_DAY)
        memory_day_ist = int((last_memory_ts + IST_OFFSET) // SECONDS_IN_DAY)

        if current_day_ist > memory_day_ist:
            logger.info("📅 New Day Detected: Triggering memory optimization.")
            query = """
                SELECT timestamp, actor, message, metadata
                FROM human_logs 
                WHERE timestamp > ? 
                AND actor NOT IN ('supervisor_routing', 'summerizer_node')
                AND COALESCE(json_extract(metadata, '$.type'), '') != 'tool_call'
                ORDER BY timestamp ASC
            """
            async with aiosqlite.connect(MEMORY_DB) as db:
                async with db.execute(query, (query_ts,)) as cursor:
                    rows = await cursor.fetchall()
                    logger.info(f"Processing {len(rows)} raw logs...")
            if len(rows) > 0:
                should_update_memory = True

    if should_update_memory:
        return "memory_update_node"

    messages = state["messages"]

    if len(messages) < 2:
        return "supervisor"

    last_ai_msg = messages[-2]

    if hasattr(last_ai_msg, "content") and isinstance(last_ai_msg.content, str):
        content_upper = last_ai_msg.content.upper()

        if "CLARIFICATION NEEDED:" in content_upper or "TALK TO USER:" in content_upper:
            if hasattr(
                last_ai_msg, "additional_kwargs"
            ) and last_ai_msg.additional_kwargs.get("name"):
                agent_name = last_ai_msg.additional_kwargs["name"]
                logger.info(f"Previous agent identified as: {agent_name}")

                if agent_name in [
                    "communication_agent",
                    "planning_agent",
                    "content_agent",
                ]:
                    return agent_name

    if count_tokens(messages) > 8000:
        return "summerizer_node"

    return "supervisor"
