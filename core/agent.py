import json
import httpx
import asyncio
from langchain_core.messages import (
    AIMessage,
    SystemMessage,
    trim_messages,
    RemoveMessage,
    HumanMessage,
)

import aiosqlite
from datetime import datetime
import sys
import re
from pathlib import Path
import time

from rag.episodic_rag import EpisodicRAG

root = Path(__file__).parent.parent
sys.path.append(str(root))

from config.settings import MEMORY_DB, DEFAULT_THREAD_ID
from utils.memory_manager import log_event


from core.state import State
from utils.memory_manager import sanitize_history
from utils.helper import (
    request_counter,
    setup_logger,
    count_tokens,
    get_current_time,
    format_tool_to_text,
)
from config.prompts import HISTORY_SUMMARIZE_PROMPT
from core.llm import build_llm
from core.codeagent import CodeExecutionAgent


logger = setup_logger(__name__)


def agent_node_factory(llm_with_tools, system_prompt, agent_name: str):
    async def agent_node(state: State):

        current_agent_name = agent_name
        request_counter["sub_agents"] += 1
        request_num = request_counter["sub_agents"]

        current_time = get_current_time()

        logger.info("\n")
        logger.info("=" * 80)
        logger.info(f"🔄 LLM REQUEST #{request_num}")
        logger.info("=" * 80)

        logger.info(f"📨 Messages in conversation: {len(state['messages'])}")

        messages = state["messages"]
        filtered_messages = []
        routing_found = False

        for msg in reversed(messages):
            if (
                getattr(msg, "name", "") == "supervisor"
                and isinstance(msg, AIMessage)
                and msg.additional_kwargs.get("routed_to") == current_agent_name
            ):
                instruction_msg = HumanMessage(
                    f"Assigned Task from supervisor:\n{msg.content}"
                )
                filtered_messages.insert(0, instruction_msg)
                routing_found = True
                break
            else:
                filtered_messages.insert(0, msg)

        if not routing_found:
            last_messages = trim_messages(
                messages,
                max_tokens=30000,
                strategy="last",
                token_counter=count_tokens,
                include_system=True,
                start_on="human",
            )
            summary = state.get("summary", None)
            if summary:
                logger.info("📝 Including global summary in the prompt.")
                summary_msg = SystemMessage(content=f"Conversation Summary:\n{summary}")
                last_messages = [summary_msg] + last_messages
        else:
            last_messages = filtered_messages

        logger.info("=" * 80)
        if last_messages:  # this is for logs purpose only
            content_preview = sanitize_history(last_messages)
            content_preview = json.dumps(content_preview, indent=2)
            logger.info(f"📝 Content preview: {content_preview}")

        logger.info("=" * 80)

        try:
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
                            content="[ERROR] Rate limit reached. Please retry later.",
                            name=current_agent_name,
                            additional_kwargs={"timestamp": current_time},
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
                        name=current_agent_name,
                        additional_kwargs={"timestamp": current_time},
                    )
                ]
            }
        except Exception as e:
            logger.error(f"Unexpected error: {e}")
            raise

        raw_content = msg.content if msg.content else ""
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

        if hasattr(msg, "content") and msg.content and not msg.tool_calls:
            content_preview = (
                msg.content[:1000] + "..."
                if len(msg.content) > 1000000
                else msg.content
            )

        logger.info("=" * 80)

        agent_message = AIMessage(
            content=final_content,
            name=current_agent_name,
            tool_calls=getattr(msg, "tool_calls", []),
        )

        if hasattr(agent_message, "content") and isinstance(agent_message.content, str):
            if ("CLARIFICATION NEEDED:" in agent_message.content.upper()) or (
                "TALK TO USER:" in agent_message.content.upper()
            ):
                current_agent_name = "Clarification Agent"
                final_content = re.sub("CLARIFICATION NEEDED", "", final_content)
                final_content = re.sub("TALK TO USER", "", final_content)

        try:
            if final_content:
                await log_event(
                    thread_id=DEFAULT_THREAD_ID,
                    actor=current_agent_name,
                    message=final_content,
                    metadata={
                        "request_num": request_num,
                        "type": "content",
                    },
                )

            if hasattr(msg, "tool_calls") and msg.tool_calls:
                await log_event(
                    thread_id=DEFAULT_THREAD_ID,
                    actor=current_agent_name,
                    message=f"{', '.join([format_tool_to_text(tc.get('name', ''), json.dumps(tc.get('args', {}))) for tc in msg.tool_calls])}",
                    metadata={"type": "tool_call"},
                )
        except Exception as e:
            logger.error(f"Failed to log audit event: {e}")

        messages_to_return = [agent_message]

        if final_content and "FINAL ANSWER:" in final_content.upper():
            cleanup_actions = []

            for m in reversed(state["messages"]):
                if getattr(m, "name", "") == "supervisor" and isinstance(m, AIMessage):
                    break

                if m.type in ["tool", "ai"] and m.id:
                    cleanup_actions.append(RemoveMessage(m.id))

            messages_to_return = cleanup_actions + messages_to_return

        return {"messages": messages_to_return}

    return agent_node


