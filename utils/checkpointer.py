from langchain_core.messages import AIMessage, HumanMessage, ToolMessage
from langgraph.checkpoint.sqlite.aio import AsyncSqliteSaver


def strip_message_metadata(message):
    if isinstance(message, AIMessage):
        return AIMessage(
            content=message.content,
            tool_calls=message.tool_calls if hasattr(message, "tool_calls") else [],
            additional_kwargs=message.additional_kwargs
            if hasattr(message, "additional_kwargs")
            else {},
        )

    elif isinstance(message, HumanMessage):
        return HumanMessage(content=message.content)

    elif isinstance(message, ToolMessage):
        return ToolMessage(
            content=message.content,
            tool_call_id=message.tool_call_id,
            name=message.name if hasattr(message, "name") else None,
        )

    else:
        return message


def clean_messages(messages):
    return [strip_message_metadata(msg) for msg in messages]


class CleaningAsyncSqliteSaver(AsyncSqliteSaver):
    async def aput(self, config, checkpoint, metadata, new_versions):
        if (
            "channel_values" in checkpoint
            and "messages" in checkpoint["channel_values"]
        ):
            checkpoint["channel_values"]["messages"] = clean_messages(
                checkpoint["channel_values"]["messages"]
            )
        return await super().aput(config, checkpoint, metadata, new_versions)
