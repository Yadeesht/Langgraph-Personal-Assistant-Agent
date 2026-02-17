import asyncio
import time
from datetime import datetime

import aiosqlite
from langchain_mcp_adapters.client import MultiServerMCPClient

from config.settings import (
    CHECKPOINT_DB,
    DEFAULT_THREAD_ID,
    communication_config,
    content_config,
    planning_config,
    supervisor_config,
)
from core.graph import build_graph
from core.voice_inference import VoiceInference
from utils.helper import (
    AsyncSqliteSaver,
    clean_text_for_tts,
    request_counter,
    setup_logger,
)
from utils.memory_manager import log_event

logger = setup_logger(__name__)

SESSION_TIMEOUT = 600
WAKE_WORD = "hey_jarvis"


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


async def voice_listener(queue, voice_agent, loop, agent_state):
    while True:
        try:
            time_since = time.time() - agent_state["last_interaction"]
            is_session_active = time_since < SESSION_TIMEOUT

            if not is_session_active:
                print("type or say the jarvis", end="\r", flush=True)
                text = await loop.run_in_executor(None, voice_agent.wait_for_wake_word)
            else:
                print("type or say what you need", end="\r", flush=True)
                text = await loop.run_in_executor(None, voice_agent.listen)

            print(" " * 50, end="\r", flush=True)

            if text.strip():
                agent_state["last_interaction"] = time.time()
                await queue.put(("VOICE", text.strip()))
        except Exception as e:
            logger.error(f"Error in voice listener: {e}")
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

        async with aiosqlite.connect(str(CHECKPOINT_DB)) as connection:
            checkpointer = AsyncSqliteSaver(connection)
            graph = build_graph(tool_sets, checkpointer)

            # g = graph.get_graph()

            # png_bytes = g.draw_mermaid_png()

            # with open("docs/images/agent_structure_graph.png", "wb") as f:
            #     f.write(png_bytes)

            config = {"configurable": {"thread_id": DEFAULT_THREAD_ID}}

            voice = VoiceInference()

            agent_state = {"last_interaction": 0}

            event_queue = asyncio.Queue()
            loop = asyncio.get_running_loop()

            # Start listeners
            asyncio.create_task(keyword_listener(event_queue, loop, agent_state))
            asyncio.create_task(voice_listener(event_queue, voice, loop, agent_state))

            logger.info(f"🎤 Say '{WAKE_WORD}' or type your message")
            logger.info("💡 Type 'exit' or 'quit' to stop\n")

            while True:
                source, query = await event_queue.get()

                agent_state["last_interaction"] = time.time()

                if query.lower() in ["exit", "quit"]:
                    logger.info("=" * 80)
                    logger.info("👋 Goodbye!")
                    logger.info("=" * 80)
                    break

                logger.info("=" * 80)
                logger.info(f"👤 You: {query}")
                logger.info("=" * 80)

                try:
                    await log_event(
                        thread_id=DEFAULT_THREAD_ID,
                        actor="Human_node",
                        message=query,
                        metadata={},
                    )
                except Exception as e:
                    logger.error(f"Failed to log human_node audit event: {e}")

                state = await graph.ainvoke(
                    {"messages": [{"role": "user", "content": query}]},
                    config=config,
                )

                last_msg = state["messages"][-1]
                if last_msg.type == "ai" and last_msg.content:
                    final_response = last_msg.content
                    print(f"🤖 Agent: {final_response}")
                    print(f"{'─' * 50}\n")

                    if source == "VOICE":
                        clean_resp = clean_text_for_tts(final_response)
                        await loop.run_in_executor(None, voice.speak, clean_resp)
                        await asyncio.sleep(0.5)

                    agent_state["last_interaction"] = time.time()

            logger.info("=" * 80)
            logger.info("🎯 EXECUTION SUMMARY")
            logger.info("=" * 80)
            logger.info("✅ Status: Success")
            logger.info(
                f"📊 Total LLM requests: {request_counter['supervisor'] + request_counter['sub_agents']}"
            )
            logger.info(f"💬 Total messages in conversation: {len(state['messages'])}")

            logger.info("📝 Conversation flow:")
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