def code_execution_factory(llm, tool_sets, agent_name: str):
    async def code_executor(state: State):
        current_time = get_current_time()  # system prompt should have this need to do
        current_agent_name = agent_name

        messages = state["messages"]
        filtered_messages = []
        routing_found = False

        for msg in reversed(messages):
            if (
                getattr(msg, "name", "") == "supervisor"
                and isinstance(msg, AIMessage)
                and msg.additional_kwargs("routed_to") == current_agent_name
            ):
                instruction_msg = HumanMessage(
                    f"Assigned Task from supervisor:\n{msg.content}"
                )
                filtered_messages.insert(0, instruction_msg)
                routing_found = True
                break
            else:
                filtered_messages.insert(0, msg)

        if not routing_found:
            last_messages = trim_messages(
                messages,
                max_tokens=30000,
                strategy="last",
                token_counter=count_tokens,
                include_system=True,
                start_on="human",
            )
            summary = state.get("summary", None)
            if summary:
                logger.info("📝 Including global summary in the prompt.")
                summary_msg = SystemMessage(content=f"Conversation Summary:\n{summary}")
                last_messages = [summary_msg] + last_messages
        else:
            last_messages = filtered_messages

        try:
            agent = CodeExecutionAgent(llm, tool_sets)

            try:
                loop = asyncio.get_event_loop()
            except RuntimeError:
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)

            msg = loop.run_until_complete(agent.execute_workflow(last_messages))
            try:
                generated_code = msg.get("generated_code", "")
                task_goal = msg.get("task_goal", "Unknown Goal")

                if generated_code:
                    await log_event(
                        thread_id=DEFAULT_THREAD_ID,
                        actor="code_agent",
                        message=f"PLAN: {task_goal}\n\nEXECUTED CODE:\n```python\n{generated_code}\n```",
                        metadata={
                            "type": "code_execution",
                        },
                    )

                execution_summary = msg.get("summary", "No summary provided")
                execution_details = json.dumps(msg.get("details", {}), indent=2)

                await log_event(
                    thread_id=DEFAULT_THREAD_ID,
                    actor="code_agent",
                    message=f"EXECUTION RESULT:\nStatus: {msg.get('status')}\nSummary: {execution_summary}\nDetails: {execution_details}",
                    metadata={"type": "code_output", "status": msg.get("status")},
                )

            except Exception as log_error:
                logger.error(f"Failed to log code execution event: {log_error}")

        except Exception as e:
            logger.error(f"Code execution error: {e}")
            raw_content = f"Code execution failed: {str(e)}"
            agent_message = AIMessage(content=raw_content, name=current_agent_name)
            return {"messages": [agent_message]}

        # Format result
        raw_content = (
            f"Status: {msg.get('status', 'unknown')}\n"
            f"Summary: {msg.get('summary', 'No summary')}\n"
        )

        final_content = raw_content
        agent_message = AIMessage(
            content=final_content,
            name=current_agent_name,
            additional_kwargs={"timestamp": current_time},
        )

        return {"messages": [agent_message]}

    return code_executor


