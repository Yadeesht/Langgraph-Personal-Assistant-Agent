import json
import re

import httpx
from langchain_core.messages import AIMessage, SystemMessage, trim_messages
from langgraph.graph import END, START, StateGraph
from langgraph.prebuilt import ToolNode

from config.prompts import (
    COMMUNICATION_SYSTEM_PROMPT,
    CONTENT_SYSTEM_PROMPT,
    PLANNING_SYSTEM_PROMPT,
    SUPERVISOR_SYSTEM_PROMPT,
    VOICE_INTERACTION_PROMPT,
)
from config.settings import DEFAULT_THREAD_ID
from core.agent import (
    agent_node_factory,
    code_execution_factory,
    memory_node_factory,
    summerizer_node,
)
from core.llm import build_llm, build_llm_with_tools
from core.state import State, internal_agent_route, route_after_supervisor, route_start
from utils.helper import (
    count_tokens,
    format_tool_to_text,
    get_current_time,
    request_counter,
    setup_logger,
)
from utils.memory_manager import log_event, sanitize_history

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

    memory_update_node = memory_node_factory()

    async def supervisor_node(
        state: State,
        llm_with_tools=supervisor_llm,
        system_prompt=SUPERVISOR_SYSTEM_PROMPT,
        agent_name="supervisor",
    ):
        request_counter[agent_name] += 1
        request_num = request_counter[agent_name]

        current_time = get_current_time()

        logger.info(f"👮 SUPERVISOR REQUEST #{request_num}")

        logger.info(f"📨 Messages in context: {len(state['messages'])}")

        last_messages = trim_messages(  # fallback if summerizer fails
            state["messages"],
            max_tokens=30000,
            strategy="last",
            token_counter=count_tokens,
            include_system=True,
            start_on="human",
        )

        logger.info("=" * 80)
        if last_messages:  # this is for logs purpose only
            content_preview = sanitize_history(last_messages)
            content_preview = json.dumps(content_preview[-2:], indent=2)
            logger.info(f"📝 Content preview: {content_preview}")

        try:
            summary = state.get("summary", None)
            if summary:
                summary_msg = SystemMessage(
                    content=f"Conversation Summary of previous messages:\n{summary}"
                )
                last_messages = [summary_msg] + last_messages

            is_voice = state.get("configurable", {}).get("is_voice", False)

            final_prompt = system_prompt

            if is_voice:
                final_prompt += VOICE_INTERACTION_PROMPT
                logger.info("voice prompt added")

            message = [SystemMessage(content=final_prompt)] + last_messages
            response = await llm_with_tools.ainvoke(message)

        except httpx.HTTPStatusError as e:
            if e.response.status_code == 429:
                logger.error("🚫 Rate limit hit in supervisor - stopping")
                return {
                    "next": "FINISH",
                    "messages": [
                        AIMessage(
                            content="[ERROR] Rate limit reached.",
                            name=agent_name,
                            additional_kwargs={"timestamp": current_time},
                        )
                    ],
                }
            logger.error(f"HTTP error in supervisor: {e}")
            return {
                "next": "FINISH",
                "messages": [
                    AIMessage(
                        content=f"[ERROR] {e}",
                        name=agent_name,
                        additional_kwargs={"timestamp": current_time},
                    )
                ],
            }
        except httpx.RequestError as e:
            logger.error(f"🚫 Network error in supervisor: {e}")
            return {
                "next": "FINISH",
                "messages": [
                    AIMessage(
                        content="[ERROR] Network unavailable.",
                        name=agent_name,
                        additional_kwargs={"timestamp": current_time},
                    )
                ],
            }
        except Exception as e:
            logger.error(f"Error in supervisor_node: {e}")
            return {
                "next": agent_name,
                "messages": [
                    AIMessage(
                        content=f"[ERROR] {e}",
                        name=agent_name,
                        additional_kwargs={"timestamp": current_time},
                    ),
                ],
            }

            # CASE A: The Supervisor wants to use a Tool
        if response.tool_calls:
            tool_names = []
            for i, tool_call in enumerate(response.tool_calls, 1):
                logger.info(f"   Tool #{i}:")
                logger.info(f"      Name: {tool_call.get('name', 'N/A')}")
                logger.info(
                    f"      Args: {json.dumps(tool_call.get('args', {}), indent=10)}"
                )
                tool_names.append(tool_call.get("name", "N/A"))

            agent_message = AIMessage(
                content=response.content,
                name=agent_name,
                tool_calls=getattr(response, "tool_calls", []),
                additional_kwargs={"timestamp": current_time},
            )

            try:
                await log_event(
                    thread_id=DEFAULT_THREAD_ID,
                    actor=agent_name,
                    message=f"{', '.join([format_tool_to_text(tc.get('name', ''), json.dumps(tc.get('args', {}))) for tc in response.tool_calls])}",
                    metadata={
                        "routing_decision": "supervisor_tools",
                        "request_num": request_num,
                        "type": "tool_call",
                    },
                )
            except Exception as e:
                logger.error(f"Failed to log supervisor tool audit: {e}")

            return {
                "next": "supervisor_tools",
                "messages": [agent_message],
            }

        # CASE B: The Supervisor outputted Text (Routing JSON or Direct Reply)
        content = response.content
        json_match = re.search(r"\{.*\}", content, re.DOTALL)

        if json_match:
            try:
                parsed = json.loads(json_match.group(0))
                next_agent = parsed.get("next")
                instructions = parsed.get("instructions", "")

                if next_agent:
                    logger.info(f"📋 Routing to: {next_agent}")
                    logger.info(f"📝 Instructions: {instructions[:200]}...")

                    agent_message = AIMessage(
                        content=instructions,
                        name="supervisor",
                        additional_kwargs={
                            "timestamp": current_time,
                            "routed_to": next_agent,
                        },
                    )

                    try:
                        await log_event(
                            thread_id=DEFAULT_THREAD_ID,
                            actor="supervisor",
                            message=f"Routing to {next_agent}: {instructions[:500]}",
                            metadata={"next_agent": next_agent},
                        )
                    except Exception as e:
                        logger.error(f"Failed to log supervisor routing event: {e}")

                    return {
                        "next": next_agent,
                        "messages": [agent_message],
                    }

            except json.JSONDecodeError as e:
                logger.warning(
                    f"⚠️ JSON parsing failed, treating as direct response: {e}"
                )
            except Exception as e:
                logger.error(f"❌ Unexpected error parsing routing: {e}")

        # CASE C: The Supervisor decided to answer the user directly
        # (This includes markdown tables, formatted text, etc.)
        if response.content:
            agent_message = AIMessage(
                content=response.content,
                name="supervisor",
                additional_kwargs={"timestamp": current_time},
            )

            try:
                await log_event(
                    thread_id=DEFAULT_THREAD_ID,
                    actor="supervisor",
                    message=f"Direct response: {response.content[:500]}",
                    metadata={},
                )
            except Exception as e:
                logger.error(f"Failed to log supervisor direct response: {e}")

            return {
                "next": "FINISH",
                "messages": [agent_message],
            }

        # CASE D: Fallback - something unexpected happened
        logger.error("⚠️ Supervisor returned unexpected format")
        return {
            "next": "FINISH",
            "messages": [
                AIMessage(
                    content="I apologize, but I encountered an unexpected issue processing your request.",
                    name="supervisor",
                    additional_kwargs={"timestamp": current_time},
                )
            ],
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

    builder.add_node("memory_update_node", memory_update_node)

    builder.add_conditional_edges(
        source=START,
        path=route_start,
        path_map={
            "communication_agent": "communication_agent",
            "planning_agent": "planning_agent",
            "content_agent": "content_agent",
            "summerizer_node": "summerizer_node",
            "memory_update_node": "memory_update_node",
            "supervisor": "supervisor",
        },
    )

    builder.add_edge("summerizer_node", "supervisor")
    builder.add_edge("memory_update_node", "supervisor")

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
