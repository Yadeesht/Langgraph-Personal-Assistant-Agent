import json
from datetime import datetime

from langchain_core.messages import trim_messages
from langgraph.types import interrupt
from langchain_core.messages import HumanMessage
from langgraph.graph import END

from core.state import State
from utils.context_cleaner import sanitize_history
from utils.logger import request_counter, setup_logger
from utils.token_counter import count_tokens

logger = setup_logger(__name__)


def agent_node_factory(llm_with_tools, system_prompt):
    def agent_node(state: State):
        request_counter["count"] += 1
        request_num = request_counter["count"]

        logger.info("=" * 80)
        logger.info(f"🔄 LLM REQUEST #{request_num}")
        logger.info("=" * 80)

        logger.info(f"📨 Messages in conversation: {len(state['messages'])}")

        last_messages = trim_messages(
            state["messages"],
            max_tokens=2000,
            strategy="last",
            token_counter=count_tokens,
            include_system=True,
            start_on="human",
        )

        try:
            formatted_prompt = system_prompt.format(
                current_time=datetime.now().strftime("%Y-%m-%d %H:%M")
            )
        except KeyError:
            # If the prompt (like Communication Agent) doesn't have {current_time}, use as is
            formatted_prompt = system_prompt
        except Exception as e:
            logger.error(f"Error formatting prompt: {e}")
            formatted_prompt = system_prompt

        logger.info("=" * 80)
        if last_messages:
            content_preview = sanitize_history(last_messages)
            content_preview = json.dumps(content_preview[-10:], indent=2)
            logger.info(f"📝 Content preview: {content_preview}")

        messages = [{"role": "system", "content": formatted_prompt}] + last_messages

        logger.info("=" * 80)

        msg = llm_with_tools.invoke(messages)

        # logger.info(f"✅ LLM RESPONSE RECEIVED: {sanitize_history([msg])}")
        # logger.info(f"📊 Response type: {msg.__class__.__name__}")

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

        if hasattr(msg, "content") and msg.content:
            content_preview = (
                msg.content[:1000] + "..." if len(msg.content) > 1000 else msg.content
            )
            logger.info(f"📄 Response content: {content_preview}")
            with open("D:\\Agentic AI\\core\\result.txt", "w", encoding="utf-8") as f:
                f.write(content_preview)

        if hasattr(msg, "usage_metadata") and msg.usage_metadata:
            usage = msg.usage_metadata
            logger.info("📈 Token usage:")
            logger.info(f"   Input tokens: {usage.get('input_tokens', 'N/A')}")
            logger.info(f"   Output tokens: {usage.get('output_tokens', 'N/A')}")
            logger.info(f"   Total tokens: {usage.get('total_tokens', 'N/A')}")

        logger.info("=" * 80)

        return {"messages": [msg]}

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

    if last_ai_msg == "communication_agent":
        return last_ai_msg
    return END
