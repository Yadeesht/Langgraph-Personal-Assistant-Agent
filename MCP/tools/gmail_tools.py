import asyncio
import base64
import logging
import sys
import webbrowser
from base64 import urlsafe_b64decode
from datetime import datetime, timedelta
from email import message_from_bytes
from email.header import decode_header
from email.message import EmailMessage
from pathlib import Path

from googleapiclient.errors import HttpError

from MCP.auth.service_decoder import get_google_service
from MCP.core.server_init import communication_server

root_dir = Path(__file__).parent.parent.parent
sys.path.insert(0, str(root_dir))

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


# auth
def get_service():
    """Get Gmail service using shared auth"""
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
    """Helper function to decode encoded email headers"""
    decoded_parts = decode_header(header)
    decoded_string = ""
    for part, encoding in decoded_parts:
        if isinstance(part, bytes):
            decoded_string += part.decode(encoding or "utf-8")
        else:
            decoded_string += part
    return decoded_string


async def get_user_email(service) -> str:
    """Get the authenticated user's email address"""
    profile = await asyncio.to_thread(service.users().getProfile(userId="me").execute)
    return profile.get("emailAddress", "")


@communication_server.tool()
async def send_email_tool(recipient_id: str, subject: str, message: str):
    """
    description="Send an email to a recipient."

    schema={
        "type": "object",
        "properties": {
            "recipient_id": {
                "type": "string",
                "description": "Recipient's email address (e.g., user@example.com)."
            },
            "subject": {
                "type": "string",
                "description": "Email subject line."
            },
            "message": {
                "type": "string",
                "description": "Email body content (plain text or HTML)."
            }
        },
        "required": ["recipient_id", "subject", "message"]
    }
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

        logger.info(f"Message sent: {send_message['id']}")
        return {"status": "success", "message_id": send_message["id"]}
    except Exception as error:
        logger.error(f"Send email error: {str(error)}")
        return {"status": "error", "error_message": str(error)}


@communication_server.tool()
async def open_email_tool(email_id: str):
    """
    description="Open a specific email in the browser using its Gmail web interface."

    schema={
        "type": "object",
        "properties": {
            "email_id": {
                "type": "string",
                "description": "The unique Gmail message ID."
            }
        },
        "required": ["email_id"]
    }
    """
    try:
        url = f"https://mail.google.com/#all/{email_id}"
        webbrowser.open(url, new=0, autoraise=True)
        return {"status": "success", "message": "Email opened in browser successfully."}
    except Exception as error:
        logger.error(f"Open email error: {str(error)}")
        return {"status": "error", "error_message": str(error)}


@communication_server.tool()
async def get_unread_emails_tool(date=10, max_results=20):
    """
    description="Fetch unread Gmail emails from the last 'n' days."

    schema={
        "type": "object",
        "properties": {
            "date": {
                "type": "integer",
                "description": "Number of days to look back for unread emails (default: 10)."
            }
        },
        "required": []
    }
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
                    "threadId": msg["threadId"],
                    "snippet": full_msg.get("snippet", ""),
                    "labels": full_msg.get("labelIds", []),
                    "size": full_msg.get("sizeEstimate", 0),
                    "internalDate": full_msg.get("internalDate"),
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
    except Exception as error:
        logger.error(f"Get unread emails error: {str(error)}")
        return {"error": str(error)}


@communication_server.tool()
async def read_email_tool(email_id: str):
    """
    description="Read the full content of a specific email by its ID. Use this after getting unread emails to view the complete message."

    schema={
        "type": "object",
        "properties": {
            "email_id": {
                "type": "string",
                "description": "The unique Gmail message ID (from get_unread_emails_tool or search results)."
            }
        },
        "required": ["email_id"]
    }
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
        decoded_data = urlsafe_b64decode(raw_data)

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
    except Exception as error:
        logger.error(f"Read email error: {str(error)}")
        return {"error": str(error)}


@communication_server.tool()
async def trash_email_tool(email_id: str):
    """
    description="Move an email to trash. Always confirm with user before trashing any email."

    schema={
        "type": "object",
        "properties": {
            "email_id": {
                "type": "string",
                "description": "The unique Gmail message ID to move to trash."
            }
        },
        "required": ["email_id"]
    }
    """

    try:
        service = get_service()
        await asyncio.to_thread(
            service.users().messages().trash(userId="me", id=email_id).execute
        )
        logger.info(f"Email moved to trash: {email_id}")
        return {"status": "success", "message": "Email moved to trash successfully."}
    except Exception as error:
        logger.error(f"Trash email error: {str(error)}")
        return {"error": str(error)}


@communication_server.tool()
async def mark_email_as_read_tool(email_id: str):
    """
    description="Mark a specific email as read to remove the unread status."

    schema={
        "type": "object",
        "properties": {
            "email_id": {
                "type": "string",
                "description": "The unique Gmail message ID to mark as read."
            }
        },
        "required": ["email_id"]
    }
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
        return {"status": "success", "message": "Email marked as read."}
    except Exception as error:
        logger.error(f"Mark as read error: {str(error)}")
        return {"error": str(error)}


