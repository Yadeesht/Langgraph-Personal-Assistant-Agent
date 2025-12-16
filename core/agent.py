import json

from langchain_core.messages import trim_messages
from langgraph.types import interrupt
from langchain_core.messages import HumanMessage, AIMessage, SystemMessage
from langgraph.graph import END

from core.state import State
from utils.context_cleaner import sanitize_history
from utils.logger import request_counter, setup_logger
from utils.token_counter import count_tokens

logger = setup_logger(__name__)


def agent_node_factory(llm_with_tools, system_prompt, agent_name: str):
    def agent_node(state: State):
        request_counter["count"] += 1
        request_num = request_counter["count"]

        logger.info("=" * 80)
        logger.info(f"🔄 LLM REQUEST #{request_num}")
        logger.info("=" * 80)

        logger.info(f"📨 Messages in conversation: {len(state['messages'])}")

        last_messages = trim_messages(
            state["messages"],
            max_tokens=100090,
            strategy="last",
            token_counter=count_tokens,
            include_system=True,
            start_on="human",
        )

        logger.info("=" * 80)
        if last_messages:  # this is for logs purpose only
            content_preview = sanitize_history(last_messages)
            content_preview = json.dumps(content_preview[-10:], indent=2)
            logger.info(f"📝 Content preview: {content_preview}")

        messages = [SystemMessage(content=system_prompt)] + last_messages

        logger.info("=" * 80)

        msg = llm_with_tools.invoke(messages)

        if hasattr(msg, "tool_calls") and msg.tool_calls:
            logger.info(f"🔧 Tool calls made: {len(msg.tool_calls)}")
            for i, tool_call in enumerate(msg.tool_calls, 1):
                logger.info(f"   Tool #{i}:")
                logger.info(f"      Name: {tool_call.get('name', 'N/A')}")
                logger.info(
                    f"      Args: {json.dumps(tool_call.get('args', {}), indent=10)}"
                )
                logger.info(f"      ID: {tool_call.get('id', 'N/A')}")
        else:
            logger.info("💭 No tool calls - Direct response")

        if hasattr(msg, "content") and msg.content and not msg.tool_calls:
            content_preview = (
                msg.content[:1000] + "..." if len(msg.content) > 1000 else msg.content
            )
            logger.info(f"📄 Response content: {content_preview}")

        if hasattr(msg, "usage_metadata") and msg.usage_metadata:
            usage = msg.usage_metadata
            logger.info("📈 Token usage:")
            logger.info(f"   Input tokens: {usage.get('input_tokens', 'N/A')}")
            logger.info(f"   Output tokens: {usage.get('output_tokens', 'N/A')}")
            logger.info(f"   Total tokens: {usage.get('total_tokens', 'N/A')}")

        logger.info("=" * 80)

        if hasattr(msg, "tool_calls") and msg.tool_calls:  # prevent hallucination
            logger.info(
                "🔧 Tool call detected - STRIPPING content to prevent hallucination"
            )
            msg.content = ""

        agent_message = AIMessage(
            content=f"{msg.content}",
            tool_calls=getattr(msg, "tool_calls", []),
            name=agent_name,
        )

        return {"messages": [agent_message]}

    return agent_node


def human_node(state: State):
    last_message = state["messages"][-1]
    user_input = interrupt(last_message.content)
    logger.info(f"👤 User Input: {user_input}")

    return {"messages": [HumanMessage(content=user_input)]}


def route_after_human(state: State):
    messages = state["messages"]
    if len(messages) < 2:
        return END
    last_ai_msg = messages[-2].name

    if last_ai_msg.lower() == "communication_agent":  # case sensitive fix
        return last_ai_msg.lower()
    elif last_ai_msg.lower() == "planning_agent":
        return last_ai_msg.lower()
    elif last_ai_msg.lower() == "content_agent":
        return last_ai_msg.lower()
    return END
