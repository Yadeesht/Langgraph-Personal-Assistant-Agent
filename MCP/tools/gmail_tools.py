"""Refactored Gmail API Tools - Best Practices Version"""

import asyncio
import base64
import logging
import webbrowser
from datetime import datetime, timedelta
from email import message_from_bytes
from email.header import decode_header
from email.message import EmailMessage
from pathlib import Path
from typing import Any, Optional

from googleapiclient.errors import HttpError

from MCP.auth.service_decoder import get_google_service
from MCP.core.server_init import communication_server

logger = logging.getLogger(__name__)


def get_service():
    """Get Gmail service using shared authentication."""
    base_dir = Path(__file__).parent.parent
    token_path = str(base_dir / "cred" / "gmail_token.json")
    creds_path = str(base_dir / "cred" / "setup_cred.json")

    return get_google_service(
        service_type="gmail",
        scope_key="gmail",
        token_path=token_path,
        creds_path=creds_path,
    )


def decode_mime_header(header: str) -> str:
    """Decode MIME-encoded email headers."""
    decoded_parts = decode_header(header)
    decoded_string = ""
    for part, encoding in decoded_parts:
        if isinstance(part, bytes):
            decoded_string += part.decode(encoding or "utf-8")
        else:
            decoded_string += part
    return decoded_string


async def get_user_email(service) -> str:
    """Get the authenticated user's email address."""
    profile = await asyncio.to_thread(service.users().getProfile(userId="me").execute)
    return profile.get("emailAddress", "")


def _generate_gmail_web_url(item_id: str, account_index: int = 0) -> str:
    """
    Generate Gmail web interface URL for a message or thread ID.
    Uses #all to access messages from any Gmail folder/label (not just inbox).

    Args:
        item_id: Gmail message ID or thread ID
        account_index: Google account index (default 0 for primary account)

    Returns:
        Gmail web interface URL that opens the message/thread in Gmail web interface
    """
    return f"https://mail.google.com/mail/u/{account_index}/#all/{item_id}"


def _format_gmail_results_plain(
    messages: list, query: str, next_page_token: Optional[str] = None
) -> str:
    """Format Gmail search results in clean, LLM-friendly plain text."""
    if not messages:
        return f"No messages found for query: '{query}'"

    lines = [
        f"Found {len(messages)} messages matching '{query}':",
        "",
        "📧 MESSAGES:",
    ]

    for i, msg in enumerate(messages, 1):
        # Handle potential null/undefined message objects
        if not msg or not isinstance(msg, dict):
            lines.extend(
                [
                    f"  {i}. Message: Invalid message data",
                    "     Error: Message object is null or malformed",
                    "",
                ]
            )
            continue

        # Handle potential null/undefined values from Gmail API
        message_id = msg.get("id")
        thread_id = msg.get("threadId")

        # Convert None, empty string, or missing values to "unknown"
        if not message_id:
            message_id = "unknown"
        if not thread_id:
            thread_id = "unknown"

        if message_id != "unknown":
            message_url = _generate_gmail_web_url(message_id)
        else:
            message_url = "N/A"

        if thread_id != "unknown":
            thread_url = _generate_gmail_web_url(thread_id)
        else:
            thread_url = "N/A"

        lines.extend(
            [
                f"  {i}. Message ID: {message_id}",
                f"     Web Link: {message_url}",
                f"     Thread ID: {thread_id}",
                f"     Thread Link: {thread_url}",
                "",
            ]
        )

    lines.extend(
        [
            "💡 USAGE:",
            "  • Pass the Message IDs **as a list** to get_gmail_messages_content_batch()",
            "    e.g. get_gmail_messages_content_batch(message_ids=[...])",
            "  • Pass the Thread IDs to get_gmail_thread_content() (single) or get_gmail_threads_content_batch() (batch)",
        ]
    )

    # Add pagination info if there's a next page
    if next_page_token:
        lines.append("")
        lines.append(
            f"📄 PAGINATION: To get the next page, call search_gmail_messages again with page_token='{next_page_token}'"
        )

    return "\n".join(lines)


