import asyncio
from datetime import datetime

import aiosqlite
from langchain_mcp_adapters.client import MultiServerMCPClient

from config.settings import (
    communication_config,
    DB_PATH,
    DEFAULT_THREAD_ID,
    planning_config,
    content_config,
    supervisor_config,
)

from core.graph import build_graph
from utils.checkpointer import CleaningAsyncSqliteSaver
from utils.logger import request_counter, setup_logger

logger = setup_logger(__name__)


async def main():
    start_time = datetime.now()
    logger.info("🚀 Starting Multi-Server Agent")
    logger.info("=" * 80)

    try:
        communication_client = MultiServerMCPClient(communication_config)
        communication_tools = await communication_client.get_tools()
        logger.info(f"📧 Communication Tools: {len(communication_tools)}")

        planning_client = MultiServerMCPClient(planning_config)
        planning_tools = await planning_client.get_tools()
        logger.info(f"✅ Planning Tools: {len(planning_tools)}")
        tool_sets = {"communication": communication_tools, "planning": planning_tools}

        content_client = MultiServerMCPClient(content_config)
        content_tools = await content_client.get_tools()
        logger.info(f"📺 Content Tools: {len(content_tools)}")

        supervisor_client = MultiServerMCPClient(supervisor_config)
        supervisor_tools = await supervisor_client.get_tools()
        logger.info(f"🔍 Supervisor Tools: {len(supervisor_tools)}")

        tool_sets = {
            "communication": communication_tools,
            "planning": planning_tools,
            "content": content_tools,
            "supervisor": supervisor_tools,
        }

        async with aiosqlite.connect(str(DB_PATH)) as connection:
            checkpointer = CleaningAsyncSqliteSaver(connection)
            graph = build_graph(tool_sets, checkpointer)

            # g = graph.get_graph()

            # png_bytes = g.draw_mermaid_png()

            # with open("agent_structure_graph.png", "wb") as f:
            #     f.write(png_bytes)

            config = {"configurable": {"thread_id": DEFAULT_THREAD_ID}}

            while True:
                user_query = input("You: ").strip()

                if user_query.lower() in ["exit", "quit", "bye"]:
                    logger.info("👋 User ended conversation")
                    break

                if not user_query:
                    continue

                logger.info(f"👤 User Query: {user_query}")
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

            logger.info("=" * 80)
            logger.info("✅ Multi-Server Agent execution completed")

    except Exception as e:
        logger.exception(f"❌ An error occurred: {e}")
        raise e


if __name__ == "__main__":
    asyncio.run(main())
