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
    number_of_summaries_today: Optional[int] = 0
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

    # this logic is broken need to be fixed
    if state.get("last_summary_timestamp") is not None:
        dt_summry = datetime.fromtimestamp(state["last_summary_timestamp"])
        now = datetime.now()

        if now.date() != dt_summry.date() and count_tokens(messages[:-15]) > 500:
            state["summary"] = ""
            state["number_of_summaries_today"] = 0
            state["last_summary_timestamp"] = now.timestamp()
            logger.info(
                "🗑️ Cleared old summary due to time limit and knowledgeGraph is updated"
            )

        dt_kg = (
            datetime.fromtimestamp(state["last_knowledgegraph_timestamp"])
            if state.get("last_knowledgegraph_timestamp")
            else None
        )

        if dt_kg and now.date() != dt_kg.date():
            logger.info(f"KnowledgeGraph Updating.")

            state["last_knowledgegraph_timestamp"] = now.timestamp()
            logger.info(
                "🗑️ knowledgeGraph updated timestamp refreshed due to time limit"
            )

    if count_tokens(messages[:-15]) > 8000:
        return "summerizer_node"

    return "supervisor"