@communication_server.tool()
async def search_gmail_messages(
    query: str,
    user_google_email: str,
    page_size: int = 10,
    page_token: Optional[str] = None,
) -> str:
    """
    Searches messages in a user's Gmail account based on a query.
    Returns both Message IDs and Thread IDs for each found message, along with Gmail web interface links for manual verification.
    Supports pagination via page_token parameter.

    Args:
        query (str): The search query. Supports standard Gmail search operators.
        page_size (int): The maximum number of messages to return. Defaults to 10.
        page_token (Optional[str]): Token for retrieving the next page of results. Use the next_page_token from a previous response.

    Returns:
        str: LLM-friendly structured results with Message IDs, Thread IDs, and clickable Gmail web interface URLs for each found message.
        Includes pagination token if more results are available.
    """

    service = get_service()

    request_params = {"userId": "me", "q": query, "maxResults": page_size}

    try:
        if page_token:
            request_params["pageToken"] = page_token
            logger.info("[search_gmail_messages] Using page_token for pagination")

        response = await asyncio.to_thread(
            service.users().messages().list(**request_params).execute
        )

        if response is None:
            logger.warning("[search_gmail_messages] Null response from Gmail API")
            return f"No response received from Gmail API for query: '{query}'"

        messages = response.get("messages", [])
        if messages is None:
            messages = []

        next_page_token = response.get("nextPageToken")

        formatted_output = _format_gmail_results_plain(messages, query, next_page_token)

        logger.info(f"[search_gmail_messages] Found {len(messages)} messages")
        if next_page_token:
            logger.info(
                "[search_gmail_messages] More results available (next_page_token present)"
            )
        return {"success": True, "output": formatted_output}
    except HttpError as error:
        logger.error(f"Gmail API error: {error}")
        return {"success": False, "error": str(error)}
    except Exception as error:
        logger.error(f"Unexpected error: {error}")
        return {"success": False, "error": str(error)}


@communication_server.tool()
async def send_email_tool(
    recipient_id: str, subject: str, message: str
) -> dict[str, Any]:
    """Send an email via Gmail.


    Args:
        recipient_id: Recipient's email address
        subject: Email subject line
        message: Email body content (plain text or HTML)

    Returns:
        Dict with 'success' boolean, 'message_id' if successful
    """
    try:
        service = get_service()
        user_email = await get_user_email(service)

        message_obj = EmailMessage()
        message_obj.set_content(message)
        message_obj["To"] = recipient_id
        message_obj["From"] = user_email
        message_obj["Subject"] = subject

        encoded_message = base64.urlsafe_b64encode(message_obj.as_bytes()).decode()
        create_message = {"raw": encoded_message}

        send_message = await asyncio.to_thread(
            service.users().messages().send(userId="me", body=create_message).execute
        )

        logger.info(f"Email sent successfully: {send_message['id']}")
        return {"success": True, "message_id": send_message["id"]}
    except HttpError as error:
        logger.error(f"Gmail API error: {error}")
        return {"success": False, "error": str(error)}
    except Exception as error:
        logger.error(f"Unexpected error: {error}")
        return {"success": False, "error": str(error)}


@communication_server.tool()
async def open_email_tool(email_id: str) -> dict[str, Any]:
    """Open a specific email in Gmail web interface.

    Args:
        email_id: The unique Gmail message ID

    Returns:
        Dict with 'success' boolean or 'error' message
    """
    try:
        url = f"https://mail.google.com/#all/{email_id}"
        webbrowser.open(url, new=0, autoraise=True)
        return {"success": True}
    except Exception as error:
        logger.error(f"Open email error: {error}")
        return {"success": False, "error": str(error)}


