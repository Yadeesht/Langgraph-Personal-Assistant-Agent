from pathlib import Path
"""
Google Chat Tools

This module provides tools for interacting with Google Chat API.
"""

import asyncio
from typing import Optional

from googleapiclient.errors import HttpError

from app_tools.auth.service_decoder import get_google_service
from app_tools.core.server_init import communication_server
from app_tools.helper.pydantic_models import (
    ListSpacesRequest,
    ListSpacesResponse,
    SpaceInfo,
    GetMessagesRequest,
    GetMessagesResponse,
    MessageInfo,
    SendMessageRequest,
    SendMessageResponse,
    SearchMessagesRequest,
    SearchMessagesResponse,
    SearchMessageInfo,
)

from utils.helper import setup_logger

logger = setup_logger(__name__)


# auth
def get_service():
    """Get Gmail service using shared auth"""
    base_dir = Path(__file__).parent.parent.parent
    token_path = str(base_dir / "cred" / "gchat_token.json")
    creds_path = str(base_dir / "cred" / "setup_cred.json")

    return get_google_service(
        service_type="gchat",
        scope_key="gchat",
        token_path=token_path,
        creds_path=creds_path,
    )


@communication_server.tool()
async def list_spaces(
    page_size: int = 100,
    space_type: str = "all",  # "all", "room", "dm"
) -> dict:
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
        dict: A dictionary containing count, spaces list, and space_type_filter.
              Each space entry includes:
              - Display name of the space
              - Space ID (used for other operations like get_messages, send_message)
              - Space type (SPACE for rooms, DIRECT_MESSAGE for DMs)
    """
    try:
        request = ListSpacesRequest(page_size=page_size, space_type=space_type)
    except Exception as e:
        return ListSpacesResponse(
            count=0,
            spaces=[],
            space_type_filter=space_type,
            error=f"Invalid parameters: {str(e)}",
        ).model_dump()

    try:
        service = get_service()

        filter_param = None
        if request.space_type == "room":
            filter_param = "spaceType = SPACE"
        elif request.space_type == "dm":
            filter_param = "spaceType = DIRECT_MESSAGE"

        request_params = {"pageSize": request.page_size}
        if filter_param:
            request_params["filter"] = filter_param

        response = await asyncio.to_thread(
            service.spaces().list(**request_params).execute
        )

        spaces = response.get("spaces", [])
        if not spaces:
            return ListSpacesResponse(
                count=0, spaces=[], space_type_filter=request.space_type
            ).model_dump()

        space_list = [
            SpaceInfo(
                name=space.get("name", ""),
                display_name=space.get("displayName", "Unnamed Space"),
                space_type=space.get("spaceType", "UNKNOWN"),
            )
            for space in spaces
        ]

        logger.info(f"Listed {len(space_list)} spaces of type '{request.space_type}'")
        return ListSpacesResponse(
            count=len(space_list),
            spaces=space_list,
            space_type_filter=request.space_type,
        ).model_dump()

    except HttpError as error:
        logger.error(f"Failed to list spaces: {error}")
        return ListSpacesResponse(
            count=0,
            spaces=[],
            space_type_filter=space_type,
            error=str(error),
        ).model_dump()
    except Exception as error:
        logger.error(f"Unexpected error: {error}")
        return ListSpacesResponse(
            count=0,
            spaces=[],
            space_type_filter=space_type,
            error=str(error),
        ).model_dump()


@communication_server.tool()
async def get_messages(
    space_id: str,
    page_size: int = 50,
    order_by: str = "createTime desc",
) -> dict:
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
        dict: Dictionary containing count, space_name, space_id, and messages list.
              Each message includes:
              - Timestamp of each message
              - Sender's display name
              - Message text content
              - Message ID (for reference or threading)
    """
    try:
        request = GetMessagesRequest(
            space_id=space_id, page_size=page_size, order_by=order_by
        )
    except Exception as e:
        return GetMessagesResponse(
            count=0,
            space_name="",
            space_id=space_id,
            messages=[],
            error=f"Invalid parameters: {str(e)}",
        ).model_dump()

    try:
        service = get_service()

        space_info = await asyncio.to_thread(
            service.spaces().get(name=request.space_id).execute
        )
        space_name = space_info.get("displayName", "Unknown Space")

        # Get messages
        response = await asyncio.to_thread(
            service.spaces()
            .messages()
            .list(
                parent=request.space_id,
                pageSize=request.page_size,
                orderBy=request.order_by,
            )
            .execute
        )

        messages = response.get("messages", [])
        if not messages:
            return GetMessagesResponse(
                count=0, space_name=space_name, space_id=request.space_id, messages=[]
            ).model_dump()

        message_list = [
            MessageInfo(
                name=msg.get("name", ""),
                sender=msg.get("sender", {}).get("displayName", "Unknown Sender"),
                create_time=msg.get("createTime", "Unknown Time"),
                text=msg.get("text", "No text content"),
            )
            for msg in messages
        ]

        logger.info(f"Retrieved {len(message_list)} messages from space '{space_name}'")
        return GetMessagesResponse(
            count=len(message_list),
            space_name=space_name,
            space_id=request.space_id,
            messages=message_list,
        ).model_dump()

    except HttpError as error:
        logger.error(f"Failed to get messages from space {space_id}: {error}")
        return GetMessagesResponse(
            count=0, space_name="", space_id=space_id, messages=[], error=str(error)
        ).model_dump()
    except Exception as error:
        logger.error(f"Unexpected error: {error}")
        return GetMessagesResponse(
            count=0, space_name="", space_id=space_id, messages=[], error=str(error)
        ).model_dump()


