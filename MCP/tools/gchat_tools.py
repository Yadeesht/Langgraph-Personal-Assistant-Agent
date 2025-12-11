"""
Google Chat MCP Tools

This module provides MCP tools for interacting with Google Chat API.
"""

import logging
import asyncio
from typing import Optional
import sys
from pathlib import Path

from googleapiclient.errors import HttpError

from MCP.auth.service_decoder import get_google_service
from MCP.core.server_init import comm_server

root_dir = Path(__file__).parent.parent.parent
sys.path.insert(0, str(root_dir))


logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


# auth
def get_service():
    """Get Gmail service using shared auth"""
    base_dir = Path(__file__).parent.parent
    token_path = str(base_dir / "cred" / "gchat_token.json")
    creds_path = str(base_dir / "cred" / "setup_cred.json")

    return get_google_service(
        service_type="chat",
        scope_key="chat",
        token_path=token_path,
        creds_path=creds_path,
    )


@comm_server.tool()
async def list_spaces(
    page_size: int = 100,
    space_type: str = "all",  # "all", "room", "dm"
) -> str:
    """
    Lists Google Chat spaces (rooms and direct messages) accessible to the user.

    Args:
        page_size (int): Maximum number of spaces to retrieve. Defaults to 100. Use smaller values for faster responses.
        space_type (str): Type of spaces to list. Options:
            - "all": Returns all accessible spaces (rooms and DMs)
            - "room": Returns only group chat rooms/spaces
            - "dm": Returns only direct message conversations
            Defaults to "all".

    Returns:
        str: A formatted list of Google Chat spaces with their display names, IDs, and types.
             Each space entry includes:
             - Display name of the space
             - Space ID (used for other operations like get_messages, send_message)
             - Space type (SPACE for rooms, DIRECT_MESSAGE for DMs)
    """

    service = get_service()

    filter_param = None
    if space_type == "room":
        filter_param = "spaceType = SPACE"
    elif space_type == "dm":
        filter_param = "spaceType = DIRECT_MESSAGE"

    request_params = {"pageSize": page_size}
    if filter_param:
        request_params["filter"] = filter_param

    response = await asyncio.to_thread(service.spaces().list(**request_params).execute)

    spaces = response.get("spaces", [])
    if not spaces:
        return f"No Chat spaces found for type '{space_type}'."

    output = [f"Found {len(spaces)} Chat spaces (type: {space_type}):"]
    for space in spaces:
        space_name = space.get("displayName", "Unnamed Space")
        space_id = space.get("name", "")
        space_type_actual = space.get("spaceType", "UNKNOWN")
        output.append(f"- {space_name} (ID: {space_id}, Type: {space_type_actual})")

    return "\n".join(output)


@comm_server.tool()
async def get_messages(
    space_id: str,
    page_size: int = 50,
    order_by: str = "createTime desc",
) -> str:
    """
    Retrieves messages from a Google Chat space (room or direct message conversation).
    Use this to read chat history, view conversation threads, or monitor space activity.

    Args:
        space_id (str): The unique identifier of the Google Chat space. Required.
                       Format: "spaces/SPACE_ID" (obtain from list_spaces tool).
                       Example: "spaces/AAAAMpdlehY"
        page_size (int): Maximum number of messages to retrieve. Defaults to 50.
                        Use smaller values (10-25) for recent messages, larger for history.
        order_by (str): Sort order for messages. Defaults to "createTime desc" (newest first).
                       Options:
                       - "createTime desc": Newest messages first (recommended)
                       - "createTime asc": Oldest messages first

    Returns:
        str: Formatted list of messages from the space including:
             - Timestamp of each message
             - Sender's display name
             - Message text content
             - Message ID (for reference or threading)
             Returns "No messages found" if the space is empty or inaccessible.
    """
    service = get_service()

    space_info = await asyncio.to_thread(service.spaces().get(name=space_id).execute)
    space_name = space_info.get("displayName", "Unknown Space")

    # Get messages
    response = await asyncio.to_thread(
        service.spaces()
        .messages()
        .list(parent=space_id, pageSize=page_size, orderBy=order_by)
        .execute
    )

    messages = response.get("messages", [])
    if not messages:
        return f"No messages found in space '{space_name}' (ID: {space_id})."

    output = [f"Messages from '{space_name}' (ID: {space_id}):\n"]
    for msg in messages:
        sender = msg.get("sender", {}).get("displayName", "Unknown Sender")
        create_time = msg.get("createTime", "Unknown Time")
        text_content = msg.get("text", "No text content")
        msg_name = msg.get("name", "")

        output.append(f"[{create_time}] {sender}:")
        output.append(f"  {text_content}")
        output.append(f"  (Message ID: {msg_name})\n")

    return "\n".join(output)