@communication_server.tool()
async def get_unread_emails_tool(
    date: int = 10, max_results: int = 20
) -> dict[str, Any]:
    """Fetch recent unread emails from the primary inbox.

    Args:
        date: Look back this many days (default: 10)
        max_results: Maximum emails to return (default: 20)

    Returns:
        Dict with 'count' and 'emails' list containing email metadata

    Note:
        Only searches the primary inbox category to avoid clutter.
    """
    try:
        service = get_service()
        after_date = (datetime.now() - timedelta(days=date)).strftime("%Y/%m/%d")
        query = f"in:inbox is:unread category:primary after:{after_date}"

        response = await asyncio.to_thread(
            service.users()
            .messages()
            .list(userId="me", q=query, maxResults=max_results)
            .execute
        )

        messages = []
        if "messages" in response:
            for msg in response["messages"]:
                email_id = msg["id"]

                full_msg = await asyncio.to_thread(
                    service.users()
                    .messages()
                    .get(
                        userId="me",
                        id=email_id,
                        format="metadata",
                        metadataHeaders=["Subject", "From", "Date", "To"],
                    )
                    .execute
                )

                headers = full_msg.get("payload", {}).get("headers", [])

                email_details = {
                    "id": email_id,
                    "thread_id": msg["threadId"],
                    "snippet": full_msg.get("snippet", ""),
                    "labels": full_msg.get("labelIds", []),
                    "size": full_msg.get("sizeEstimate", 0),
                    "internal_date": full_msg.get("internalDate"),
                    "subject": next(
                        (h["value"] for h in headers if h["name"] == "Subject"),
                        "No Subject",
                    ),
                    "from": next(
                        (h["value"] for h in headers if h["name"] == "From"),
                        "Unknown",
                    ),
                    "date": next(
                        (h["value"] for h in headers if h["name"] == "Date"), ""
                    ),
                    "to": next((h["value"] for h in headers if h["name"] == "To"), ""),
                }
                messages.append(email_details)

        return {"count": len(messages), "emails": messages}
    except HttpError as error:
        logger.error(f"Failed to fetch unread emails: {error}")
        return {"error": str(error)}
    except Exception as error:
        logger.error(f"Unexpected error: {error}")
        return {"error": str(error)}


@communication_server.tool()
async def read_email_tool(email_id: str) -> dict[str, Any]:
    """Read the full content of a specific email and mark it as read.

    Args:
        email_id: The unique Gmail message ID

    Returns:
        Dict with email content, subject, from, to, date fields

    Note:
        Automatically marks the email as read after fetching.
    """
    try:
        service = get_service()
        msg = await asyncio.to_thread(
            service.users()
            .messages()
            .get(userId="me", id=email_id, format="raw")
            .execute
        )

        # Decode the base64URL encoded raw content
        raw_data = msg["raw"]
        decoded_data = base64.urlsafe_b64decode(raw_data)

        # Parse the RFC 2822 email
        mime_message = message_from_bytes(decoded_data)

        # Extract the email body
        body = None
        if mime_message.is_multipart():
            for part in mime_message.walk():
                if part.get_content_type() == "text/plain":
                    body = part.get_payload(decode=True).decode()
                    break
        else:
            body = mime_message.get_payload(decode=True).decode()

        email_metadata = {
            "content": body,
            "subject": decode_mime_header(mime_message.get("subject", "")),
            "from": mime_message.get("from", ""),
            "to": mime_message.get("to", ""),
            "date": mime_message.get("date", ""),
        }

        logger.info(f"Email read: {email_id}")

        # Mark as read
        await asyncio.to_thread(
            service.users()
            .messages()
            .modify(userId="me", id=email_id, body={"removeLabelIds": ["UNREAD"]})
            .execute
        )

        return email_metadata
    except HttpError as error:
        logger.error(f"Failed to read email {email_id}: {error}")
        return {"error": str(error)}
    except Exception as error:
        logger.error(f"Unexpected error: {error}")
        return {"error": str(error)}


@communication_server.tool()
async def trash_email_tool(email_id: str) -> dict[str, Any]:
    """Move an email to trash.

    Args:
        email_id: The unique Gmail message ID

    Returns:
        Dict with 'success' boolean or 'error' message

    Warning:
        Always confirm with user before trashing emails.
    """
    try:
        service = get_service()
        await asyncio.to_thread(
            service.users().messages().trash(userId="me", id=email_id).execute
        )
        logger.info(f"Email trashed: {email_id}")
        return {"success": True}
    except HttpError as error:
        logger.error(f"Failed to trash email: {error}")
        return {"success": False, "error": str(error)}
    except Exception as error:
        logger.error(f"Unexpected error: {error}")
        return {"success": False, "error": str(error)}


@communication_server.tool()
async def mark_email_as_read_tool(email_id: str) -> dict[str, Any]:
    """Mark a specific email as read to remove the unread status.

    Args:
        email_id: The unique Gmail message ID to mark as read

    Returns:
        Dict with 'success' boolean or 'error' message
    """
    try:
        service = get_service()
        await asyncio.to_thread(
            service.users()
            .messages()
            .modify(userId="me", id=email_id, body={"removeLabelIds": ["UNREAD"]})
            .execute
        )
        logger.info(f"Email marked as read: {email_id}")
        return {"success": True}
    except HttpError as error:
        logger.error(f"Failed to mark as read: {error}")
        return {"success": False, "error": str(error)}
    except Exception as error:
        logger.error(f"Unexpected error: {error}")
        return {"success": False, "error": str(error)}