async def summerizer_node(state: State):
    logger.info("📝 Summarizer node activated to condense conversation history.")

    messages_to_summerize = state["messages"][:-15]
    # right now the prompt is not aware of we sending the summary and to summerize previous messages too
    prompt_content = f"Summary:\n{state.get('summary', '')}\n\n Chat Messages:\n{messages_to_summerize}"
    llm = build_llm()
    messages = [
        SystemMessage(content=HISTORY_SUMMARIZE_PROMPT),
        SystemMessage(content=prompt_content),
    ]
    cleaned = await llm.ainvoke(messages)

    summarized_content = cleaned.content

    delete_actions = []
    missing_ids_count = 0
    for m in messages_to_summerize:
        if m.id:
            delete_actions.append(RemoveMessage(id=m.id))
        else:
            missing_ids_count += 1

    if missing_ids_count > 0:
        logger.warning(
            f"⚠️ Found {missing_ids_count} messages without IDs that cannot be removed."
        )

    try:
        await log_event(
            thread_id=DEFAULT_THREAD_ID,
            actor="summerizer_node",
            message=f"summerized content: {summarized_content}",
            metadata={
                "archived_messages": len(delete_actions),
                "unremovable_messages": missing_ids_count,
            },
        )
    except Exception as e:
        logger.error(f"Failed to log summarizer audit event: {e}")

    return {"summary": summarized_content, "messages": delete_actions}


def memory_node_factory():
    async def memory_node(state: State):
        from core.agent import updation_knowledge_graph
        from core.agent import updation_episodic_rag

        from config.settings import DEFAULT_THREAD_ID, MEMORY_DB

        now_float = time.time()

        updates = {
            "summary": "",
            "number_of_summaries_today": 0,
            "last_summary_timestamp": now_float,
        }

        await updation_knowledge_graph(
            state=state, thread_id=DEFAULT_THREAD_ID, db_path=MEMORY_DB
        )

        await updation_episodic_rag(
            past_summary_date=state.get("last_memory_timestamp", 0.0), db_path=MEMORY_DB
        )

        updates["last_memory_timestamp"] = now_float
        return updates

    return memory_node


async def updation_episodic_rag(past_summary_date=None, db_path=MEMORY_DB):
    try:
        logger.info("🔄 Starting episodic RAG update process.")

        if past_summary_date is None or past_summary_date == 0.0:
            past_summary_date = None
            logger.info("No previous timestamp found, fetching all available logs")

        if past_summary_date is not None:
            if isinstance(past_summary_date, float):
                past_summary_date_iso = datetime.fromtimestamp(
                    past_summary_date
                ).isoformat()
            elif isinstance(past_summary_date, datetime):
                past_summary_date_iso = past_summary_date.isoformat()
            else:
                past_summary_date_iso = str(past_summary_date)

            logger.info(f"Fetching logs after: {past_summary_date_iso}")
        else:
            logger.info("Fetching ALL logs from database")

        rag = EpisodicRAG(db_path=db_path)
        chunks = await rag.custom_text_splitters(past_summary_date=past_summary_date)

        if not chunks:
            logger.info("No chunks generated - no new data to index.")
            return

        rag.index_creation(chunks)
        logger.info("✅ Episodic RAG update process completed successfully.")
    except Exception as e:
        logger.error(f"Episodic RAG update failed: {e}")


async def updation_knowledge_graph(
    state: State, thread_id: str, db_path: str = MEMORY_DB
):
    try:
        from rag.knowledge_graph import KnowledgeGraph

        logger.info("🔄 Starting knowledge graph update process.")
        last_update = state.get("last_knowledgegraph_timestamp", 0.0)

        if isinstance(last_update, float):
            last_update_str = datetime.fromtimestamp(last_update).isoformat()

        elif isinstance(last_update, datetime):
            last_update_str = last_update.isoformat()

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

        if not candidates_json.get("candidates", {}).get(
            "entities"
        ) and not candidates_json.get("candidates", {}).get("relationships"):
            logger.info(
                "🔍 No valid entities or relationships found. Exiting update process."
            )
            return
        entities = candidates_json.get("candidates", {}).get("entities", [])

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
                kg.add_entity(
                    node_id=entity["id"] and not None,
                    node_type=entity.get("type", "unknown") and not None,
                    search_keywords=", ".join(entity.get("keywords", [])) and not None,
                    description=entity.get("description", "") and not None,
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
        kg.visualize()

    except Exception as e:
        logger.error(f"Knowledge graph update failed: {e}")
