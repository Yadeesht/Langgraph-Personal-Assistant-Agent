import json
import httpx
import asyncio
from langchain_core.messages import (
    AIMessage,
    SystemMessage,
    trim_messages,
    RemoveMessage,
)

import aiosqlite
from datetime import datetime
import sys
from pathlib import Path

root = Path(__file__).parent.parent
sys.path.append(str(root))

from config.settings import MEMORY_DB, DEFAULT_THREAD_ID
from utils.audit_manager import log_event


from core.state import State
from utils.context_manager import sanitize_history
from utils.helper import request_counter, setup_logger, count_tokens, get_current_time
from config.prompts import HISTORY_SUMMARIZE_PROMPT
from core.llm import build_llm
from core.codeagent import CodeExecutionAgent


logger = setup_logger(__name__)


def agent_node_factory(llm_with_tools, system_prompt, agent_name: str):
    async def agent_node(state: State):
        request_counter["count"] += 1
        request_num = request_counter["count"]

        current_time = get_current_time()

        logger.info("=" * 80)
        logger.info(f"🔄 LLM REQUEST #{request_num}")
        logger.info("=" * 80)

        logger.info(f"📨 Messages in conversation: {len(state['messages'])}")

        last_messages = trim_messages(  # fallback if summerizer fails
            state["messages"],
            max_tokens=30000,
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

        logger.info("=" * 80)

        try:
            summary = state.get("summary", None)
            if summary:
                logger.info("📝 Including conversation summary in the prompt.")
                summary_msg = SystemMessage(
                    content=f"Conversation Summary of previous messages:\n{summary}"
                )
                last_messages = [summary_msg] + last_messages

            messages = [SystemMessage(content=system_prompt)] + last_messages
            logger.info(
                f"🤖 Sending messages to LLM with {count_tokens(messages)} tokens"
            )
            msg = await llm_with_tools.ainvoke(messages)

        except httpx.HTTPStatusError as e:
            if e.response.status_code == 429:
                logger.error("🚫 Rate limit hit - stopping execution")
                return {
                    "messages": [
                        AIMessage(
                            content=f"[{current_time}] [{agent_name}] [ERROR] Rate limit reached. Please retry later.",
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
                        content=f"[{current_time}] [{agent_name}] [ERROR] Network unavailable. Check connection.",
                    )
                ]
            }
        except Exception as e:
            logger.error(f"Unexpected error: {e}")
            raise

        raw_content = msg.content if msg.content else ""

        if raw_content:
            final_content = f"[{current_time}] [{agent_name}] {raw_content}"
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

        # if hasattr(msg, "usage_metadata") and msg.usage_metadata:
        #     usage = msg.usage_metadata
        #     logger.info("📈 Token usage:")
        #     logger.info(f"   Input tokens: {usage.get('input_tokens', 'N/A')}")
        #     logger.info(f"   Output tokens: {usage.get('output_tokens', 'N/A')}")
        #     logger.info(f"   Total tokens: {usage.get('total_tokens', 'N/A')}")

        logger.info("=" * 80)

        if hasattr(msg, "tool_calls") and msg.tool_calls:  # prevent hallucination
            msg.content = ""

        agent_message = AIMessage(
            content=final_content,
            tool_calls=getattr(msg, "tool_calls", []),
        )

        if hasattr(agent_message, "content") and isinstance(agent_message.content, str):
            if "CLARIFICATION NEEDED:" in agent_message.content.upper():
                logger.info("❓ Clarification needed - routing to human")
                agent_name = "Clarification Agent"

            if "TALK TO USER:" in agent_message.content.upper():
                logger.info("💬 Agent wants to talk to user - routing to human")
                agent_name = "Clarification Agent"

        # Log agent response for audit trail
        try:
            await log_event(
                thread_id=DEFAULT_THREAD_ID,
                actor=agent_name,
                message=final_content if final_content else "Tool calls made",
                metadata={
                    "tool_calls": len(msg.tool_calls)
                    if hasattr(msg, "tool_calls")
                    else 0,
                    "request_num": request_num,
                },
            )
        except Exception as e:
            logger.error(f"Failed to log audit event: {e}")

        return {"messages": [agent_message]}

    return agent_node


def code_execution_factory(llm, tool_sets, agent_name: str):
    async def code_executor(state: State):
        current_time = get_current_time()  # system prompt should have this need to do

        last_messages = trim_messages(
            state["messages"],
            max_tokens=30000,
            strategy="last",
            token_counter=count_tokens,
            include_system=True,
            start_on="human",
        )

        summary = state.get("summary", None)
        if summary:
            logger.info("📝 Including conversation summary in the prompt.")
            summary_msg = SystemMessage(
                content=f"Conversation Summary of previous messages:\n{summary}"
            )
            last_messages = [summary_msg] + last_messages

        try:
            agent = CodeExecutionAgent(llm, tool_sets)

            try:
                loop = asyncio.get_event_loop()
            except RuntimeError:
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)

            msg = loop.run_until_complete(agent.execute_workflow(last_messages))

        except Exception as e:
            logger.error(f"Code execution error: {e}")
            raw_content = f"Code execution failed: {str(e)}"
            agent_message = AIMessage(
                content=f"[{current_time}] [{agent_name}] {raw_content}"
            )
            return {"messages": [agent_message]}

        # Format result
        raw_content = (
            f"Status: {msg.get('status', 'unknown')}\n"
            f"Summary: {msg.get('summary', 'No summary')}\n"
        )

        final_content = f"[{current_time}] [{agent_name}] {raw_content}"
        agent_message = AIMessage(content=final_content)

        return {"messages": [agent_message]}

    return code_executor