@communication_server.tool()
async def create_draft_tool(
    recipient_id: str, subject: str, message: str
) -> dict[str, Any]:
    """Create a draft email without sending it.

    Args:
        recipient_id: Recipient's email address (e.g., user@example.com)
        subject: Email subject line
        message: Email body content (plain text or HTML)

    Returns:
        Dict with 'success' boolean, 'draft_id' if successful

    Note:
        Use this when user wants to draft an email for later review.
    """
    try:
        service = get_service()
        user_email = await get_user_email(service)

        message_obj = EmailMessage()
        message_obj.set_content(message)
        message_obj["To"] = recipient_id
        message_obj["From"] = user_email
        message_obj["Subject"] = subject

        encoded_message = base64.urlsafe_b64encode(message_obj.as_bytes()).decode()
        create_message = {"raw": encoded_message}

        draft = await asyncio.to_thread(
            service.users()
            .drafts()
            .create(userId="me", body={"message": create_message})
            .execute
        )

        logger.info(f"Draft created: {draft['id']}")
        return {"success": True, "draft_id": draft["id"]}
    except HttpError as error:
        logger.error(f"Failed to create draft: {error}")
        return {"success": False, "error": str(error)}
    except Exception as error:
        logger.error(f"Unexpected error: {error}")
        return {"success": False, "error": str(error)}


@communication_server.tool()
async def list_drafts_tool() -> dict[str, Any]:
    """List all draft emails in the user's mailbox.

    Returns:
        Dict with 'count' and 'drafts' list containing draft metadata
    """
    try:
        service = get_service()
        results = await asyncio.to_thread(
            service.users().drafts().list(userId="me").execute
        )
        drafts = results.get("drafts", [])

        draft_list = []
        for draft in drafts:
            draft_id = draft["id"]
            draft_data = await asyncio.to_thread(
                service.users().drafts().get(userId="me", id=draft_id).execute
            )

            message = draft_data.get("message", {})
            headers = message.get("payload", {}).get("headers", [])

            subject = next(
                (h["value"] for h in headers if h["name"].lower() == "subject"),
                "No Subject",
            )
            to = next(
                (h["value"] for h in headers if h["name"].lower() == "to"),
                "No Recipient",
            )

            draft_list.append({"id": draft_id, "subject": subject, "to": to})

        return {"count": len(draft_list), "drafts": draft_list}
    except HttpError as error:
        logger.error(f"Failed to list drafts: {error}")
        return {"error": str(error)}
    except Exception as error:
        logger.error(f"Unexpected error: {error}")
        return {"error": str(error)}


@communication_server.tool()
async def list_labels_tool() -> dict[str, Any]:
    """List all labels (tags/folders) in the user's Gmail mailbox.

    Returns:
        Dict with 'count' and 'labels' list containing id, name, and type

    Note:
        Includes both system labels (INBOX, SENT) and user-created labels.
    """
    try:
        service = get_service()
        results = await asyncio.to_thread(
            service.users().labels().list(userId="me").execute
        )
        labels = results.get("labels", [])

        label_list = [
            {
                "id": label["id"],
                "name": label["name"],
                "type": label.get("type", "user"),
            }
            for label in labels
        ]

        return {"count": len(label_list), "labels": label_list}
    except HttpError as error:
        logger.error(f"Failed to list labels: {error}")
        return {"error": str(error)}
    except Exception as error:
        logger.error(f"Unexpected error: {error}")
        return {"error": str(error)}


@communication_server.tool()
async def create_label_tool(name: str) -> dict[str, Any]:
    """Create a new label (tag/folder) in Gmail for organizing emails.

    Args:
        name: The name of the new label to create

    Returns:
        Dict with 'success' boolean, 'label_id' and 'name' if successful
    """
    try:
        service = get_service()
        label_object = {
            "name": name,
            "labelListVisibility": "labelShow",
            "messageListVisibility": "show",
        }

        created_label = await asyncio.to_thread(
            service.users().labels().create(userId="me", body=label_object).execute
        )

        logger.info(f"Label created: {created_label['id']}")
        return {
            "success": True,
            "label_id": created_label["id"],
            "name": created_label["name"],
        }
    except HttpError as error:
        logger.error(f"Failed to create label: {error}")
        return {"success": False, "error": str(error)}
    except Exception as error:
        logger.error(f"Unexpected error: {error}")
        return {"success": False, "error": str(error)}


