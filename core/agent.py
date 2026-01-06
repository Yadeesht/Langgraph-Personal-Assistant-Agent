import json
from datetime import datetime
import httpx

import pytz
from langchain_core.messages import (
    AIMessage,
    SystemMessage,
    trim_messages,
)

from core.state import State
from utils.context_manager import sanitize_history
from utils.helper import request_counter, setup_logger
from utils.helper import count_tokens

logger = setup_logger(__name__)


def get_current_time():
    now = datetime.now(pytz.timezone("Asia/Kolkata"))
    return now.strftime("%Y-%m-%d %H:%M:%S IST")


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
        logger.info(f"📨 Trimmed messages: {last_messages[:4]}")

        logger.info("=" * 80)
        if last_messages:  # this is for logs purpose only
            content_preview = sanitize_history(last_messages)
            content_preview = json.dumps(content_preview[-10:], indent=2)
            logger.info(f"📝 Content preview: {content_preview}")

        messages = [SystemMessage(content=system_prompt)] + last_messages

        logger.info("=" * 80)

        try:
            msg = llm_with_tools.invoke(messages)
        except httpx.HTTPStatusError as e:
            if e.response.status_code == 429:
                logger.error("🚫 Rate limit hit - stopping execution")
                return {
                    "messages": [
                        AIMessage(
                            content="[ERROR] Rate limit reached. Please retry later.",
                            name=agent_name,
                        )
                    ]
                }
            logger.error(f"HTTP error: {e}")
            raise
        except httpx.RequestError as e:
            logger.error(f"🚫 Network error - no internet connection: {e}")
            return {
                "messages": [
                    AIMessage(
                        content="[ERROR] Network unavailable. Check connection.",
                        name=agent_name,
                    )
                ]
            }
        except Exception as e:
            logger.error(f"Unexpected error: {e}")
            raise

        current_time = get_current_time()

        raw_content = msg.content if msg.content else ""

        if raw_content:
            final_content = f"[{current_time}] {raw_content}"
        else:
            final_content = raw_content

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
                msg.content[:1000] + "..."
                if len(msg.content) > 1000000
                else msg.content
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
            msg.content = ""

        agent_message = AIMessage(
            content=final_content,
            tool_calls=getattr(msg, "tool_calls", []),
            additional_kwargs={"name": agent_name},
        )
        logger.info(f"🚀 LLM sends this: {agent_message}")
        return {"messages": [agent_message]}

    return agent_node