@communication_server.tool()
async def create_draft_tool(recipient_id: str, subject: str, message: str):
    """
    description="Create a draft email without sending it. Use this when user wants to draft an email for later review."

    schema={
        "type": "object",
        "properties": {
            "recipient_id": {
                "type": "string",
                "description": "Recipient's email address (e.g., user@example.com)."
            },
            "subject": {
                "type": "string",
                "description": "Email subject line."
            },
            "message": {
                "type": "string",
                "description": "Email body content (plain text or HTML)."
            }
        },
        "required": ["recipient_id", "subject", "message"]
    }
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
        return {"status": "success", "draft_id": draft["id"]}
    except Exception as error:
        logger.error(f"Create draft error: {str(error)}")
        return {"status": "error", "error_message": str(error)}


@communication_server.tool()
async def list_drafts_tool():
    """
    description="List all draft emails in the user's mailbox."

    schema={
        "type": "object",
        "properties": {},
        "required": []
    }
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
    except Exception as error:
        logger.error(f"List drafts error: {str(error)}")
        return {"error": str(error)}


@communication_server.tool()
async def list_labels_tool():
    """
    description="List all labels (tags/folders) available in the user's Gmail mailbox."

    schema={
        "type": "object",
        "properties": {},
        "required": []
    }
    """

    try:
        service = get_service()
        results = await asyncio.to_thread(
            service.users().labels().list(userId="me").execute
        )
        labels = results.get("labels", [])

        label_list = []
        for label in labels:
            label_list.append(
                {
                    "id": label["id"],
                    "name": label["name"],
                    "type": label.get("type", "user"),
                }
            )

        return {"count": len(label_list), "labels": label_list}
    except Exception as error:
        logger.error(f"List labels error: {str(error)}")
        return {"error": str(error)}


@communication_server.tool()
async def create_label_tool(name: str):
    """
    description="Create a new label (tag/folder) in Gmail for organizing emails."

    schema={
        "type": "object",
        "properties": {
            "name": {
                "type": "string",
                "description": "The name of the new label to create."
            }
        },
        "required": ["name"]
    }
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
            "status": "success",
            "label_id": created_label["id"],
            "name": created_label["name"],
        }
    except Exception as error:
        logger.error(f"Create label error: {str(error)}")
        return {"status": "error", "error_message": str(error)}


@communication_server.tool()
async def apply_label_tool(email_id: str, label_id: str):
    """
    description="Apply a label (tag) to a specific email for organization."

    schema={
        "type": "object",
        "properties": {
            "email_id": {
                "type": "string",
                "description": "The unique Gmail message ID."
            },
            "label_id": {
                "type": "string",
                "description": "The label ID to apply (from list_labels_tool)."
            }
        },
        "required": ["email_id", "label_id"]
    }
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
        return {"status": "success", "message": "Label applied successfully to email."}
    except Exception as error:
        logger.error(f"Apply label error: {str(error)}")
        return {"error": str(error)}