@communication_server.tool()
async def apply_label_tool(email_id: str, label_id: str) -> dict[str, Any]:
    """Apply a label (tag) to a specific email for organization.

    Args:
        email_id: The unique Gmail message ID
        label_id: The label ID to apply (from list_labels_tool)

    Returns:
        Dict with 'success' boolean or 'error' message
    """
    try:
        service = get_service()
        await asyncio.to_thread(
            service.users()
            .messages()
            .modify(userId="me", id=email_id, body={"addLabelIds": [label_id]})
            .execute
        )

        logger.info(f"Label {label_id} applied to email {email_id}")
        return {"success": True}
    except HttpError as error:
        logger.error(f"Failed to apply label: {error}")
        return {"success": False, "error": str(error)}
    except Exception as error:
        logger.error(f"Unexpected error: {error}")
        return {"success": False, "error": str(error)}


@communication_server.tool()
async def remove_labels_tool(email_id: str, label_id: str) -> dict[str, Any]:
    """Remove a label (tag) from a specific email.

    Args:
        email_id: The unique Gmail message ID
        label_id: The label ID to remove (from list_labels_tool)

    Returns:
        Dict with 'success' boolean or 'error' message
    """
    try:
        service = get_service()
        await asyncio.to_thread(
            service.users()
            .messages()
            .modify(userId="me", id=email_id, body={"removeLabelIds": [label_id]})
            .execute
        )

        logger.info(f"Label {label_id} removed from email {email_id}")
        return {"success": True}
    except HttpError as error:
        logger.error(f"Failed to remove label: {error}")
        return {"success": False, "error": str(error)}
    except Exception as error:
        logger.error(f"Unexpected error: {error}")
        return {"success": False, "error": str(error)}


@communication_server.tool()
async def search_by_label_tool(label_id: str) -> dict[str, Any]:
    """Search for all emails that have a specific label applied.

    Args:
        label_id: The label ID to search for (from list_labels_tool)

    Returns:
        List of message IDs with the label
    """
    try:
        service = get_service()
        query = f"label:{label_id}"

        response = await asyncio.to_thread(
            service.users().messages().list(userId="me", q=query).execute
        )

        messages = []
        if "messages" in response:
            messages.extend(response["messages"])

        while "nextPageToken" in response:
            page_token = response["nextPageToken"]
            response = await asyncio.to_thread(
                service.users()
                .messages()
                .list(userId="me", q=query, pageToken=page_token)
                .execute
            )
            messages.extend(response["messages"])

        return {"count": len(messages), "messages": messages}
    except HttpError as error:
        logger.error(f"Search by label failed: {error}")
        return {"error": str(error)}
    except Exception as error:
        logger.error(f"Unexpected error: {error}")
        return {"error": str(error)}


"""This tool is not working with the Gmail API but there is a way using the google.auth"""
# @communication_server.tool()
# async def create_filter_tool(**kwargs):
#     """
#     name="create-filter"
#     description="Creates a new email filter"
#     schema={
#         "type": "object",
#         "properties": {
#             "from_email": {"type": "string", "description": "Filter emails from this sender"},
#             "to_email": {"type": "string", "description": "Filter emails to this recipient"},
#             "subject": {"type": "string", "description": "Filter emails with this subject"},
#             "query": {"type": "string", "description": "Filter emails matching this query"},
#             "has_attachment": {"type": "boolean", "description": "Filter emails with attachments"},
#             "exclude_chats": {"type": "boolean", "description": "Exclude chats from filter"},
#             "size_comparison": {"type": "string", "description": "Size comparison ('larger' or 'smaller')"},
#             "size": {"type": "integer", "description": "Size in bytes for comparison"},
#             "add_label_ids": {"type": "array", "items": {"type": "string"}, "description": "Labels to add to matching emails"},
#             "remove_label_ids": {"type": "array", "items": {"type": "string"}, "description": "Labels to remove from matching emails"},
#             "forward_to": {"type": "string", "description": "Email address to forward matching emails to"},
#         },
#     }
#     """
#     gmail_service = GmailService(
#         creds_file_path="D:\\Agentic AI\\cred\\client_secret_979296281541-k7n60e6i7kcq1hijr30umufmis1auhgl.apps.googleusercontent.com.json",
#         token_path="D:\\Agentic AI\\cred\\token.json",
#     )
#     create_filter_response = await gmail_service.create_filter(**kwargs)
#     return create_filter_response


