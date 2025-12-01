import json

from langchain_core.messages import trim_messages

from config.prompts import SYSTEM_PROMPT
from core.state import State
from utils.logger import request_counter, setup_logger
from utils.token_counter import count_tokens

logger = setup_logger(__name__)


def agent_node_factory(llm_with_tools):
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
        logger.info("=" * 80)
        if last_messages:
            content_preview = (
                last_messages[:20] + ["..."]
                if len(str(last_messages)) > 20
                else str(last_messages)
            )
            logger.info(f"📝 Content preview: {content_preview}")

        messages = [{"role": "system", "content": SYSTEM_PROMPT}] + last_messages

        logger.info("=" * 80)

        msg = llm_with_tools.invoke(messages)
        logger.info(f"✅ LLM RESPONSE RECEIVED: {msg}")
        logger.info(f"📊 Response type: {msg.__class__.__name__}")

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
                msg.content[:300] + "..." if len(msg.content) > 300 else msg.content
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
