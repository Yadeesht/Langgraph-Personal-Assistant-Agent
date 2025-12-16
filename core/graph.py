from langchain_core.messages import SystemMessage, trim_messages, AIMessage
from langgraph.graph import END, START, StateGraph
from langgraph.prebuilt import ToolNode

from config.prompts import (
    COMMUNICATION_SYSTEM_PROMPT,
    PLANNING_SYSTEM_PROMPT,
    SUPERVISOR_SYSTEM_PROMPT,
)
from core.agent import agent_node_factory, human_node, route_after_human
from core.llm import build_llm_with_tools
from core.state import Route, State, route_after_supervisor, internal_agent_route
from utils.logger import request_counter, setup_logger
from utils.token_counter import count_tokens

logger = setup_logger(__name__)


def build_graph(tool_sets, checkpointer):
    communication_tools = tool_sets["communication"]
    planning_tools = tool_sets["planning"]

    communication_llm = build_llm_with_tools(communication_tools)
    planning_llm = build_llm_with_tools(planning_tools)
    supervisor_llm = build_llm_with_tools([])

    communication_agent_node = agent_node_factory(
        communication_llm, COMMUNICATION_SYSTEM_PROMPT, "communication Agent"
    )
    planning_agent_node = agent_node_factory(
        planning_llm, PLANNING_SYSTEM_PROMPT, "planning Agent"
    )

    def supervisor_node(state: State):
        request_counter["count"] += 1
        request_num = request_counter["count"]

        logger.info("=" * 80)
        logger.info(f"👮 SUPERVISOR REQUEST #{request_num}")
        logger.info("=" * 80)

        logger.info(f"📨 Messages in context: {len(state['messages'])}")

        last_messages = trim_messages(
            state["messages"],
            max_tokens=80000,
            strategy="last",
            token_counter=count_tokens,
            include_system=True,
            start_on="human",
        )

        if last_messages:
            preview = str(last_messages[-3:])
            logger.info(f"📝 Latest Input: {preview}")
        logger.info("=" * 80)

        try:
            router = supervisor_llm.with_structured_output(Route)
            response = router.invoke(
                [SystemMessage(content=SUPERVISOR_SYSTEM_PROMPT)] + state["messages"]
            )

            logger.info("=" * 80)
            logger.info(f"➡ Routing to: {response.step}")

            supervisor_message = AIMessage(
                content=f"[SUPERVISOR ROUTING] Delegating task to: {response.step}",
                name="supervisor",
            )

            return {
                "next": response.step,
                "messages": [supervisor_message],
            }

        except Exception as e:
            logger.warning(f"⚠️ Structured output failed: {e}")

            error_message = AIMessage(
                content=f"[SUPERVISOR ERROR] Routing failed: {e}. Defaulting to FINISH.",
                name="supervisor",
            )

            response = Route(step="FINISH")

            logger.info("=" * 80)
            logger.info(f"➡ Routing to (fallback): {response.step}")

            return {
                "next": response.step,
                "messages": [error_message],
            }

    builder = StateGraph(State)

    builder.add_node("supervisor", supervisor_node)
    builder.add_node("communication_agent", communication_agent_node)
    builder.add_node("planning_agent", planning_agent_node)
    builder.add_node("human_node", human_node)

    builder.add_node(
        "communication_tools",
        ToolNode(tools=communication_tools, handle_tool_errors=True),
    )
    builder.add_node(
        "planning_tools",
        ToolNode(tools=planning_tools, handle_tool_errors=True),
    )

    builder.add_edge(START, "supervisor")

    builder.add_conditional_edges(
        "supervisor",
        route_after_supervisor,
        {
            "communication_agent": "communication_agent",
            "planning_agent": "planning_agent",
            "FINISH": END,
        },
    )

    builder.add_conditional_edges(
        "communication_agent",
        internal_agent_route,
        {
            "tools": "communication_tools",
            "supervisor": "supervisor",
            "ASK": "human_node",
        },
    )

    builder.add_edge("communication_tools", "communication_agent")

    builder.add_conditional_edges(
        "planning_agent",
        internal_agent_route,
        {
            "tools": "planning_tools",
            "supervisor": "supervisor",
            "ASK": "human_node",
        },
    )
    builder.add_edge("planning_tools", "planning_agent")

    builder.add_conditional_edges(
        "human_node",
        route_after_human,
        {
            "communication_agent": "communication_agent",
            "planning_agent": "planning_agent",
            END: END,
        },
    )

    graph = builder.compile(checkpointer=checkpointer)
    return graph
