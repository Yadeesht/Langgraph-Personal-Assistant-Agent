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
from langchain_google_genai import ChatGoogleGenerativeAI
import asyncio
import logging

load_dotenv()
# key = os.getenv("openrouter_api_key")

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

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


# api_key = os.getenv("OPENROUTER_API_KEY")
# base_url = "https://openrouter.ai/api/v1"

memory = MemorySaver()
builder = StateGraph(State)


def build_llm_with_tools(tools):
    llm = init_chat_model("google_genai:gemini-2.0-flash")
    logger.info("LLM binding successful")
    return llm.bind_tools(tools)


def agent_node_factory(llm_with_tools):
    def agent_node(state: State):
        msg = llm_with_tools.invoke(state["messages"])
        logger.info("node successful")
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
                    "role": "system",
                    "content": """You are a helpful email assistant. When you need to use a tool, 
                    you MUST respond with proper JSON tool calls in this format:
                    {"name": "tool_name", "arguments": {"param": "value"}}
                    
                    Available tools:
                    - get_unread_emails_tool: Retrieves unread emails (params: date=10)
                    - read_email_tool: Reads specific email (params: email_id)
                    - search_emails_tool: Searches emails (params: query, max_results)
                    """,
                },
                {
                    "role": "user",
                    "content": "Use the get_unread_emails_tool to retrieve my recent emails. What are the recent mails I have received?",
                },
            ]
        },
        config=config,
    )
    logger.info("state successful")
    print(state)


if __name__ == "__main__":
    asyncio.run(main())
