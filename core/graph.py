from langchain_core.messages import SystemMessage, trim_messages, AIMessage
from langgraph.graph import END, START, StateGraph
from langgraph.prebuilt import ToolNode
import re
import json
import httpx
from config.prompts import (
    COMMUNICATION_SYSTEM_PROMPT,
    PLANNING_SYSTEM_PROMPT,
    SUPERVISOR_SYSTEM_PROMPT,
    CONTENT_SYSTEM_PROMPT,
)
from core.agent import agent_node_factory, summerizer_node, code_execution_factory
from core.llm import build_llm_with_tools, build_llm
from core.state import State, route_after_supervisor, internal_agent_route, route_start
from utils.helper import request_counter, setup_logger
from utils.helper import count_tokens, get_current_time
from config.settings import DEFAULT_OPEN_CODE_MODEL

logger = setup_logger(__name__)


def build_graph(tool_sets, checkpointer):
    communication_tools = tool_sets["communication"]
    planning_tools = tool_sets["planning"]
    content_tools = tool_sets["content"]
    supervisor_tools = tool_sets["supervisor"]

    communication_llm = build_llm_with_tools(communication_tools)
    planning_llm = build_llm_with_tools(planning_tools)
    content_llm = build_llm_with_tools(tools=content_tools)
    supervisor_llm = build_llm_with_tools(supervisor_tools)
    code_agent_llm = build_llm()

    communication_agent_node = agent_node_factory(
        communication_llm, COMMUNICATION_SYSTEM_PROMPT, agent_name="communication_agent"
    )
    planning_agent_node = agent_node_factory(
        planning_llm, PLANNING_SYSTEM_PROMPT, agent_name="planning_agent"
    )
    content_agent_node = agent_node_factory(
        llm_with_tools=content_llm,
        system_prompt=CONTENT_SYSTEM_PROMPT,
        agent_name="content_agent",
    )

    code_agent_node = code_execution_factory(
        llm=code_agent_llm,
        tool_sets=tool_sets,
        agent_name="code_agent",
    )

    def supervisor_node(
        state: State,
        llm_with_tools=supervisor_llm,
        system_prompt=SUPERVISOR_SYSTEM_PROMPT,
        agent_name="supervisor",
    ):
        request_counter["count"] += 1
        request_num = request_counter["count"]

        current_time = get_current_time()

        logger.info("=" * 80)
        logger.info(f"👮 SUPERVISOR REQUEST #{request_num}")
        logger.info("=" * 80)

        logger.info(f"📨 Messages in context: {len(state['messages'])}")

        last_messages = trim_messages(  # fallback if summerizer fails
            state["messages"],
            max_tokens=30000,
            strategy="last",
            token_counter=count_tokens,
            include_system=True,
            start_on="human",
        )

        # if last_messages:
        #     preview = str(last_messages[-3:])
        #     logger.info(f"📝 Latest Input: {preview}")
        # logger.info("=" * 80)

        try:
            summary = state.get("summary", None)
            if summary:
                summary_msg = SystemMessage(
                    content=f"Conversation Summary of previous messages:\n{summary}"
                )
                last_messages = [summary_msg] + last_messages

            message = [SystemMessage(content=SUPERVISOR_SYSTEM_PROMPT)] + last_messages
            logger.info(
                f"🤖 Sending messages to LLM with {count_tokens(message)} tokens"
            )
            response = supervisor_llm.invoke(message)
        except httpx.HTTPStatusError as e:
            if e.response.status_code == 429:
                logger.error("🚫 Rate limit hit in supervisor - stopping")
                return {
                    "next": "FINISH",
                    "messages": [
                        AIMessage(
                            content=f"[{current_time}] [supervisor] [ERROR] Rate limit reached.",
                        )
                    ],
                }
            logger.error(f"HTTP error in supervisor: {e}")
            return {
                "next": "FINISH",
                "messages": [
                    AIMessage(
                        content=f"[{current_time}] [supervisor] [ERROR] {e}",
                    )
                ],
            }
        except httpx.RequestError as e:
            logger.error(f"🚫 Network error in supervisor: {e}")
            return {
                "next": "FINISH",
                "messages": [
                    AIMessage(
                        content=f"[{current_time}] [supervisor] [ERROR] Network unavailable.",
                    )
                ],
            }
        except Exception as e:
            logger.error(f"Error in supervisor_node: {e}")
            return {
                "next": "supervisor",
                "messages": [
                    AIMessage(
                        content=f"[{current_time}] [supervisor] [ERROR] {e}",
                    ),
                ],
            }

            # CASE A: The Supervisor wants to use a Tool (e.g., Search)
        if response.tool_calls:
            logger.info(
                f"🔎 Supervisor is researching: {len(response.tool_calls)} tool calls"
            )
            for i, tool_call in enumerate(response.tool_calls, 1):
                logger.info(f"   Tool #{i}:")
                logger.info(f"      Name: {tool_call.get('name', 'N/A')}")
                logger.info(
                    f"      Args: {json.dumps(tool_call.get('args', {}), indent=10)}"
                )
                logger.info(f"      ID: {tool_call.get('id', 'N/A')}")

            agent_message = AIMessage(
                content=f"[{current_time}] [supervisor] {response.content}",
                tool_calls=getattr(response, "tool_calls", []),
            )

            return {
                "next": "supervisor_tools",  # New internal route
                "messages": [agent_message],
            }

        # CASE B: The Supervisor outputted Text (Routing JSON or Direct Reply)
        content = response.content
        json_match = re.search(r"\{.*\}", content, re.DOTALL)

        if json_match:
            try:
                parsed = json.loads(json_match.group(0))
                step = parsed.get("step", "FINISH")

                agent_message = AIMessage(
                    content=response.content,
                )

                logger.info(f"➡ Supervisor Routing to: {step}")
                return {"next": step, "messages": [agent_message]}
            except Exception as e:
                response = f"Error in json parsing tried to route to other agent: {e}"

                agent_message = AIMessage(
                    content=f"[{current_time}] [supervisor] {response}",
                )

                return {
                    "next": "supervisor",
                    "messages": [agent_message],
                }

        # CASE C: Direct Reply (No Tools, No JSON)
        # The Supervisor decided to answer the user directly
        logger.info("🗣️ Supervisor responding directly")
        if (
            hasattr(response, "content")
            and response.content
            and not response.tool_calls
        ):
            content_preview = (
                response.content[:1000] + "..."
                if len(response.content) > 100000
                else response.content
            )
            logger.info(f"📄 Response content: {content_preview}")
            agent_message = AIMessage(
                content=f"[{current_time}] [supervisor] {response.content}",
            )
            return {
                "next": "FINISH",  # Or loop back to Human
                "messages": [agent_message],
            }

    builder = StateGraph(State)

    builder.add_node("supervisor", supervisor_node)
    builder.add_node("communication_agent", communication_agent_node)
    builder.add_node("planning_agent", planning_agent_node)
    builder.add_node("content_agent", content_agent_node)
    builder.add_node("summerizer_node", summerizer_node)
    builder.add_node("code_agent", code_agent_node)

    builder.add_node(
        "communication_tools",
        ToolNode(tools=communication_tools, handle_tool_errors=True),
    )
    builder.add_node(
        "planning_tools",
        ToolNode(tools=planning_tools, handle_tool_errors=True),
    )
    builder.add_node(
        "content_tools",
        ToolNode(tools=content_tools, handle_tool_errors=True),
    )
    builder.add_node(
        "supervisor_tools",
        ToolNode(tools=supervisor_tools, handle_tool_errors=True),
    )

    builder.add_conditional_edges(
        source=START,
        path=route_start,
        path_map={
            "communication_agent": "communication_agent",
            "planning_agent": "planning_agent",
            "content_agent": "content_agent",
            "supervisor": "supervisor",
            "summerizer_node": "summerizer_node",
        },
    )

    builder.add_edge("summerizer_node", "supervisor")

    builder.add_conditional_edges(
        "supervisor",
        route_after_supervisor,
        {
            "communication_agent": "communication_agent",
            "planning_agent": "planning_agent",
            "content_agent": "content_agent",
            "code_agent": "code_agent",
            "supervisor_tools": "supervisor_tools",
            "supervisor": "supervisor",  # for tool fail fallback to same node and ask the LLM to re-decide
            "FINISH": END,
        },
    )

    builder.add_edge("supervisor_tools", "supervisor")

    builder.add_edge("code_agent", "supervisor")

    builder.add_conditional_edges(
        "communication_agent",
        internal_agent_route,
        {
            "tools": "communication_tools",
            "supervisor": "supervisor",
            "END": END,
        },
    )

    builder.add_edge("communication_tools", "communication_agent")

    builder.add_conditional_edges(
        "planning_agent",
        internal_agent_route,
        {
            "tools": "planning_tools",
            "supervisor": "supervisor",
            "END": END,
        },
    )
    builder.add_edge("planning_tools", "planning_agent")

    builder.add_conditional_edges(
        "content_agent",
        internal_agent_route,
        {
            "tools": "content_tools",
            "supervisor": "supervisor",
            "END": END,
        },
    )
    builder.add_edge("content_tools", "content_agent")

    graph = builder.compile(checkpointer=checkpointer)
    return graph
