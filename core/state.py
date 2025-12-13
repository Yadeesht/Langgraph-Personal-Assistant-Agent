from typing import Annotated, Literal, Optional
import logging
from langgraph.graph.message import add_messages
from pydantic import BaseModel, Field
from typing_extensions import TypedDict

logger = logging.getLogger(__name__)


class State(TypedDict):
    messages: Annotated[list, add_messages]

    next: Optional[str]


class Route(BaseModel):
    """Routing decision for the supervisor"""

    step: Literal["communication_agent", "planning_agent", "FINISH"] = Field(
        description="The next agent to route to, or FINISH if done"
    )


def route_after_supervisor(state: State):
    return state["next"]


def internal_agent_route(state: State) -> str:
    """Route from agent node to tools, supervisor, or human clarification"""
    last_message = state["messages"][-1]

    if hasattr(last_message, "content") and isinstance(last_message.content, str):
        if "FINAL ANSWER:" in last_message.content.upper():
            logger.info("✅ Detected FINAL ANSWER - returning to supervisor")
            return "supervisor"

    if hasattr(last_message, "tool_calls") and last_message.tool_calls:
        logger.info(f"🔧 Agent requesting {len(last_message.tool_calls)} tool(s)")
        return "tools"

    if (
        hasattr(last_message, "content")
        and "CLARIFICATION NEEDED:" in last_message.content
    ):
        logger.info("❓ Clarification needed - routing to human")
        return "ASK"

    logger.info("📤 No tools/clarification - returning to supervisor")
    return "supervisor"