async def summerizer_node(state: State):
    logger.info("📝 Summarizer node activated to condense conversation history.")

    state["number_of_summaries_today"] = state.get("number_of_summaries_today", 0) + 1
    # right now the prompt is not aware of we sending the summary and to summerize previous messages too
    messages = f"Summary:\n{state.get('summary', '')}\n\n Chat Messages:\n{state['messages'][:-15]}"
    llm = build_llm()
    messages = [SystemMessage(content=HISTORY_SUMMARIZE_PROMPT)] + messages
    cleaned = await llm.ainvoke(messages)

    summarized_content = cleaned.content

    delete_actions = [RemoveMessage(id=m.id) for m in messages]

    # Log summarization event for audit trail
    try:
        await log_event(
            thread_id=DEFAULT_THREAD_ID,
            actor="summerizer_node",
            message=f"summerized content of previous text: {summarized_content}",
            metadata={
                f"Archived {len(delete_actions)} messages.",
            },
        )
    except Exception as e:
        logger.error(f"Failed to log summarizer audit event: {e}")

    return {"summary": summarized_content, "messages": delete_actions}


async def updation_knowledge_graph(
    state: State, thread_id: str, db_path: str = MEMORY_DB
):
    try:
        from rag.knowledge_graph import KnowledgeGraph

        logger.info("🔄 Starting knowledge graph update process.")
        last_update = state.get("last_knowledgegraph_timestamp", 0.0)

        if isinstance(last_update, (int, float)):
            last_update_str = datetime.fromtimestamp(last_update).isoformat()
        else:
            last_update_str = str(last_update)

        query = "SELECT actor,message FROM human_logs WHERE thread_id = ? AND actor IN (?,?,?) AND timestamp > ? ORDER BY timestamp ASC;"

        target_actors = ("human", "supervisor", "clarification_agent")

        async with aiosqlite.connect(db_path) as db:
            async with db.execute(
                query, (thread_id, *target_actors, last_update_str)
            ) as cursor:
                rows = await cursor.fetchall()
                logger.info(f"🔎 Found {len(rows)} new log entries in DB.")
        if not rows:
            logger.info("↩️ No new logs found since last update. Exiting.")  # NEW LOG
            return

        extraction_context = "\n".join([f"{actor}: {msg}" for actor, msg in rows])
        kg = KnowledgeGraph()
        candidates_json = kg.generate_entity_relation(extraction_context)

        logger.info(
            f"Extracted candidates for KG update: {json.dumps(candidates_json, indent=2)}"
        )

        entities = candidates_json.get("candidates", {}).get("entities", [])
        if not entities:
            return

        types_df = kg.search_similar_node(entities)

        final_update_json = kg.validate_entity_relation(types_df, candidates_json)
        resolution = final_update_json.get("resolution", {})

        logger.info(
            f"The validated KG update resolution: {json.dumps(resolution, indent=2)}"
        )
        for entity in resolution.get("entities", []):
            action = entity.get("action", "DISCARD").upper()

            if action == "CREATE":
                kg.add_entity(
                    node_id=entity["id"],
                    node_type=entity.get("type", "unknown"),
                    search_keywords=", ".join(entity.get("keywords", [])),
                    description=entity.get("description", ""),
                )
            elif action == "UPDATE":
                kg.modify_entity(
                    node_id=entity["id"],
                    updates={
                        "type": entity.get("type"),
                        "description": entity.get("description"),
                        "search_keywords": ", ".join(entity.get("keywords", [])),
                    },
                )

        for rel in resolution.get("relationships", []):
            action = rel.get("action", "DISCARD").upper()

            if action == "CREATE":
                kg.add_relationship(
                    source=rel["source"],
                    target=rel["target"],
                    relation_type=rel.get("relation_type", "unknown"),
                )
            elif action == "UPDATE":
                kg.modify_relationship(
                    source=rel["source"],
                    target=rel["target"],
                    relation_type=rel.get("relation_type", "unknown"),
                )
        logger.info("✅ Knowledge graph update process completed successfully.")

    except Exception as e:
        logger.error(f"Knowledge graph update failed: {e}")
