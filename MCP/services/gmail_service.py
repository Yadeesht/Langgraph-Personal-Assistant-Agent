import asyncio
import base64
import logging
import os
import webbrowser
from base64 import urlsafe_b64decode
from datetime import datetime, timedelta
from email import message_from_bytes
from email.header import decode_header
from email.message import EmailMessage
from typing import Any

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


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


class GmailService:
    def __init__(
        self,
        creds_file_path: str,
        token_path: str,
        scopes: list[str] = [
            "https://mail.google.com/",
            "https://www.googleapis.com/auth/gmail.modify",
            "https://www.googleapis.com/auth/gmail.settings.basic",
            "https://www.googleapis.com/auth/gmail.settings.sharing",
        ],
    ):
        logger.info(f"Initializing GmailService with creds file: {creds_file_path}")
        self.creds_file_path = creds_file_path
        self.token_path = token_path
        self.scopes = scopes
        self.token = self._get_token()
        logger.info("Token retrieved successfully")
        self.service = self._get_service()
        logger.info("Gmail service initialized")
        self.user_email = self._get_user_email()
        logger.info(f"User email retrieved: {self.user_email}")

    def _get_token(self) -> Credentials:
        """Get or refresh Google API token"""

        token = None

        if os.path.exists(self.token_path):
            logger.info("Loading token from file")
            token = Credentials.from_authorized_user_file(self.token_path, self.scopes)

        if not token or not token.valid:
            if token and token.expired and token.refresh_token:
                logger.info("Refreshing token")
                token.refresh(Request())
            else:
                logger.info("Fetching new token")
                flow = InstalledAppFlow.from_client_secrets_file(
                    self.creds_file_path, self.scopes
                )
                token = flow.run_local_server(port=0)

            with open(self.token_path, "w") as token_file:
                token_file.write(token.to_json())
                logger.info(f"Token saved to {self.token_path}")

        return token

    def _get_service(self) -> Any:
        """Initialize Gmail API service"""
        try:
            service = build("gmail", "v1", credentials=self.token)
            return service
        except HttpError as error:
            logger.error(f"An error occurred building Gmail service: {error}")
            raise ValueError(f"An error occurred: {error}")

    def _get_user_email(self) -> str:
        """Get user email address"""
        profile = self.service.users().getProfile(userId="me").execute()
        user_email = profile.get("emailAddress", "")
        return user_email

    async def send_email(
        self,
        recipient_id: str,
        subject: str,
        message: str,
    ) -> dict:
        """Creates and sends an email message"""
        try:
            message_obj = EmailMessage()
            message_obj.set_content(message)

            message_obj["To"] = recipient_id
            message_obj["From"] = self.user_email
            message_obj["Subject"] = subject

            encoded_message = base64.urlsafe_b64encode(message_obj.as_bytes()).decode()
            create_message = {"raw": encoded_message}

            send_message = await asyncio.to_thread(
                self.service.users()
                .messages()
                .send(userId="me", body=create_message)
                .execute
            )
            logger.info(f"Message sent: {send_message['id']}")
            return {"status": "success", "message_id": send_message["id"]}
        except HttpError as error:
            return {"status": "error", "error_message": str(error)}

    async def open_email(self, email_id: str) -> str:
        """Opens email in browser given ID."""
        try:
            url = f"https://mail.google.com/#all/{email_id}"
            webbrowser.open(url, new=0, autoraise=True)
            return "Email opened in browser successfully."
        except HttpError as error:
            return f"An HttpError occurred: {str(error)}"

    async def get_detailed_email_info(
        self, email_id: str, format: str = "full"
    ) -> dict:
        """
        Retrieve all possible information from an email message.

        Available formats:
        - 'minimal': Returns only email message ID and labels
        - 'full': Returns the full email message data (default)
        - 'raw': Returns the raw MIME message
        - 'metadata': Returns only email message metadata
        """

        # 1. Get FULL message details
        full_message = (
            self.service.users()
            .messages()
            .get(
                userId="me",
                id=email_id,
                format="full",  # or 'minimal', 'raw', 'metadata'
            )
            .execute()
        )

        # Available top-level fields:
        message_info = {
            "id": full_message["id"],  # Message ID
            "threadId": full_message["threadId"],  # Thread ID
            "labelIds": full_message.get(
                "labelIds", []
            ),  # Labels (INBOX, UNREAD, etc.)
            "snippet": full_message.get("snippet", ""),  # Preview text
            "historyId": full_message.get("historyId"),  # History ID for sync
            "internalDate": full_message.get("internalDate"),  # Unix timestamp (ms)
            "sizeEstimate": full_message.get("sizeEstimate"),  # Estimated size in bytes
        }

        # 2. Extract headers from payload
        headers = full_message.get("payload", {}).get("headers", [])

        # Common headers you can extract:
        header_fields = {
            "Subject": None,
            "From": None,
            "To": None,
            "Cc": None,
            "Bcc": None,
            "Date": None,
            "Message-ID": None,
            "In-Reply-To": None,
            "References": None,
            "Reply-To": None,
            "Return-Path": None,
            "Delivered-To": None,
            "Content-Type": None,
            "MIME-Version": None,
            "X-Gmail-Labels": None,
            "List-Unsubscribe": None,  # For mailing lists
            "Precedence": None,
            "X-Priority": None,
            "Importance": None,
        }

        for header in headers:
            header_name = header["name"]
            if header_name in header_fields:
                header_fields[header_name] = header["value"]

        # 3. Extract body parts
        payload = full_message.get("payload", {})

        body_info = {
            "mimeType": payload.get(
                "mimeType"
            ),  # text/plain, text/html, multipart/alternative
            "filename": payload.get("filename"),
            "parts": [],  # For multipart messages
        }

        # 4. Get attachments info
        attachments = []

        def extract_parts(parts):
            for part in parts:
                if part.get("filename"):
                    attachments.append(
                        {
                            "filename": part["filename"],
                            "mimeType": part["mimeType"],
                            "size": part["body"].get("size", 0),
                            "attachmentId": part["body"].get("attachmentId"),
                        }
                    )

                # Recursive for nested parts
                if "parts" in part:
                    extract_parts(part["parts"])

        if "parts" in payload:
            extract_parts(payload["parts"])

        return {
            "message_info": message_info,
            "headers": header_fields,
            "body_info": body_info,
            "attachments": attachments,
        }

    # Modify the EXISTING get_unread_emails method in GmailService class

    async def get_unread_emails(
        self, date=10, max_results=50
    ) -> list[dict[str, str]] | str:
        """
        Retrieves detailed unread messages from mailbox.
        Returns list of messages with subject, from, date, snippet, etc.
        """
        try:
            user_id = "me"
            after_date = (datetime.now() - timedelta(days=date)).strftime("%Y/%m/%d")
            query = f"in:inbox is:unread category:primary after:{after_date}"

            response = (
                self.service.users()
                .messages()
                .list(userId=user_id, q=query, maxResults=max_results)
                .execute()
            )

            messages = []
            if "messages" in response:
                # Get detailed info for each message
                for msg in response["messages"]:
                    email_id = msg["id"]

                    # Fetch full metadata
                    full_msg = (
                        self.service.users()
                        .messages()
                        .get(
                            userId=user_id,
                            id=email_id,
                            format="metadata",
                            metadataHeaders=["Subject", "From", "Date", "To"],
                        )
                        .execute()
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
                        "to": next(
                            (h["value"] for h in headers if h["name"] == "To"), ""
                        ),
                    }

                    messages.append(email_details)

            return messages

        except HttpError as error:
            return f"An HttpError occurred: {str(error)}"

    async def read_email(self, email_id: str) -> dict[str, str] | str:
        """Retrieves email contents including to, from, subject, and contents."""
        try:
            msg = (
                self.service.users()
                .messages()
                .get(userId="me", id=email_id, format="raw")
                .execute()
            )
            email_metadata = {}

            # Decode the base64URL encoded raw content
            raw_data = msg["raw"]
            decoded_data = urlsafe_b64decode(raw_data)

            # Parse the RFC 2822 email
            mime_message = message_from_bytes(decoded_data)

            # Extract the email body
            body = None
            if mime_message.is_multipart():
                for part in mime_message.walk():
                    # Extract the text/plain part
                    if part.get_content_type() == "text/plain":
                        body = part.get_payload(decode=True).decode()
                        break
            else:
                # For non-multipart messages
                body = mime_message.get_payload(decode=True).decode()
            email_metadata["content"] = body

            # Extract metadata
            email_metadata["subject"] = decode_mime_header(
                mime_message.get("subject", "")
            )
            email_metadata["from"] = mime_message.get("from", "")
            email_metadata["to"] = mime_message.get("to", "")
            email_metadata["date"] = mime_message.get("date", "")

            logger.info(f"Email read: {email_id}")

            # We want to mark email as read once we read it
            await self.mark_email_as_read(email_id)

            return email_metadata
        except HttpError as error:
            return f"An HttpError occurred: {str(error)}"

    async def trash_email(self, email_id: str) -> str:
        """Moves email to trash given ID."""
        try:
            self.service.users().messages().trash(userId="me", id=email_id).execute()
            logger.info(f"Email moved to trash: {email_id}")
            return "Email moved to trash successfully."
        except HttpError as error:
            return f"An HttpError occurred: {str(error)}"

    async def mark_email_as_read(self, email_id: str) -> str:
        """Marks email as read given ID."""
        try:
            self.service.users().messages().modify(
                userId="me", id=email_id, body={"removeLabelIds": ["UNREAD"]}
            ).execute()
            logger.info(f"Email marked as read: {email_id}")
            return "Email marked as read."
        except HttpError as error:
            return f"An HttpError occurred: {str(error)}"

    async def create_draft(self, recipient_id: str, subject: str, message: str) -> dict:
        """Creates a draft email message"""
        try:
            message_obj = EmailMessage()
            message_obj.set_content(message)

            message_obj["To"] = recipient_id
            message_obj["From"] = self.user_email
            message_obj["Subject"] = subject

            encoded_message = base64.urlsafe_b64encode(message_obj.as_bytes()).decode()
            create_message = {"raw": encoded_message}

            draft = await asyncio.to_thread(
                self.service.users()
                .drafts()
                .create(userId="me", body={"message": create_message})
                .execute
            )
            logger.info(f"Draft created: {draft['id']}")
            return {"status": "success", "draft_id": draft["id"]}
        except HttpError as error:
            return {"status": "error", "error_message": str(error)}

    async def list_drafts(self) -> list[dict] | str:
        """Lists all draft emails"""
        try:
            results = await asyncio.to_thread(
                self.service.users().drafts().list(userId="me").execute
            )
            drafts = results.get("drafts", [])

            draft_list = []
            for draft in drafts:
                draft_id = draft["id"]
                # Get the draft details to extract subject and recipient
                draft_data = await asyncio.to_thread(
                    self.service.users().drafts().get(userId="me", id=draft_id).execute
                )

                message = draft_data.get("message", {})
                headers = message.get("payload", {}).get("headers", [])

                subject = next(
                    (
                        header["value"]
                        for header in headers
                        if header["name"].lower() == "subject"
                    ),
                    "No Subject",
                )
                to = next(
                    (
                        header["value"]
                        for header in headers
                        if header["name"].lower() == "to"
                    ),
                    "No Recipient",
                )

                draft_list.append({"id": draft_id, "subject": subject, "to": to})

            return draft_list
        except HttpError as error:
            return f"An HttpError occurred: {str(error)}"

    async def list_labels(self) -> list[dict] | str:
        """Lists all labels in the user's mailbox"""
        try:
            results = await asyncio.to_thread(
                self.service.users().labels().list(userId="me").execute
            )
            labels = results.get("labels", [])

            label_list = []
            for label in labels:
                label_list.append(
                    {
                        "id": label["id"],
                        "name": label["name"],
                        "type": label["type"],  # 'system' or 'user'
                    }
                )

            return label_list
        except HttpError as error:
            return f"An HttpError occurred: {str(error)}"

    async def create_label(self, name: str) -> dict | str:
        """Creates a new label"""
        try:
            label_object = {
                "name": name,
                "labelListVisibility": "labelShow",  # Show in label list
                "messageListVisibility": "show",  # Show in message list
            }

            created_label = await asyncio.to_thread(
                self.service.users()
                .labels()
                .create(userId="me", body=label_object)
                .execute
            )

            logger.info(f"Label created: {created_label['id']}")
            return {
                "status": "success",
                "label_id": created_label["id"],
                "name": created_label["name"],
            }
        except HttpError as error:
            return {"status": "error", "error_message": str(error)}

    async def apply_label(self, email_id: str, label_id: str) -> str:
        """Applies a label to an email"""
        try:
            await asyncio.to_thread(
                self.service.users()
                .messages()
                .modify(userId="me", id=email_id, body={"addLabelIds": [label_id]})
                .execute
            )

            logger.info(f"Label {label_id} applied to email {email_id}")
            return f"Label applied successfully to email."
        except HttpError as error:
            return f"An HttpError occurred: {str(error)}"

    async def remove_label(self, email_id: str, label_id: str) -> str:
        """Removes a label from an email"""
        try:
            await asyncio.to_thread(
                self.service.users()
                .messages()
                .modify(userId="me", id=email_id, body={"removeLabelIds": [label_id]})
                .execute
            )

            logger.info(f"Label {label_id} removed from email {email_id}")
            return f"Label removed successfully from email."
        except HttpError as error:
            return f"An HttpError occurred: {str(error)}"

    async def search_by_label(self, label_id: str) -> list[dict] | str:
        """Searches for emails with a specific label"""
        try:
            query = f"label:{label_id}"

            response = await asyncio.to_thread(
                self.service.users().messages().list(userId="me", q=query).execute
            )

            messages = []
            if "messages" in response:
                messages.extend(response["messages"])

            while "nextPageToken" in response:
                page_token = response["nextPageToken"]
                response = await asyncio.to_thread(
                    self.service.users()
                    .messages()
                    .list(userId="me", q=query, pageToken=page_token)
                    .execute
                )
                messages.extend(response["messages"])

            return messages
        except HttpError as error:
            return f"An HttpError occurred: {str(error)}"

    async def create_filter(
        self,
        from_email: str = None,
        to_email: str = None,
        subject: str = None,
        query: str = None,
        has_attachment: bool = None,
        exclude_chats: bool = None,
        size_comparison: str = None,
        size: int = None,
        add_label_ids: list[str] = None,
        remove_label_ids: list[str] = None,
        forward_to: str = None,
    ) -> dict | str:
        """Creates a new email filter

        Args:
            from_email: Email from a specific sender
            to_email: Email to a specific recipient
            subject: Email with a specific subject
            query: Email matching a custom query
            has_attachment: Email has an attachment
            exclude_chats: Exclude chats from filter
            size_comparison: 'larger' or 'smaller'
            size: Size in bytes for comparison
            add_label_ids: Labels to add to matching emails
            remove_label_ids: Labels to remove from matching emails
            forward_to: Email address to forward matching emails to
        """
        try:
            # Build the filter criteria
            criteria = {}
            if from_email:
                criteria["from"] = from_email
            if to_email:
                criteria["to"] = to_email
            if subject:
                criteria["subject"] = subject
            if query:
                criteria["query"] = query
            if has_attachment is not None:
                criteria["hasAttachment"] = has_attachment
            if exclude_chats is not None:
                criteria["excludeChats"] = exclude_chats
            if size_comparison and size:
                if size_comparison.lower() == "larger":
                    criteria["sizeComparison"] = "larger"
                    criteria["size"] = size
                elif size_comparison.lower() == "smaller":
                    criteria["sizeComparison"] = "smaller"
                    criteria["size"] = size

            # Build the filter actions
            action = {}
            if add_label_ids:
                action["addLabelIds"] = add_label_ids
            if remove_label_ids:
                action["removeLabelIds"] = remove_label_ids
            if forward_to:
                action["forward"] = forward_to

            # Create the filter
            filter_object = {"criteria": criteria, "action": action}

            created_filter = await asyncio.to_thread(
                self.service.users()
                .settings()
                .filters()
                .create(userId="me", body=filter_object)
                .execute
            )

            logger.info(f"Filter created: {created_filter['id']}")
            return {
                "status": "success",
                "filter_id": created_filter["id"],
                "filter": created_filter,
            }
        except HttpError as error:
            return {"status": "error", "error_message": str(error)}

    async def list_filters(self) -> list[dict] | str:
        """Lists all filters in the user's mailbox"""
        try:
            results = await asyncio.to_thread(
                self.service.users().settings().filters().list(userId="me").execute
            )
            filters = results.get("filter", [])
            return filters
        except HttpError as error:
            return f"An HttpError occurred: {str(error)}"

    async def get_filter(self, filter_id: str) -> dict | str:
        """Gets a specific filter by ID"""
        try:
            filter_data = await asyncio.to_thread(
                self.service.users()
                .settings()
                .filters()
                .get(userId="me", id=filter_id)
                .execute
            )
            return filter_data
        except HttpError as error:
            return f"An HttpError occurred: {str(error)}"

    async def delete_filter(self, filter_id: str) -> str:
        """Deletes a filter by ID"""
        try:
            await asyncio.to_thread(
                self.service.users()
                .settings()
                .filters()
                .delete(userId="me", id=filter_id)
                .execute
            )

            logger.info(f"Filter deleted: {filter_id}")
            return f"Filter deleted successfully."
        except HttpError as error:
            return f"An HttpError occurred: {str(error)}"

    async def search_emails(
        self, query: str, max_results: int = 50
    ) -> list[dict] | str:
        """
        Searches for emails using Gmail's search syntax.

        Args:
            query: Gmail search query (e.g., 'from:example@gmail.com', 'subject:hello', etc.)
            max_results: Maximum number of results to return (default: 50)

        Returns:
            List of message objects or error message
        """
        try:
            user_id = "me"

            response = await asyncio.to_thread(
                self.service.users()
                .messages()
                .list(userId=user_id, q=query, maxResults=max_results)
                .execute
            )

            messages = []
            if "messages" in response:
                messages.extend(response["messages"])

            # Get additional pages if available and needed
            while "nextPageToken" in response and len(messages) < max_results:
                page_token = response["nextPageToken"]
                response = await asyncio.to_thread(
                    self.service.users()
                    .messages()
                    .list(
                        userId=user_id,
                        q=query,
                        pageToken=page_token,
                        maxResults=max_results - len(messages),
                    )
                    .execute
                )
                if "messages" in response:
                    messages.extend(response["messages"])

            # Get basic metadata for each message
            result_messages = []
            for msg in messages:
                msg_data = await asyncio.to_thread(
                    self.service.users()
                    .messages()
                    .get(
                        userId=user_id,
                        id=msg["id"],
                        format="metadata",
                        metadataHeaders=["Subject", "From", "Date"],
                    )
                    .execute
                )

                headers = msg_data.get("payload", {}).get("headers", [])

                subject = next(
                    (
                        header["value"]
                        for header in headers
                        if header["name"].lower() == "subject"
                    ),
                    "No Subject",
                )
                sender = next(
                    (
                        header["value"]
                        for header in headers
                        if header["name"].lower() == "from"
                    ),
                    "Unknown Sender",
                )
                date = next(
                    (
                        header["value"]
                        for header in headers
                        if header["name"].lower() == "date"
                    ),
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

            return result_messages

        except HttpError as error:
            return f"An HttpError occurred: {str(error)}"

    async def create_folder(self, name: str) -> dict | str:
        """
        Creates a new folder (implemented as a label with special handling).

        Args:
            name: Name of the folder to create

        Returns:
            Dictionary with status and folder information or error message
        """
        try:
            # In Gmail, folders are just labels with special visibility settings
            label_object = {
                "name": name,
                "labelListVisibility": "labelShow",
                "messageListVisibility": "show",
                "type": "user",  # Ensure it's a user label
            }

            created_label = await asyncio.to_thread(
                self.service.users()
                .labels()
                .create(userId="me", body=label_object)
                .execute
            )

            logger.info(f"Folder created: {created_label['id']}")
            return {
                "status": "success",
                "folder_id": created_label["id"],
                "name": created_label["name"],
            }
        except HttpError as error:
            return {"status": "error", "error_message": str(error)}

    async def move_to_folder(self, email_id: str, folder_id: str) -> str:
        """
        Moves an email to a folder by:
        1. Applying the folder label
        2. Removing the INBOX label (to remove from inbox)

        Args:
            email_id: ID of the email to move
            folder_id: ID of the folder (label) to move to

        Returns:
            Success or error message
        """
        try:
            # First, apply the folder label
            await asyncio.to_thread(
                self.service.users()
                .messages()
                .modify(
                    userId="me",
                    id=email_id,
                    body={"addLabelIds": [folder_id], "removeLabelIds": ["INBOX"]},
                )
                .execute
            )

            logger.info(f"Email {email_id} moved to folder {folder_id}")
            return f"Email moved to folder successfully."
        except HttpError as error:
            return f"An HttpError occurred: {str(error)}"

    async def list_folders(self) -> list[dict] | str:
        """
        Lists all user-created labels (folders)

        Returns:
            List of folder information or error message
        """
        try:
            results = await asyncio.to_thread(
                self.service.users().labels().list(userId="me").execute
            )
            labels = results.get("labels", [])

            # Filter to only include user-created labels (folders)
            folders = [
                {"id": label["id"], "name": label["name"]}
                for label in labels
                if label["type"] == "user"
            ]

            return folders
        except HttpError as error:
            return f"An HttpError occurred: {str(error)}"

    async def rename_label(self, label_id: str, new_name: str) -> dict | str:
        """
        Renames an existing label

        Args:
            label_id: ID of the label to rename
            new_name: New name for the label

        Returns:
            Dictionary with status and updated label information or error message
        """
        try:
            # First, get the current label to preserve its settings
            label = await asyncio.to_thread(
                self.service.users().labels().get(userId="me", id=label_id).execute
            )

            # Update only the name field
            label["name"] = new_name

            # Update the label
            updated_label = await asyncio.to_thread(
                self.service.users()
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
        except HttpError as error:
            return {"status": "error", "error_message": str(error)}

    async def delete_label(self, label_id: str) -> str:
        """
        Deletes a label

        Args:
            label_id: ID of the label to delete

        Returns:
            Success or error message
        """
        try:
            await asyncio.to_thread(
                self.service.users().labels().delete(userId="me", id=label_id).execute
            )

            logger.info(f"Label deleted: {label_id}")
            return f"Label deleted successfully."
        except HttpError as error:
            return f"An HttpError occurred: {str(error)}"

    async def archive_email(self, email_id: str) -> str:
        """
        Archives an email by removing the INBOX label

        Args:
            email_id: ID of the email to archive

        Returns:
            Success or error message
        """
        try:
            await asyncio.to_thread(
                self.service.users()
                .messages()
                .modify(userId="me", id=email_id, body={"removeLabelIds": ["INBOX"]})
                .execute
            )

            logger.info(f"Email archived: {email_id}")
            return f"Email archived successfully."
        except HttpError as error:
            return f"An HttpError occurred: {str(error)}"

    async def batch_archive(self, query: str, max_emails: int = 100) -> dict:
        """
        Archives multiple emails matching a search query

        Args:
            query: Gmail search query to find emails to archive
            max_emails: Maximum number of emails to archive in one batch

        Returns:
            Dictionary with status and count of archived emails
        """
        try:
            # First, search for emails matching the query
            user_id = "me"

            response = await asyncio.to_thread(
                self.service.users()
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
                        self.service.users()
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

    async def list_archived(self, max_results: int = 50) -> list[dict] | str:
        """
        Lists archived emails (emails not in inbox)

        Args:
            max_results: Maximum number of results to return

        Returns:
            List of archived email objects or error message
        """
        try:
            # Search for emails that are in "All Mail" but not in "Inbox"
            query = "-in:inbox"

            # Use the existing search_emails method
            return await self.search_emails(query, max_results)
        except Exception as error:
            return f"An error occurred: {str(error)}"

    async def restore_to_inbox(self, email_id: str) -> str:
        """
        Restores an archived email to the inbox

        Args:
            email_id: ID of the email to restore

        Returns:
            Success or error message
        """
        try:
            await asyncio.to_thread(
                self.service.users()
                .messages()
                .modify(userId="me", id=email_id, body={"addLabelIds": ["INBOX"]})
                .execute
            )

            logger.info(f"Email restored to inbox: {email_id}")
            return f"Email restored to inbox successfully."
        except HttpError as error:
            return f"An HttpError occurred: {str(error)}"