@communication_server.tool()
async def list_filters_tool() -> dict[str, Any]:
    """List all email filters configured in Gmail.

    Returns:
        Dict with 'filters' list or 'error' message

    Note:
        Filters are rules that automatically organize incoming emails.
    """
    try:
        service = get_service()
        results = await asyncio.to_thread(
            service.users().settings().filters().list(userId="me").execute
        )
        filters = results.get("filters", [])
        return {"count": len(filters), "filters": filters}
    except HttpError as error:
        logger.error(f"Failed to list filters: {error}")
        return {"error": str(error)}
    except Exception as error:
        logger.error(f"Unexpected error: {error}")
        return {"error": str(error)}


@communication_server.tool()
async def get_filter_tool(filter_id: str) -> dict[str, Any]:
    """Get detailed information about a specific email filter by its ID.

    Args:
        filter_id: The filter ID to retrieve (from list_filters_tool)

    Returns:
        Filter configuration details or error message
    """
    try:
        service = get_service()
        filter_data = await asyncio.to_thread(
            service.users().settings().filters().get(userId="me", id=filter_id).execute
        )
        return filter_data
    except HttpError as error:
        logger.error(f"Failed to get filter: {error}")
        return {"error": str(error)}
    except Exception as error:
        logger.error(f"Unexpected error: {error}")
        return {"error": str(error)}


@communication_server.tool()
async def delete_filter_tool(filter_id: str) -> dict[str, Any]:
    """Delete a specific email filter by its ID.

    Args:
        filter_id: The filter ID to delete (from list_filters_tool)

    Returns:
        Dict with 'success' boolean or 'error' message
    """
    try:
        service = get_service()
        await asyncio.to_thread(
            service.users()
            .settings()
            .filters()
            .delete(userId="me", id=filter_id)
            .execute
        )
        logger.info(f"Filter deleted: {filter_id}")
        return {"success": True}
    except HttpError as error:
        logger.error(f"Failed to delete filter: {error}")
        return {"success": False, "error": str(error)}
    except Exception as error:
        logger.error(f"Unexpected error: {error}")
        return {"success": False, "error": str(error)}


@communication_server.tool()
async def search_emails_tool(
    query: str, max_results: int | None = None
) -> dict[str, Any]:
    """Search emails using Gmail's query syntax.

    Args:
        query: Gmail search query (supports from:, subject:, after:, has:attachment, etc.)
        max_results: Maximum number of results to return (optional)

    Returns:
        Dict with 'count' and 'emails' list

    Examples:
        - "from:boss@company.com subject:urgent"
        - "has:attachment after:2024/01/01"
        - "is:unread from:newsletter@site.com"

    See: https://support.google.com/mail/answer/7190
    """
    try:
        service = get_service()
        response = await asyncio.to_thread(
            service.users()
            .messages()
            .list(userId="me", q=query, maxResults=max_results)
            .execute
        )

        messages = []
        if "messages" in response:
            messages.extend(response["messages"])

        # Get metadata for each message
        result_messages = []
        for msg in messages:
            msg_data = await asyncio.to_thread(
                service.users()
                .messages()
                .get(
                    userId="me",
                    id=msg["id"],
                    format="metadata",
                    metadataHeaders=["Subject", "From", "Date"],
                )
                .execute
            )

            headers = msg_data.get("payload", {}).get("headers", [])

            subject = next(
                (h["value"] for h in headers if h["name"].lower() == "subject"),
                "No Subject",
            )
            sender = next(
                (h["value"] for h in headers if h["name"].lower() == "from"),
                "Unknown Sender",
            )
            date = next(
                (h["value"] for h in headers if h["name"].lower() == "date"),
                "",
            )

            result_messages.append(
                {
                    "id": msg["id"],
                    "thread_id": msg["threadId"],
                    "subject": subject,
                    "from": sender,
                    "date": date,
                    "snippet": msg_data.get("snippet", ""),
                }
            )

        return {"count": len(result_messages), "emails": result_messages}
    except HttpError as error:
        logger.error(f"Search failed for query '{query}': {error}")
        return {"error": str(error)}
    except Exception as error:
        logger.error(f"Unexpected error: {error}")
        return {"error": str(error)}