@communication_server.tool()
async def send_message(
    space_id: str,
    message_text: str,
    thread_key: Optional[str] = None,
) -> dict:
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
        dict: Dictionary containing success status, message_id, space_id, and thread_id.
              Includes full message details if successful.
    """
    try:
        request = SendMessageRequest(
            space_id=space_id, message_text=message_text, thread_key=thread_key
        )
    except Exception as e:
        return SendMessageResponse(
            success=False, error=f"Invalid parameters: {str(e)}"
        ).model_dump()

    try:
        service = get_service()
        message_body = {"text": request.message_text}

        # Add thread key if provided (for threaded replies)
        request_params = {"parent": request.space_id, "body": message_body}
        if request.thread_key:
            request_params["threadKey"] = request.thread_key

        message = await asyncio.to_thread(
            service.spaces().messages().create(**request_params).execute
        )

        message_id = message.get("name", "")
        thread_id = message.get("thread", {}).get("name", "")

        logger.info(
            f"Successfully sent message to space '{request.space_id}': {request.message_text[:50]}..."
        )
        return SendMessageResponse(
            success=True,
            message_id=message_id,
            space_id=request.space_id,
            thread_id=thread_id if thread_id else None,
        ).model_dump()

    except HttpError as error:
        logger.error(f"Failed to send message to space {space_id}: {error}")
        return SendMessageResponse(success=False, error=str(error)).model_dump()
    except Exception as error:
        logger.error(f"Unexpected error: {error}")
        return SendMessageResponse(success=False, error=str(error)).model_dump()


@communication_server.tool()
async def search_messages(
    query: str,
    space_id: Optional[str] = None,
    page_size: int = 25,
) -> dict:
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
        dict: Dictionary containing count, query, context, and messages list.
              Each message includes:
              - Message timestamp
              - Sender's display name
              - Space name where message was found
              - Message text (truncated to 100 characters if longer)
    """
    try:
        request = SearchMessagesRequest(
            query=query, space_id=space_id, page_size=page_size
        )
    except Exception as e:
        return SearchMessagesResponse(
            count=0,
            query=query,
            context="",
            messages=[],
            error=f"Invalid parameters: {str(e)}",
        ).model_dump()

    try:
        service = get_service()

        if request.space_id:
            response = await asyncio.to_thread(
                service.spaces()
                .messages()
                .list(
                    parent=request.space_id,
                    pageSize=request.page_size,
                    filter=f'text:"{request.query}"',
                )
                .execute
            )
            messages = response.get("messages", [])
            context = f"space '{request.space_id}'"
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
                            parent=space.get("name"),
                            pageSize=5,
                            filter=f'text:"{request.query}"',
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
            return SearchMessagesResponse(
                count=0, query=request.query, context=context, messages=[]
            ).model_dump()

        message_list = []
        for msg in messages:
            sender = msg.get("sender", {}).get("displayName", "Unknown Sender")
            create_time = msg.get("createTime", "Unknown Time")
            text_content = msg.get("text", "No text content")
            space_name = msg.get("_space_name", "Unknown Space")

            # Truncate long messages
            if len(text_content) > 100:
                text_content = text_content[:100] + "..."

            message_list.append(
                SearchMessageInfo(
                    sender=sender,
                    create_time=create_time,
                    text=text_content,
                    space_name=space_name,
                )
            )

        logger.info(
            f"Found {len(message_list)} messages matching '{request.query}' in {context}"
        )
        return SearchMessagesResponse(
            count=len(message_list),
            query=request.query,
            context=context,
            messages=message_list,
        ).model_dump()

    except HttpError as error:
        logger.error(f"Failed to search messages for '{query}': {error}")
        return SearchMessagesResponse(
            count=0, query=query, context="", messages=[], error=str(error)
        ).model_dump()
    except Exception as error:
        logger.error(f"Unexpected error: {error}")
        return SearchMessagesResponse(
            count=0, query=query, context="", messages=[], error=str(error)
        ).model_dump()
