from core.llm import build_llm
from langchain_core.messages import HumanMessage, AIMessage, ToolMessage, SystemMessage


def summarize_tool_result(messages, prompt):
    """Summarize the context from the message history"""

    llm = build_llm()

    messages = [SystemMessage(content=prompt)] + [messages]

    cleaned = llm.invoke(messages)
    cleaned_history = cleaned.content

    return cleaned_history


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
                "agent_name": msg.additional_kwargs.get("agent_name", "default_agent"),
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