@communication_server.tool()
async def remove_labels_tool(email_id: str, label_id: str):
    """
    description="Remove a label (tag) from a specific email."

    schema={
        "type": "object",
        "properties": {
            "email_id": {
                "type": "string",
                "description": "The unique Gmail message ID."
            },
            "label_id": {
                "type": "string",
                "description": "The label ID to remove (from list_labels_tool)."
            }
        },
        "required": ["email_id", "label_id"]
    }
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
        return {
            "status": "success",
            "message": "Label removed successfully from email.",
        }
    except Exception as error:
        logger.error(f"Remove label error: {str(error)}")
        return {"error": str(error)}


@communication_server.tool()
async def search_by_label_tool(label_id: str):
    """
    description="Search for all emails that have a specific label applied."

    schema={
        "type": "object",
        "properties": {
            "label_id": {
                "type": "string",
                "description": "The label ID to search for (from list_labels_tool)."
            }
        },
        "required": ["label_id"]
    }
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

        return messages
    except HttpError as error:
        return f"An HttpError occurred: {str(error)}"


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
async def list_filters_tool():
    """
    description="List all email filters configured in the user's Gmail account."

    schema={
        "type": "object",
        "properties": {},
        "required": []
    }
    """
    try:
        service = get_service()
        results = await asyncio.to_thread(
            service.users().settings().filters().list(userId="me").execute
        )
        filters = results.get("filter", [])
        return filters
    except HttpError as error:
        return f"An HttpError occurred: {str(error)}"


@communication_server.tool()
async def get_filter_tool(filter_id: str):
    """
    description="Get detailed information about a specific email filter by its ID."

    schema={
        "type": "object",
        "properties": {
            "filter_id": {
                "type": "string",
                "description": "The filter ID to retrieve (from list_filters_tool)."
            }
        },
        "required": ["filter_id"]
    }
    """

    try:
        service = get_service()
        filter_data = await asyncio.to_thread(
            service.users().settings().filters().get(userId="me", id=filter_id).execute
        )
        return filter_data
    except HttpError as error:
        return f"An HttpError occurred: {str(error)}"


@communication_server.tool()
async def delete_filter_tool(filter_id: str):
    """
    description="Delete a specific email filter by its ID."

    schema={
        "type": "object",
        "properties": {
            "filter_id": {
                "type": "string",
                "description": "The filter ID to delete (from list_filters_tool)."
            }
        },
        "required": ["filter_id"]
    }
    """

    try:
        service = get_service()
        await asyncio.to_thread(
            service.users()
            .settings()
            .filters()
            .delete(userId="me", id=filter_id)
            .execute()
        )
        logger.info(f"Filter deleted: {filter_id}")
        return "Filter deleted successfully."
    except HttpError as error:
        return f"An HttpError occurred: {str(error)}"


@communication_server.tool()
async def search_emails_tool(query: str, max_results: int | None = None):
    """
    description="Search for emails using Gmail's advanced search syntax. Supports queries like 'from:sender@example.com subject:invoice after:2025/01/01 has:attachment'."

    schema={
        "type": "object",
        "properties": {
            "query": {
                "type": "string",
                "description": "Gmail search query using syntax (from:, subject:, after:, before:, has:attachment, etc.)."
            },
            "max_results": {
                "type": "integer",
                "description": "Maximum number of emails to return (optional)."
            }
        },
        "required": ["query"]
    }
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
                    "threadId": msg["threadId"],
                    "subject": subject,
                    "from": sender,
                    "date": date,
                    "snippet": msg_data.get("snippet", ""),
                }
            )

        return {"count": len(result_messages), "emails": result_messages}
    except Exception as error:
        logger.error(f"Search emails error: {str(error)}")
        return {"error": str(error)}


@communication_server.tool()
async def create_folder_tool(name: str):
    """
    description="Create a new folder in Gmail. Note: In Gmail, folders are implemented as labels with special handling."

    schema={
        "type": "object",
        "properties": {
            "name": {
                "type": "string",
                "description": "The name of the new folder to create."
            }
        },
        "required": ["name"]
    }
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
            "status": "success",
            "folder_id": created_label["id"],
            "name": created_label["name"],
        }
    except Exception as error:
        logger.error(f"Create folder error: {str(error)}")
        return {"status": "error", "error_message": str(error)}


@communication_server.tool()
async def move_to_folder_tool(email_id: str, folder_id: str):
    """
    description="Move an email to a specific folder (applies folder label and removes from inbox)."

    schema={
        "type": "object",
        "properties": {
            "email_id": {
                "type": "string",
                "description": "The unique Gmail message ID."
            },
            "folder_id": {
                "type": "string",
                "description": "The folder ID (label ID) to move the email to."
            }
        },
        "required": ["email_id", "folder_id"]
    }
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
        return {"status": "success", "message": "Email moved to folder successfully."}
    except Exception as error:
        logger.error(f"Move to folder error: {str(error)}")
        return {"error": str(error)}


@communication_server.tool()
async def list_folders_tool():
    """
    description="List all user-created folders in Gmail."

    schema={
        "type": "object",
        "properties": {},
        "required": []
    }
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
    except Exception as error:
        logger.error(f"List folders error: {str(error)}")
        return {"error": str(error)}


