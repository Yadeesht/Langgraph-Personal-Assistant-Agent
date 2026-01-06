from langchain_core.messages import AIMessage, HumanMessage, ToolMessage, SystemMessage
from langgraph.checkpoint.sqlite.aio import AsyncSqliteSaver


def strip_message_metadata(message):
    """Strip unnecessary metadata while preserving essential fields"""
    if isinstance(message, AIMessage):
        return AIMessage(
            content=message.content,
            tool_calls=getattr(message, "tool_calls", []),
            additional_kwargs=getattr(message, "additional_kwargs", {}),
        )

    elif isinstance(message, HumanMessage):
        return HumanMessage(
            content=message.content,
            additional_kwargs=getattr(message, "additional_kwargs", {}),
        )

    elif isinstance(message, ToolMessage):
        return ToolMessage(
            content=message.content,
            tool_call_id=message.tool_call_id,
            additional_kwargs=getattr(message, "additional_kwargs", {}),
        )

    elif isinstance(message, SystemMessage):
        return SystemMessage(
            content=message.content,
            additional_kwargs=getattr(message, "additional_kwargs", {}),
        )

    else:
        return message


def clean_messages(messages):
    """Clean all messages in a list"""
    return [strip_message_metadata(msg) for msg in messages]


class CleaningAsyncSqliteSaver(AsyncSqliteSaver):
    async def aput(self, config, checkpoint, metadata, new_versions):
        """Save checkpoint with cleaned messages"""
        if (
            "channel_values" in checkpoint
            and "messages" in checkpoint["channel_values"]
        ):
            checkpoint["channel_values"]["messages"] = clean_messages(
                checkpoint["channel_values"]["messages"]
            )
        return await super().aput(config, checkpoint, metadata, new_versions)
