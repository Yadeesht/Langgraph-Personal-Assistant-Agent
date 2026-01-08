from core.llm import build_llm
from langchain_core.messages import HumanMessage, AIMessage, ToolMessage, SystemMessage
from config.prompts import HISTORY_SUMMARIZE_PROMPT


def summarize_context(messages):
    """Summarize the context from the message history"""

    llm = build_llm()

    messages = [SystemMessage(content=HISTORY_SUMMARIZE_PROMPT)] + messages

    cleaned = llm.invoke(messages)
    cleaned_history = cleaned.content

    return cleaned_history


def slim_messages(messages):
    slim = []

    for m in messages:
        if isinstance(m, HumanMessage):
            slim.append({"role": "user", "content": m.content})

        elif isinstance(m, AIMessage):
            additional_kwargs = m.additional_kwargs if m.additional_kwargs else {}
            agent_name = additional_kwargs.get("name", "unknown_agent")
            slim.append(
                {
                    "role": "assistant",
                    "content": m.content,
                    "agent_name": agent_name,
                    "tool_calls": m.tool_calls or [],
                }
            )

        elif isinstance(
            m, SystemMessage
        ):  # this is never stored in the context actually
            slim.append({"role": "system", "content": m.content})

        elif isinstance(m, ToolMessage):
            slim.append(
                {
                    "role": "tool",
                    "tool_call_id": m.tool_call_id,
                    "tool_name": m.name,
                    "content": m.content,
                    "status": m.status,
                }
            )

    return slim


def sanitize_history(messages):
    clean_history = []

    for msg in messages:
        # 1. Handle Human Messages
        if isinstance(msg, HumanMessage):
            clean_history.append({"role": "user", "content": msg.content})

        # 2. Handle AI Messages (Reasoning + Tool Calls)
        elif isinstance(msg, AIMessage):
            entry = {
                "role": "assistant",
                "content": msg.content or "",
                "agent_name": getattr(msg, "additional_kwargs", {}),
            }

            if msg.tool_calls:
                entry["tool_calls"] = []
                for tool in msg.tool_calls:
                    entry["tool_calls"].append(
                        {"name": tool["name"], "args": tool["args"], "id": tool["id"]}
                    )

            clean_history.append(entry)

        # 3. Handle Tool Results
        elif isinstance(msg, ToolMessage):
            clean_history.append(
                {
                    "role": "tool",
                    "tool_call_id": msg.tool_call_id,
                    "result": msg.content,
                }
            )

    return clean_history
