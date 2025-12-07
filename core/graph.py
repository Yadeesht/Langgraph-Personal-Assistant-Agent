from langchain_core.messages import AIMessage, SystemMessage, trim_messages
from langgraph.graph import END, START, StateGraph
from langgraph.prebuilt import ToolNode, tools_condition

from config.prompts import (
    COMM_SYSTEM_PROMPT,
    PROD_SYSTEM_PROMPT,
    SUPERVISOR_SYSTEM_PROMPT,
)
from core.agent import agent_node_factory
from core.llm import build_llm_with_tools
from core.state import Route, State, route_after_supervisor
from utils.logger import request_counter, setup_logger
from utils.token_counter import count_tokens

logger = setup_logger(__name__)


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
            logger.info(f"📝 Latest Input: {preview}")
        logger.info("=" * 80)

        try:
            router = supervisor_llm.with_structured_output(Route)
            response = router.invoke(
                [SystemMessage(content=SUPERVISOR_SYSTEM_PROMPT)] + state["messages"]
            )
        except Exception as e:
            logger.warning(f"⚠️ Structured output failed: {e}")
            logger.info("🔄 Falling back to text-based routing")

            # Fallback: Use regular LLM call and parse manually
            raw_response = supervisor_llm.invoke(
                [
                    SystemMessage(
                        content=SUPERVISOR_SYSTEM_PROMPT
                        + '\n\nIMPORTANT: Respond with ONLY a JSON object in this exact format:\n{"step": "communication_agent" or "productivity_agent" or null, "direct_reply": "your message" or null}'
                    )
                ]
                + state["messages"]
            )

            content = raw_response.content.strip()
            logger.info(f"🔍 Raw response: {content[:200]}...")

            # Try to extract JSON from the response
            import json
            import re

            # Try to find JSON in the response
            json_match = re.search(r"\{[^}]+\}", content)
            if json_match:
                try:
                    parsed = json.loads(json_match.group())
                    response = Route(**parsed)
                except:
                    # Default to productivity agent if parsing fails
                    logger.warning(
                        "⚠️ Could not parse JSON, defaulting to productivity_agent"
                    )
                    response = Route(step="productivity_agent")
            else:
                # Check keywords in response
                content_lower = content.lower()
                if any(
                    word in content_lower
                    for word in ["email", "gmail", "send", "mail", "message"]
                ):
                    response = Route(step="communication_agent")
                elif any(
                    word in content_lower
                    for word in ["calendar", "event", "schedule", "meeting"]
                ):
                    response = Route(step="productivity_agent")
                else:
                    response = Route(direct_reply=content)

        logger.info("🧭 ROUTING DECISION MADE")
        logger.info(f"👉 Selected Agent: {response.step}")
        logger.info("=" * 80)

        # Case A: Supervisor wants to speak directly (General chat or "Finished")
        if response.direct_reply:
            final_msg = AIMessage(content=response.direct_reply)
            logger.info("🤖 SUPERVISOR FINAL REPLY:")
            return {"messages": [final_msg]}

        # Case B: Supervisor is routing to a worker
        if response.step:
            logger.info(f"➡ Routing to: {response.step}")
            return {"next": response.step}

        # Fallback (Safety)
        logger.info("⚠ No valid routing decision made. Ending conversation.")
        return {"next": "__end__"}

    builder = StateGraph(State)

    builder.add_node("supervisor", supervisor_node)
    builder.add_node("communication_agent", comm_agent_node)
    builder.add_node("productivity_agent", prod_agent_node)

    builder.add_node("comm_tools", ToolNode(tools=comm_tools, handle_tool_errors=True))
    builder.add_node("prod_tools", ToolNode(tools=prod_tools, handle_tool_errors=True))

    builder.add_edge(START, "supervisor")
    builder.add_conditional_edges(
        "supervisor",
        route_after_supervisor,
        {
            "communication_agent": "communication_agent",
            "productivity_agent": "productivity_agent",
            END: END,
        },
    )

    builder.add_conditional_edges(
        "communication_agent",
        tools_condition,
        {"tools": "comm_tools", END: "supervisor"},
    )
    builder.add_edge("comm_tools", "communication_agent")

    builder.add_conditional_edges(
        "productivity_agent",
        tools_condition,
        {"tools": "prod_tools", END: "supervisor"},
    )
    builder.add_edge("prod_tools", "productivity_agent")

    graph = builder.compile(checkpointer=checkpointer)
    return graph