@communication_server.tool()
async def create_folder_tool(name: str) -> dict[str, Any]:
    """Create a new folder in Gmail.

    Args:
        name: The name of the new folder to create

    Returns:
        Dict with 'success' boolean, 'folder_id' and 'name' if successful

    Note:
        In Gmail, folders are implemented as labels with special handling.
    """
    try:
        service = get_service()
        label_object = {
            "name": name,
            "labelListVisibility": "labelShow",
            "messageListVisibility": "show",
            "type": "user",
        }

        created_label = await asyncio.to_thread(
            service.users().labels().create(userId="me", body=label_object).execute
        )

        logger.info(f"Folder created: {created_label['id']}")
        return {
            "success": True,
            "folder_id": created_label["id"],
            "name": created_label["name"],
        }
    except HttpError as error:
        logger.error(f"Failed to create folder: {error}")
        return {"success": False, "error": str(error)}
    except Exception as error:
        logger.error(f"Unexpected error: {error}")
        return {"success": False, "error": str(error)}
    except Exception as error:
        logger.error(f"Create folder error: {str(error)}")
        return {"status": "error", "error_message": str(error)}


@communication_server.tool()
async def move_to_folder_tool(email_id: str, folder_id: str) -> dict[str, Any]:
    """Move an email to a specific folder.

    Args:
        email_id: The unique Gmail message ID
        folder_id: The folder ID (label ID) to move the email to

    Returns:
        Dict with 'success' boolean or 'error' message

    Note:
        This applies folder label and removes from inbox.
    """
    try:
        service = get_service()
        await asyncio.to_thread(
            service.users()
            .messages()
            .modify(
                userId="me",
                id=email_id,
                body={"addLabelIds": [folder_id], "removeLabelIds": ["INBOX"]},
            )
            .execute
        )

        logger.info(f"Email {email_id} moved to folder {folder_id}")
        return {"success": True}
    except HttpError as error:
        logger.error(f"Failed to move to folder: {error}")
        return {"success": False, "error": str(error)}
    except Exception as error:
        logger.error(f"Unexpected error: {error}")
        return {"success": False, "error": str(error)}


@communication_server.tool()
async def list_folders_tool() -> dict[str, Any]:
    """List all user-created folders in Gmail.

    Returns:
        Dict with 'count' and 'folders' list containing user-created labels
    """
    try:
        service = get_service()
        results = await asyncio.to_thread(
            service.users().labels().list(userId="me").execute
        )
        labels = results.get("labels", [])

        # Filter to only include user-created labels
        folders = [
            {"id": label["id"], "name": label["name"]}
            for label in labels
            if label.get("type") == "user"
        ]

        return {"count": len(folders), "folders": folders}
    except HttpError as error:
        logger.error(f"Failed to list folders: {error}")
        return {"error": str(error)}
    except Exception as error:
        logger.error(f"Unexpected error: {error}")
        return {"error": str(error)}


@communication_server.tool()
async def rename_labels_tool(label_id: str, new_name: str) -> dict[str, Any]:
    """Rename an existing label to a new name.

    Args:
        label_id: The label ID to rename (from list_labels_tool)
        new_name: The new name for the label

    Returns:
        Dict with 'success' boolean, 'label_id' and 'name' if successful
    """
    try:
        service = get_service()
        # Get current label
        label = await asyncio.to_thread(
            service.users().labels().get(userId="me", id=label_id).execute
        )

        # Update name
        label["name"] = new_name

        # Update the label
        updated_label = await asyncio.to_thread(
            service.users()
            .labels()
            .update(userId="me", id=label_id, body=label)
            .execute
        )

        logger.info(f"Label renamed: {label_id} to {new_name}")
        return {
            "success": True,
            "label_id": updated_label["id"],
            "name": updated_label["name"],
        }
    except HttpError as error:
        logger.error(f"Failed to rename label: {error}")
        return {"success": False, "error": str(error)}
    except Exception as error:
        logger.error(f"Unexpected error: {error}")
        return {"success": False, "error": str(error)}
        return {
            "status": "success",
            "label_id": updated_label["id"],
            "name": updated_label["name"],
        }
    except Exception as error:
        logger.error(f"Rename label error: {str(error)}")
        return {"status": "error", "error_message": str(error)}