@communication_server.tool()
async def rename_labels_tool(label_id: str, new_name: str):
    """
    description="Rename an existing label to a new name."

    schema={
        "type": "object",
        "properties": {
            "label_id": {
                "type": "string",
                "description": "The label ID to rename (from list_labels_tool)."
            },
            "new_name": {
                "type": "string",
                "description": "The new name for the label."
            }
        },
        "required": ["label_id", "new_name"]
    }
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
            "status": "success",
            "label_id": updated_label["id"],
            "name": updated_label["name"],
        }
    except Exception as error:
        logger.error(f"Rename label error: {str(error)}")
        return {"status": "error", "error_message": str(error)}


@communication_server.tool()
async def delete_label_tool(label_id: str):
    """
    description="Permanently delete a label from Gmail. This action cannot be undone."

    schema={
        "type": "object",
        "properties": {
            "label_id": {
                "type": "string",
                "description": "The label ID to delete (from list_labels_tool)."
            }
        },
        "required": ["label_id"]
    }
    """

    try:
        service = get_service()
        await asyncio.to_thread(
            service.users().labels().delete(userId="me", id=label_id).execute
        )

        logger.info(f"Label deleted: {label_id}")
        return {"status": "success", "message": "Label deleted successfully."}
    except Exception as error:
        logger.error(f"Delete label error: {str(error)}")
        return {"error": str(error)}


@communication_server.tool()
async def archive_email_tool(email_id: str):
    """
    description="Archive a single email (removes from inbox without deleting, keeps in 'All Mail')."

    schema={
        "type": "object",
        "properties": {
            "email_id": {
                "type": "string",
                "description": "The unique Gmail message ID to archive."
            }
        },
        "required": ["email_id"]
    }
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
        return {"status": "success", "message": "Email archived successfully."}
    except Exception as error:
        logger.error(f"Archive email error: {str(error)}")
        return {"error": str(error)}


@communication_server.tool()
async def batch_archive_tool(query: str, max_emails: int = 100):
    """
    description="Archive multiple emails matching a Gmail search query. Use Gmail search syntax to specify which emails to archive."

    schema={
        "type": "object",
        "properties": {
            "query": {
                "type": "string",
                "description": "Gmail search query to find emails to archive (e.g., 'from:sender older_than:30d')."
            },
            "max_emails": {
                "type": "integer",
                "description": "Maximum number of emails to archive (default: 100)."
            }
        },
        "required": ["query"]
    }
    """
    try:
        service = get_service()
        # First, search for emails matching the query
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
                "status": "success",
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
                logger.error(f"Error archiving email {msg['id']}: {str(e)}")

        logger.info(f"Batch archived {archived_count} emails")
        return {
            "status": "success",
            "archived_count": archived_count,
            "total_found": len(messages),
            "message": f"Successfully archived {archived_count} out of {len(messages)} emails.",
        }
    except HttpError as error:
        return {"status": "error", "error_message": str(error)}


@communication_server.tool()
async def list_archived_tool(max_results: int = 100):
    """
    description="List archived emails (emails not in inbox but still in 'All Mail')."

    schema={
        "type": "object",
        "properties": {
            "max_results": {
                "type": "integer",
                "description": "Maximum number of archived emails to return (default: 100)."
            }
        },
        "required": []
    }
    """
    try:
        service = get_service()
        # Search for emails that are in "All Mail" but not in "Inbox"
        query = "-in:inbox"
        # Use the existing search_emails method
        return await search_emails_tool(service, query, max_results)
    except Exception as error:
        return f"An error occurred: {str(error)}"


@communication_server.tool()
async def restore_to_inbox_tool(email_id: str):
    """
    description="Restore an archived email back to the inbox."

    schema={
        "type": "object",
        "properties": {
            "email_id": {
                "type": "string",
                "description": "The unique Gmail message ID to restore to inbox."
            }
        },
        "required": ["email_id"]
    }
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
        return {"status": "success", "message": "Email restored to inbox successfully."}
    except Exception as error:
        logger.error(f"Restore to inbox error: {str(error)}")
        return {"error": str(error)}