@comm_server.tool()
async def send_message(
    space_id: str,
    message_text: str,
    thread_key: Optional[str] = None,
) -> str:
    """
    Sends a message to a Google Chat space (room or direct message conversation).
    Use this to post messages, respond to conversations, or start new threads.

    Args:
        space_id (str): The unique identifier of the target Google Chat space. Required.
                       Format: "spaces/SPACE_ID" (obtain from list_spaces tool).
                       Example: "spaces/AAAAMpdlehY"
        message_text (str): The text content of the message to send. Required.
                           Supports plain text. For formatting, use simple markdown.
                           Maximum length: 4096 characters.
        thread_key (Optional[str]): Optional thread identifier for creating or replying to a specific thread.
                                    If provided, the message will be posted as a reply in that thread.
                                    If None (default), creates a new standalone message or thread.
                                    Use this to maintain conversation context in busy spaces.

    Returns:
        str: JSON object containing the sent message details including:
             - Message ID
             - Sender information
             - Timestamp
             - Thread information (if applicable)
             Logs success confirmation to application logs.
    """
    service = get_service()
    message_body = {"text": message_text}

    # Add thread key if provided (for threaded replies)
    request_params = {"parent": space_id, "body": message_body}
    if thread_key:
        request_params["threadKey"] = thread_key

    message = await asyncio.to_thread(
        service.spaces().messages().create(**request_params).execute
    )

    logger.info(f"Successfully sent message to space '{space_id}': {message_text}")
    return message


@comm_server.tool()
async def search_messages(
    query: str,
    space_id: Optional[str] = None,
    page_size: int = 25,
) -> str:
    """
    Searches for messages in Google Chat spaces by text content.
    Use this to find specific messages, locate information across conversations, or audit chat history.

    Args:
        query (str): The search term or phrase to look for in message text. Required.
                    Searches are case-insensitive and match partial text.
                    Example: "meeting notes", "project update", "deadline"
        space_id (Optional[str]): The unique identifier of a specific space to search within.
                                 Format: "spaces/SPACE_ID" (obtain from list_spaces tool).
                                 If None (default), searches across all accessible spaces (up to first 10).
                                 Provide space_id for faster, focused searches.
        page_size (int): Maximum number of matching messages to return. Defaults to 25.
                        When searching across all spaces, this limit applies per space.
                        Use smaller values (5-10) for quick overview, larger for comprehensive search.

    Returns:
        str: A formatted list of messages matching the search query including:
             - Message timestamp
             - Sender's display name
             - Space name where message was found
             - Message text (truncated to 100 characters if longer)
             Returns "No messages found" if query yields no results.
             Note: May skip spaces that are inaccessible due to permissions.
    """
    service = get_service()

    if space_id:
        response = await asyncio.to_thread(
            service.spaces()
            .messages()
            .list(parent=space_id, pageSize=page_size, filter=f'text:"{query}"')
            .execute
        )
        messages = response.get("messages", [])
        context = f"space '{space_id}'"
    else:
        # Search across all accessible spaces (this may require iterating through spaces)
        # For simplicity, we'll search the user's spaces first
        spaces_response = await asyncio.to_thread(
            service.spaces().list(pageSize=100).execute
        )
        spaces = spaces_response.get("spaces", [])

        messages = []
        for space in spaces[:10]:  # Limit to first 10 spaces to avoid timeout
            try:
                space_messages = await asyncio.to_thread(
                    service.spaces()
                    .messages()
                    .list(
                        parent=space.get("name"), pageSize=5, filter=f'text:"{query}"'
                    )
                    .execute
                )
                space_msgs = space_messages.get("messages", [])
                for msg in space_msgs:
                    msg["_space_name"] = space.get("displayName", "Unknown")
                messages.extend(space_msgs)
            except HttpError:
                continue  # Skip spaces we can't access
        context = "all accessible spaces"

    if not messages:
        return f"No messages found matching '{query}' in {context}."

    output = [f"Found {len(messages)} messages matching '{query}' in {context}:"]
    for msg in messages:
        sender = msg.get("sender", {}).get("displayName", "Unknown Sender")
        create_time = msg.get("createTime", "Unknown Time")
        text_content = msg.get("text", "No text content")
        space_name = msg.get("_space_name", "Unknown Space")

        # Truncate long messages
        if len(text_content) > 100:
            text_content = text_content[:100] + "..."

        output.append(f"- [{create_time}] {sender} in '{space_name}': {text_content}")

    return "\n".join(output)
