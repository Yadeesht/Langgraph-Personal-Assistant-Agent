from core.llm import build_llm_with_tools
from langchain_core.messages import SystemMessage


def summarize_context(messages):
    """Summarize the context from the message history"""

    llm = build_llm_with_tools(tools=[])
    messages = [
        SystemMessage(content="Summarize the following conversation:")
    ] + messages
    cleaned = llm.invoke(messages)
    cleaned_history = cleaned.content

    return cleaned_history
