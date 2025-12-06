from typing import Literal
from pydantic import BaseModel
from langchain_core.messages import SystemMessage
from langgraph.graph import START, END, StateGraph
from langgraph.prebuilt import ToolNode, tools_condition

from core.agent import agent_node_factory
from core.llm import build_llm_with_tools
from core.state import State
from config.prompts import (
    SUPERVISOR_SYSTEM_PROMPT,
    COMM_SYSTEM_PROMPT,
    PROD_SYSTEM_PROMPT,
)
from langchain_core.messages import trim_messages
from utils.logger import request_counter, setup_logger
from utils.token_counter import count_tokens

logger = setup_logger(__name__)


class Route(BaseModel):
    """Route decision for supervisor"""

    step: Literal["communication_agent", "productivity_agent"]


def build_graph(tool_sets, checkpointer):
    comm_tools = tool_sets["communication"]
    prod_tools = tool_sets["productivity"]

    comm_llm = build_llm_with_tools(comm_tools)
    prod_llm = build_llm_with_tools(prod_tools)
    supervisor_llm = build_llm_with_tools([])

    comm_agent_node = agent_node_factory(comm_llm, COMM_SYSTEM_PROMPT)
    prod_agent_node = agent_node_factory(prod_llm, PROD_SYSTEM_PROMPT)

    def supervisor_node(state: State):
        request_counter["count"] += 1
        request_num = request_counter["count"]

        logger.info("=" * 80)
        logger.info(f"👮 SUPERVISOR REQUEST #{request_num}")
        logger.info("=" * 80)

        logger.info(f"📨 Messages in context: {len(state['messages'])}")

        last_messages = trim_messages(
            state["messages"],
            max_tokens=2000,
            strategy="last",
            token_counter=count_tokens,
            include_system=True,
            start_on="human",
        )

        if last_messages:
            preview = str(last_messages[-1].content)
            content_preview = preview[:100] + "..." if len(preview) > 100 else preview
            logger.info(f"📝 Latest Input: {content_preview}")
        logger.info("=" * 80)

        router = supervisor_llm.with_structured_output(Route)

        response = router.invoke(
            [SystemMessage(content=SUPERVISOR_SYSTEM_PROMPT)] + state["messages"]
        )

        logger.info(f"🧭 ROUTING DECISION MADE")
        logger.info(f"👉 Selected Agent: {response.step}")
        logger.info("=" * 80)

        return {"next": response.step}

    def route_after_supervisor(state: State):
        # supervisor_node sets state["next"] to "communication_agent" or "productivity_agent"
        return state["next"]

    builder = StateGraph(State)

    builder.add_node("supervisor", supervisor_node)
    builder.add_node("communication_agent", comm_agent_node)
    builder.add_node("productivity_agent", prod_agent_node)

    builder.add_node("comm_tools", ToolNode(tools=comm_tools, handle_tool_errors=True))
    builder.add_node("prod_tools", ToolNode(tools=prod_tools, handle_tool_errors=True))

    builder.add_edge(START, "supervisor")
    builder.add_conditional_edges("supervisor", route_after_supervisor)

    builder.add_conditional_edges(
        "communication_agent", tools_condition, {"tools": "comm_tools", END: END}
    )
    builder.add_edge("comm_tools", "communication_agent")

    builder.add_conditional_edges(
        "productivity_agent", tools_condition, {"tools": "prod_tools", END: END}
    )
    builder.add_edge("prod_tools", "productivity_agent")

    graph = builder.compile(checkpointer=checkpointer)
    return graph
