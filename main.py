import asyncio
import time
from datetime import datetime

import aiosqlite
from langchain_core.messages import AIMessage, HumanMessage
from langchain_mcp_adapters.client import MultiServerMCPClient

from config.settings import (
    CHECKPOINT_DB,
    DEFAULT_THREAD_ID,
    communication_config,
    planning_config,
    content_config,
    supervisor_config,
)
from core.graph import build_graph
from utils.helper import (
    AsyncSqliteSaver,
    request_counter,
    setup_logger,
)
from utils.memory_manager import log_event

logger = setup_logger(__name__)


AGENT_MESSAGE_KEY = {
    "supervisor": "supervisor_messages",
    "communication_agent": "communication_messages",
    "planning_agent": "planning_messages",
    "document_agent": "document_messages",
    "presentation_agent": "presentation_messages",
    "data_agent": "data_messages",
    "code_agent": "code_messages",
}


async def keyword_listener(queue, loop, agent_state):
    while True:
        try:
            user_input = await loop.run_in_executor(None, input)
            if user_input.strip():
                agent_state["last_interaction"] = time.time()
                await queue.put(("TEXT", user_input.strip()))
        except EOFError:
            break
        except Exception as e:
            logger.error(f"Error in keyword listener: {e}")
            await asyncio.sleep(1)


async def main():
    start_time = datetime.now()
    logger.info("🚀 Starting Agent")

    try:
        communication_client = MultiServerMCPClient(communication_config)
        communication_tools = await communication_client.get_tools()
        logger.info(f"📧 Communication Tools: {len(communication_tools)}")

        planning_client = MultiServerMCPClient(planning_config)
        planning_tools = await planning_client.get_tools()
        logger.info(f"✅ Planning Tools: {len(planning_tools)}")

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

        async with aiosqlite.connect(str(CHECKPOINT_DB)) as connection:
            checkpointer = AsyncSqliteSaver(connection)
            graph = build_graph(tool_sets, checkpointer)

            # g = graph.get_graph()

            # png_bytes = g.draw_mermaid_png()

            # with open("docs/images/agent_structure_graph.png", "wb") as f:
            #     f.write(png_bytes)

            config = {
                "configurable": {
                    "thread_id": DEFAULT_THREAD_ID,
                }
            }

            agent_state = {"last_interaction": 0}

            event_queue = asyncio.Queue()
            loop = asyncio.get_running_loop()

            asyncio.create_task(keyword_listener(event_queue, loop, agent_state))

            logger.info("⌨️ Type your message")
            logger.info("💡 Type 'exit' or 'quit' to stop\n")

            while True:
                _, query = await event_queue.get()

                agent_state["last_interaction"] = time.time()

                if query.lower() in ["exit", "quit", "bye"]:
                    logger.info("👋 Goodbye!")
                    break

                logger.info(f"👤 You: {query}")

                try:
                    await log_event(
                        thread_id=DEFAULT_THREAD_ID,
                        actor="Human_node",
                        message=query,
                        metadata={},
                    )
                except Exception as e:
                    logger.error(f"Failed to log human_node audit event: {e}")

                request_counter.start_turn(query)
                snapshot = await graph.aget_state(config)
                current_agent = "supervisor"
                if snapshot and snapshot.values:
                    current_agent = snapshot.values.get("current_agent", "supervisor")

                context_key = AGENT_MESSAGE_KEY.get(
                    current_agent, "supervisor_messages"
                )
                human_message = HumanMessage(content=query)

                new_input = {
                    "messages": [human_message],
                    context_key: [human_message],
                }

                state = await graph.ainvoke(new_input, config=config)
                request_counter.end_turn()

                active_agent = state.get("current_agent", current_agent)
                response_key = AGENT_MESSAGE_KEY.get(
                    active_agent, "supervisor_messages"
                )

                messages = state.get(response_key) or state.get("messages", [])
                last_msg = messages[-1] if messages else None

                if isinstance(last_msg, AIMessage) and last_msg.content:
                    final_response = last_msg.content
                    logger.info(f"🤖 Agent: {final_response}")

                    agent_state["last_interaction"] = time.time()

            end_time = datetime.now()
            execution_time = (end_time - start_time).total_seconds()
            logger.info(
                f"🎯 Session complete | "
                f"LLM requests: {request_counter.session_total()} | "
                f"Messages: {len(state['messages'])} | "
                f"Time: {execution_time:.2f}s"
            )

    except Exception as e:
        logger.exception(f"❌ An error occurred: {e}")
        raise e


if __name__ == "__main__":
    asyncio.run(main())
