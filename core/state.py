from typing import Annotated, Literal, Optional, List, Dict, Any
from langgraph.graph.message import add_messages
from pydantic import BaseModel, Field
from typing_extensions import TypedDict
from utils.helper import setup_logger, count_tokens
from datetime import datetime

logger = setup_logger(__name__)


class State(TypedDict):
    messages: Annotated[list, add_messages]
    summary: Optional[str]
    last_summary_timestamp: Optional[float] = datetime.now().timestamp()
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


def route_start(state: State) -> str:
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

    if (
        state.get("last_summary_timestamp") is not None
        and (datetime.now().timestamp() - state.get("last_summary_timestamp")) > 21600
    ) and count_tokens(messages[:]) > 4000:
        state["summary"] = ""
        state["last_summary_timestamp"] = datetime.now().timestamp()
        logger.info("🗑️ Cleared old summary due to time/token limits")

    if count_tokens(messages[:-15]) > 8000:
        return "summerizer_node"

    return "supervisor"