@communication_server.tool()
async def delete_label_tool(label_id: str) -> dict[str, Any]:
    """Permanently delete a label from Gmail.

    Args:
        label_id: The label ID to delete (from list_labels_tool)

    Returns:
        Dict with 'success' boolean or 'error' message

    Warning:
        This action cannot be undone.
    """
    try:
        service = get_service()
        await asyncio.to_thread(
            service.users().labels().delete(userId="me", id=label_id).execute
        )

        logger.info(f"Label deleted: {label_id}")
        return {"success": True}
    except HttpError as error:
        logger.error(f"Failed to delete label: {error}")
        return {"success": False, "error": str(error)}
    except Exception as error:
        logger.error(f"Unexpected error: {error}")
        return {"success": False, "error": str(error)}


@communication_server.tool()
async def archive_email_tool(email_id: str) -> dict[str, Any]:
    """Archive a single email.

    Args:
        email_id: The unique Gmail message ID to archive

    Returns:
        Dict with 'success' boolean or 'error' message

    Note:
        Removes from inbox without deleting, keeps in 'All Mail'.
    """
    try:
        service = get_service()
        await asyncio.to_thread(
            service.users()
            .messages()
            .modify(userId="me", id=email_id, body={"removeLabelIds": ["INBOX"]})
            .execute
        )

        logger.info(f"Email archived: {email_id}")
        return {"success": True}
    except HttpError as error:
        logger.error(f"Failed to archive email: {error}")
        return {"success": False, "error": str(error)}
    except Exception as error:
        logger.error(f"Unexpected error: {error}")
        return {"success": False, "error": str(error)}


@communication_server.tool()
async def batch_archive_tool(query: str, max_emails: int = 100) -> dict[str, Any]:
    """Archive multiple emails matching a Gmail search query.

    Args:
        query: Gmail search query to find emails to archive (e.g., 'from:sender older_than:30d')
        max_emails: Maximum number of emails to archive (default: 100)

    Returns:
        Dict with 'success' boolean, 'archived_count'

    Note:
        Use Gmail search syntax to specify which emails to archive.
    """
    try:
        service = get_service()
        user_id = "me"

        response = await asyncio.to_thread(
            service.users()
            .messages()
            .list(userId=user_id, q=query, maxResults=max_emails)
            .execute
        )

        messages = []
        if "messages" in response:
            messages.extend(response["messages"])

        if not messages:
            return {
                "success": True,
                "archived_count": 0,
                "message": "No emails found matching the query.",
            }

        # Archive each email in the batch
        archived_count = 0
        for msg in messages:
            try:
                await asyncio.to_thread(
                    service.users()
                    .messages()
                    .modify(
                        userId="me",
                        id=msg["id"],
                        body={"removeLabelIds": ["INBOX"]},
                    )
                    .execute
                )
                archived_count += 1
            except Exception as e:
                logger.error(f"Error archiving email {msg['id']}: {e}")

        logger.info(f"Batch archived {archived_count} emails")
        return {
            "success": True,
            "archived_count": archived_count,
            "total_found": len(messages),
        }
    except HttpError as error:
        logger.error(f"Batch archive failed: {error}")
        return {"success": False, "error": str(error)}
    except Exception as error:
        logger.error(f"Unexpected error: {error}")
        return {"success": False, "error": str(error)}


@communication_server.tool()
async def list_archived_tool(max_results: int = 100) -> dict[str, Any]:
    """List archived emails.

    Args:
        max_results: Maximum number of archived emails to return (default: 100)

    Returns:
        Dict with 'count' and 'emails' list or 'error' message

    Note:
        Emails not in inbox but still in 'All Mail'.
    """
    try:
        query = "-in:inbox"
        return await search_emails_tool(query, max_results)
    except Exception as error:
        logger.error(f"Failed to list archived emails: {error}")
        return {"error": str(error)}


@communication_server.tool()
async def restore_to_inbox_tool(email_id: str) -> dict[str, Any]:
    """Restore an archived email back to the inbox.

    Args:
        email_id: The unique Gmail message ID to restore to inbox

    Returns:
        Dict with 'success' boolean or 'error' message
    """
    try:
        service = get_service()
        await asyncio.to_thread(
            service.users()
            .messages()
            .modify(userId="me", id=email_id, body={"addLabelIds": ["INBOX"]})
            .execute
        )

        logger.info(f"Email restored to inbox: {email_id}")
        return {"success": True}
    except HttpError as error:
        logger.error(f"Failed to restore to inbox: {error}")
        return {"success": False, "error": str(error)}
    except Exception as error:
        logger.error(f"Unexpected error: {error}")
        return {"success": False, "error": str(error)}
