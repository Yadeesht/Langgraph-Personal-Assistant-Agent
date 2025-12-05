import asyncio
from datetime import datetime

import aiosqlite
from langchain_mcp_adapters.client import MultiServerMCPClient

from config.settings import (
    DB_PATH,
    DEFAULT_THREAD_ID,
    COMMUNICATION_SERVER,
    PRODUCTIVITY_SERVER,
)
from core.graph import build_graph
from utils.checkpointer import CleaningAsyncSqliteSaver
from utils.logger import request_counter, setup_logger

logger = setup_logger(__name__)

comm_config = {
    "communication": {
        "transport": "stdio",
        "command": "python",
        "args": [str(COMMUNICATION_SERVER)],
    }
}

prod_config = {
    "productivity": {
        "transport": "stdio",
        "command": "python",
        "args": [str(PRODUCTIVITY_SERVER)],
    }
}


async def main():
    start_time = datetime.now()
    logger.info("🚀 Starting Multi-Server Agent")
    logger.info("=" * 80)

    try:
        # Initialize MCP clients (no context manager)
        comm_client = MultiServerMCPClient(comm_config)
        comm_tools = await comm_client.get_tools()
        logger.info(f"📧 Communication Tools: {len(comm_tools)}")

        prod_client = MultiServerMCPClient(prod_config)
        prod_tools = await prod_client.get_tools()
        logger.info(f"✅ Productivity Tools: {len(prod_tools)}")

        tool_sets = {"communication": comm_tools, "productivity": prod_tools}

        async with aiosqlite.connect(str(DB_PATH)) as conn:
            checkpointer = CleaningAsyncSqliteSaver(conn)
            graph = build_graph(tool_sets, checkpointer)
            config = {"configurable": {"thread_id": DEFAULT_THREAD_ID}}

            while True:
                user_query = input("You: ").strip()

                if user_query.lower() in ["exit", "quit", "bye"]:
                    logger.info("👋 User ended conversation")
                    break

                if not user_query:
                    continue

                logger.info(f"👤 User Query: {user_query}")
                logger.info("=" * 80)
                state = await graph.ainvoke(
                    {
                        "messages": [
                            {
                                "role": "user",
                                "content": user_query,
                            }
                        ]
                    },
                    config=config,
                )

            logger.info("=" * 80)
            logger.info("🎯 EXECUTION SUMMARY")
            logger.info("=" * 80)
            logger.info("✅ Status: Success")
            logger.info(f"📊 Total LLM requests: {request_counter['count']}")
            logger.info(f"💬 Total messages in conversation: {len(state['messages'])}")

            logger.info("📝 Conversation flow:")
            for i, msg in enumerate(state["messages"], 1):
                msg_type = msg.__class__.__name__
                logger.info(f"   {i}. {msg_type}")

            end_time = datetime.now()
            execution_time = (end_time - start_time).total_seconds()
            logger.info(f"⏱️  Execution time: {execution_time:.2f} seconds")
            logger.info("=" * 80)

            final_response = state["messages"][-1]
            logger.info("📤 FINAL RESPONSE:")
            logger.info("=" * 80)
            if hasattr(final_response, "content") and final_response.content:
                print(f"\n{final_response.content}\n")
            else:
                print(f"\n{final_response}\n")

            logger.info("=" * 80)
            logger.info("✅ Multi-Server Agent execution completed")

    except Exception as e:
        logger.exception(f"❌ An error occurred: {e}")
        raise e


if __name__ == "__main__":
    asyncio.run(main())
