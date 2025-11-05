from dotenv import load_dotenv
import os
import matplotlib.pyplot as plt
import networkx as nx
from langgraph.graph import StateGraph, START, END
from langchain_openai import ChatOpenAI
from typing import Annotated
from typing_extensions import TypedDict
from langgraph.graph.message import add_messages
from langgraph.prebuilt import ToolNode, tools_condition
from langgraph.checkpoint.memory import MemorySaver
from langchain_mcp_adapters.client import MultiServerMCPClient
from langchain.chat_models import init_chat_model
import asyncio
import logging
import json

load_dotenv()
key = os.getenv("openrouter_api_key")

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)-8s | %(name)-20s | %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger(__name__)
request_counter = {"count": 0}

client = MultiServerMCPClient(
    {
        "gmail": {
            "transport": "stdio",
            "command": "python",
            "args": ["D:/Agentic AI/MCP/server.py"],
        }
    }
)


class State(TypedDict):
    messages: Annotated[list, add_messages]


api_key = os.getenv("OPENROUTER_API_KEY")
base_url = "https://openrouter.ai/api/v1"

memory = MemorySaver()
builder = StateGraph(State)


def build_llm_with_tools(tools):
    # llm = init_chat_model("google_genai:gemini-2.0-flash")
    llm = ChatOpenAI(
        model="openai/gpt-oss-safeguard-20b",
        openai_api_key=api_key,
        openai_api_base=base_url,
    )
    logger.info("LLM binding successful")
    return llm.bind_tools(tools)


def agent_node_factory(llm_with_tools):
    def agent_node(state: State):
        request_counter["count"] += 1
        request_num = request_counter["count"]
        logger.info("=" * 80)
        logger.info(f"🔄 LLM REQUEST #{request_num}")
        logger.info("=" * 80)

        last_message = state["messages"][-1]
        if hasattr(last_message, "content"):
            logger.info(f"💬 Last message type: {last_message.__class__.__name__}")
            content_preview = (
                str(last_message.content)[:200] + "..."
                if len(str(last_message.content)) > 200
                else str(last_message.content)
            )
            logger.info(f"📝 Content preview: {content_preview}")

        msg = llm_with_tools.invoke(state["messages"])
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
            logger.info(f"💭 No tool calls - Direct response")

        if hasattr(msg, "content") and msg.content:
            content_preview = (
                msg.content[:300] + "..." if len(msg.content) > 300 else msg.content
            )
            logger.info(f"📄 Response content: {content_preview}")

        # Log token usage if available
        if hasattr(msg, "usage_metadata") and msg.usage_metadata:
            usage = msg.usage_metadata
            logger.info(f"📈 Token usage:")
            logger.info(f"   Input tokens: {usage.get('input_tokens', 'N/A')}")
            logger.info(f"   Output tokens: {usage.get('output_tokens', 'N/A')}")
            logger.info(f"   Total tokens: {usage.get('total_tokens', 'N/A')}")

        logger.info("=" * 80)
        return {"messages": [msg]}

    return agent_node


def build_graph(tools, memory):
    llm_with_tools = build_llm_with_tools(tools)
    agent_node = agent_node_factory(llm_with_tools)
    builder = StateGraph(State)
    builder.add_node("Agent", agent_node)
    tool_node = ToolNode(tools=tools)
    builder.add_node("tools", tool_node)
    builder.add_edge(START, "Agent")
    builder.add_conditional_edges("Agent", tools_condition)
    builder.add_edge("tools", "Agent")
    builder.add_edge("Agent", END)
    return builder.compile(checkpointer=memory)


async def main():
    tools = await client.get_tools()
    logger.info(f"Tools loaded: {len(tools)} tools")
    logger.info(f"Tool names: {[t.name for t in tools]}")
    graph = build_graph(tools, memory)
    config = {"configurable": {"thread_id": "buy_thread"}}
    state = await graph.ainvoke(
        {
            "messages": [
                {
                    "role": "user",
                    "content": "Use the get_unread_emails_tool to retrieve my recent emails. What are the recent mails I have received last 7 days?",
                },
            ]
        },
        config=config,
    )
    final_response = state["messages"][-1]
    logger.info("📤 FINAL RESPONSE:")
    logger.info("=" * 80)
    if hasattr(final_response, "content") and final_response.content:
        print(f"\n{final_response.content}\n")
    else:
        print(f"\n{final_response}\n")


if __name__ == "__main__":
    asyncio.run(main())
