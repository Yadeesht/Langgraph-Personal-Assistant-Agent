import mcp.types as types
from mcp.server.fastmcp import FastMCP
from service.gmail_service import GmailService

EMAIL_ADMIN_PROMPTS = """You are an email administrator. 
You can draft, edit, read, trash, open, and send emails.
You've been given access to a specific gmail account. 
You have the following tools available:
- Send an email (send-email)
- Create a draft email (create-draft)
- List draft emails (list-drafts)
- Retrieve unread emails (get-unread-emails)
- Read email content (read-email)
- Trash email (trash-email)
- Open email in browser (open-email)
- List all labels (list-labels)
- Create a new label (create-label)
- Apply a label to an email (apply-label)
- Remove a label from an email (remove-label)
- Rename a label (rename-label)
- Delete a label (delete-label)
- Search for emails with a specific label (search-by-label)
- Search for emails using Gmail's search syntax (search-emails)
- List all email filters (list-filters)
- Get details of a specific filter (get-filter)
- Create a new email filter (create-filter)
- Delete a filter (delete-filter)
- Create a new folder (create-folder)
- Move an email to a folder (move-to-folder)
- List all folders (list-folders)
- Archive an email (archive-email)
- Batch archive emails (batch-archive)
- List archived emails (list-archived)
- Restore an email to inbox (restore-to-inbox)

Never send an email draft or trash an email unless the user confirms first. 
Always ask for approval if not already given.
"""
mcp = FastMCP(
    name="Gmail Assistant",
    host="0.0.0.0",
    port=8050,
    stateless_http=True,
)

# Define available prompts for developer understanding
PROMPTS = {
    "manage-email": types.Prompt(
        name="manage-email",
        description="Act like an email administrator",
        arguments=None,
    ),
    "draft-email": types.Prompt(
        name="draft-email",
        description="Draft an email with cotent and recipient",
        arguments=[
            types.PromptArgument(
                name="content", description="What the email is about", required=True
            ),
            types.PromptArgument(
                name="recipient",
                description="Who should the email be addressed to",
                required=True,
            ),
            types.PromptArgument(
                name="recipient_email",
                description="Recipient's email address",
                required=True,
            ),
        ],
    ),
    "edit-draft": types.Prompt(
        name="edit-draft",
        description="Edit the existing email draft",
        arguments=[
            types.PromptArgument(
                name="changes",
                description="What changes should be made to the draft",
                required=True,
            ),
            types.PromptArgument(
                name="current_draft",
                description="The current draft to edit",
                required=True,
            ),
        ],
    ),
    "manage-labels": types.Prompt(
        name="manage-labels",
        description="Manage email labels for organization",
        arguments=[
            types.PromptArgument(
                name="action",
                description="What action to take with labels (create, list, apply, remove, search)",
                required=True,
            ),
        ],
    ),
    "manage-filters": types.Prompt(
        name="manage-filters",
        description="Manage email filters for automation",
        arguments=[
            types.PromptArgument(
                name="action",
                description="What action to take with filters (create, list, view, delete)",
                required=True,
            ),
        ],
    ),
    "search-emails": types.Prompt(
        name="search-emails",
        description="Search for emails using Gmail's search syntax",
        arguments=[
            types.PromptArgument(
                name="query", description="What to search for in emails", required=True
            ),
        ],
    ),
    "manage-folders": types.Prompt(
        name="manage-folders",
        description="Manage email folders for organization",
        arguments=[
            types.PromptArgument(
                name="action",
                description="What action to take with folders (create, list, move)",
                required=True,
            ),
        ],
    ),
    "manage-archive": types.Prompt(
        name="manage-archive",
        description="Manage archived emails",
        arguments=[
            types.PromptArgument(
                name="action",
                description="What action to take with archives (archive, batch-archive, list, restore)",
                required=True,
            ),
        ],
    ),
}


@mcp.prompt("manage-email")
def manage_email_prompt(arguments=None):
    return types.GetPromptResult(
        messages=[
            types.PromptMessage(
                role="user",
                content=types.TextContent(
                    type="text",
                    text=EMAIL_ADMIN_PROMPTS,
                ),
            )
        ]
    )


@mcp.prompt("draft-email")
def draft_email_prompt(arguments):
    content = arguments.get("content", "")
    recipient = arguments.get("recipient", "")
    recipient_email = arguments.get("recipient_email", "")
    # First message asks the LLM to create the draft
    return types.GetPromptResult(
        messages=[
            types.PromptMessage(
                role="user",
                content=types.TextContent(
                    type="text",
                    text=f"""Please draft an email about {content} for {recipient} ({recipient_email}).
                    Include a subject line starting with 'Subject:' on the first line.
                    Do not send the email yet, just draft it and ask the user for their thoughts.""",
                ),
            )
        ]
    )


@mcp.prompt("edit-draft")
def edit_draft_prompt(arguments):
    changes = arguments.get("changes", "")
    current_draft = arguments.get("current_draft", "")
    # Edit existing draft based on requested changes
    return types.GetPromptResult(
        messages=[
            types.PromptMessage(
                role="user",
                content=types.TextContent(
                    type="text",
                    text=f"""Please revise the current email draft:
                    {current_draft}
                    
                    Requested changes:
                    {changes}
                    
                    Please provide the updated draft.""",
                ),
            )
        ]
    )


@mcp.prompt("manage-labels")
def manage_labels_prompt(arguments):
    action = arguments.get("action", "")
    return types.GetPromptResult(
        messages=[
            types.PromptMessage(
                role="user",
                content=types.TextContent(
                    type="text",
                    text=f"""I need help with managing my email labels. Specifically, I want to {action}.

Here are the tools you can use for label management:
- list-labels: Lists all existing labels in my Gmail account
- create-label: Creates a new label with a specified name
- apply-label: Applies a label to a specific email
- remove-label: Removes a label from a specific email
- rename-label: Renames an existing label
- delete-label: Permanently deletes a label
- search-by-label: Finds all emails with a specific label

Please help me {action} by using the appropriate tools. If you need to list labels first to get label IDs, please do so.""",
                ),
            )
        ]
    )


@mcp.prompt("manage-filters")
def manage_filters_prompt(arguments):
    action = arguments.get("action", "")
    # Guide the LLM on how to manage filters
    return types.GetPromptResult(
        messages=[
            types.PromptMessage(
                role="user",
                content=types.TextContent(
                    type="text",
                    text=f"""I need help with managing my email filters. Specifically, I want to {action}.

Here are the tools you can use for filter management:
- list-filters: Lists all existing filters in my Gmail account
- get-filter: Gets details of a specific filter
- create-filter: Creates a new filter
- delete-filter: Deletes a specific filter

Please help me {action} by using the appropriate tools. If you need to list filters first to get filter IDs, please do so.""",
                ),
            ),
        ]
    )


@mcp.prompt("search-emails")
def search_emails_prompt(arguments):
    query = arguments.get("query", "")
    # Guide the LLM on how to search emails
    return types.GetPromptResult(
        messages=[
            types.PromptMessage(
                role="user",
                content=types.TextContent(
                    type="text",
                    text=f"""I need to search through my emails for: {query}

Here are the tools you can use for searching emails:
- search-emails: Searches all emails using Gmail's search syntax
- get-unread-emails: Gets only unread emails from the inbox

Please help me find emails matching my search criteria. You can use Gmail's search syntax for advanced searches:
- from:sender - Emails from a specific sender
- to:recipient - Emails to a specific recipient
- subject:text - Emails with specific text in the subject
- has:attachment - Emails with attachments
- after:YYYY/MM/DD - Emails after a specific date
- before:YYYY/MM/DD - Emails before a specific date
- is:important - Important emails
- label:name - Emails with a specific label

Please search for emails matching: {query}""",
                ),
            )
        ]
    )


@mcp.prompt("manage-folders")
def manage_folders_prompt(arguments):
    action = arguments.get("action", "")
    # Guide the LLM on how to manage folders
    return types.GetPromptResult(
        messages=[
            types.PromptMessage(
                role="user",
                content=types.TextContent(
                    type="text",
                    text=f"""I need help with managing my email folders. Specifically, I want to {action}.

Here are the tools you can use for folder management:
- list-folders: Lists all existing folders in my Gmail account
- create-folder: Creates a new folder with a specified name
- move-to-folder: Moves an email to a specific folder (removes it from inbox)

Please help me {action} by using the appropriate tools. If you need to list folders first to get folder IDs, please do so.

Note: In Gmail, folders are implemented as labels with special handling. When you move an email to a folder, it applies the folder's label and removes the email from the inbox.""",
                ),
            )
        ]
    )


@mcp.prompt("manage-archive")
def manage_archive_prompt(arguments):
    action = arguments.get("action", "")
    return types.GetPromptResult(
        messages=[
            types.PromptMessage(
                role="user",
                content=types.TextContent(
                    type="text",
                    text=f"""I need help with managing my email archives. Specifically, I want to {action}.

Here are the tools you can use for archive management:
- archive-email: Archives a single email (removes from inbox without deleting)
- batch-archive: Archives multiple emails matching a search query
- list-archived: Lists emails that have been archived
- restore-to-inbox: Restores an archived email back to the inbox

Please help me {action} by using the appropriate tools.

For batch archiving, you can use Gmail's search syntax to find emails to archive:
- from:sender - Emails from a specific sender
- older_than:30d - Emails older than 30 days
- has:attachment - Emails with attachments
- subject:text - Emails with specific text in the subject
- before:YYYY/MM/DD - Emails before a specific date

Note: Archiving in Gmail means removing the email from your inbox while keeping it accessible in "All Mail". It's a great way to declutter your inbox without losing any emails.""",
                ),
            )
        ]
    )


@mcp.tool()
async def send_email_tool(recipient_id: str, subject: str, message: str):
    """
    description="Send an email to a recipient. Do not use if user only asked to draft email. Drafts must be approved before sending."

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

    gmail_service = GmailService(
        creds_file_path="D:\\Agentic AI\\MCP\\cred\\client_secret_979296281541-k7n60e6i7kcq1hijr30umufmis1auhgl.apps.googleusercontent.com.json",
        token_path="D:\\Agentic AI\\MCP\\cred\\token.json",
    )
    send_response = await gmail_service.send_email(recipient_id, subject, message)
    return send_response


@mcp.tool()
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

    gmail_service = GmailService(
        creds_file_path="D:\\Agentic AI\\MCP\\cred\\client_secret_979296281541-k7n60e6i7kcq1hijr30umufmis1auhgl.apps.googleusercontent.com.json",
        token_path="D:\\Agentic AI\\MCP\\cred\\token.json",
    )
    email_content = await gmail_service.open_email(email_id)
    return email_content


@mcp.tool()
async def get_unread_emails_tool(date=10):
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
    # Convert string to int if needed (some LLMs pass strings)
    if isinstance(date, str):
        date = int(date)

    gmail_service = GmailService(
        creds_file_path="D:\\Agentic AI\\MCP\\cred\\client_secret_979296281541-k7n60e6i7kcq1hijr30umufmis1auhgl.apps.googleusercontent.com.json",
        token_path="D:\\Agentic AI\\MCP\\cred\\token.json",
    )
    unread_emails = await gmail_service.get_unread_emails(date=date)
    return unread_emails


@mcp.tool()
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

    gmail_service = GmailService(
        creds_file_path="D:\\Agentic AI\\MCP\\cred\\client_secret_979296281541-k7n60e6i7kcq1hijr30umufmis1auhgl.apps.googleusercontent.com.json",
        token_path="D:\\Agentic AI\\MCP\\cred\\token.json",
    )
    email_content = await gmail_service.read_email(email_id)
    return email_content


@mcp.tool()
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

    gmail_service = GmailService(
        creds_file_path="D:\\Agentic AI\\MCP\\cred\\client_secret_979296281541-k7n60e6i7kcq1hijr30umufmis1auhgl.apps.googleusercontent.com.json",
        token_path="D:\\Agentic AI\\MCP\\cred\\token.json",
    )
    trash_response = await gmail_service.trash_email(email_id)
    return trash_response


@mcp.tool()
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

    gmail_service = GmailService(
        creds_file_path="D:\\Agentic AI\\MCP\\cred\\client_secret_979296281541-k7n60e6i7kcq1hijr30umufmis1auhgl.apps.googleusercontent.com.json",
        token_path="D:\\Agentic AI\\MCP\\cred\\token.json",
    )
    mark_response = await gmail_service.mark_email_as_read(email_id)
    return mark_response


@mcp.tool()
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

    gmail_service = GmailService(
        creds_file_path="D:\\Agentic AI\\MCP\\cred\\client_secret_979296281541-k7n60e6i7kcq1hijr30umufmis1auhgl.apps.googleusercontent.com.json",
        token_path="D:\\Agentic AI\\MCP\\cred\\token.json",
    )
    create_draft_response = await gmail_service.create_draft(
        recipient_id, subject, message
    )
    return create_draft_response


@mcp.tool()
async def list_drafts_tool():
    """
    description="List all draft emails in the user's mailbox."

    schema={
        "type": "object",
        "properties": {},
        "required": []
    }
    """

    gmail_service = GmailService(
        creds_file_path="D:\\Agentic AI\\MCP\\cred\\client_secret_979296281541-k7n60e6i7kcq1hijr30umufmis1auhgl.apps.googleusercontent.com.json",
        token_path="D:\\Agentic AI\\MCP\\cred\\token.json",
    )
    drafts_response = await gmail_service.list_drafts()
    return drafts_response


@mcp.tool()
async def list_labels_tool():
    """
    description="List all labels (tags/folders) available in the user's Gmail mailbox."

    schema={
        "type": "object",
        "properties": {},
        "required": []
    }
    """

    gmail_service = GmailService(
        creds_file_path="D:\\Agentic AI\\MCP\\cred\\client_secret_979296281541-k7n60e6i7kcq1hijr30umufmis1auhgl.apps.googleusercontent.com.json",
        token_path="D:\\Agentic AI\\MCP\\cred\\token.json",
    )
    labels_response = await gmail_service.list_labels()
    return labels_response


@mcp.tool()
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

    gmail_service = GmailService(
        creds_file_path="D:\\Agentic AI\\MCP\\cred\\client_secret_979296281541-k7n60e6i7kcq1hijr30umufmis1auhgl.apps.googleusercontent.com.json",
        token_path="D:\\Agentic AI\\MCP\\cred\\token.json",
    )
    create_label_response = await gmail_service.create_label(name)
    return create_label_response


@mcp.tool()
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

    gmail_service = GmailService(
        creds_file_path="D:\\Agentic AI\\MCP\\cred\\client_secret_979296281541-k7n60e6i7kcq1hijr30umufmis1auhgl.apps.googleusercontent.com.json",
        token_path="D:\\Agentic AI\\MCP\\cred\\token.json",
    )
    apply_label_response = await gmail_service.apply_label(email_id, label_id)
    return apply_label_response


@mcp.tool()
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

    gmail_service = GmailService(
        creds_file_path="D:\\Agentic AI\\MCP\\cred\\client_secret_979296281541-k7n60e6i7kcq1hijr30umufmis1auhgl.apps.googleusercontent.com.json",
        token_path="D:\\Agentic AI\\MCP\\cred\\token.json",
    )
    remove_label_response = await gmail_service.remove_label(email_id, label_id)
    return remove_label_response


@mcp.tool()
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

    gmail_service = GmailService(
        creds_file_path="D:\\Agentic AI\\MCP\\cred\\client_secret_979296281541-k7n60e6i7kcq1hijr30umufmis1auhgl.apps.googleusercontent.com.json",
        token_path="D:\\Agentic AI\\MCP\\cred\\token.json",
    )
    search_response = await gmail_service.search_by_label(label_id)
    return search_response


"""This tool is not working with the Gmail API but there is a way using the google.auth"""
# @mcp.tool()
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


@mcp.tool()
async def list_filters_tool():
    """
    description="List all email filters configured in the user's Gmail account."

    schema={
        "type": "object",
        "properties": {},
        "required": []
    }
    """

    gmail_service = GmailService(
        creds_file_path="D:\\Agentic AI\\MCP\\cred\\client_secret_979296281541-k7n60e6i7kcq1hijr30umufmis1auhgl.apps.googleusercontent.com.json",
        token_path="D:\\Agentic AI\\MCP\\cred\\token.json",
    )
    filters_response = await gmail_service.list_filters()
    return filters_response


@mcp.tool()
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

    gmail_service = GmailService(
        creds_file_path="D:\\Agentic AI\\MCP\\cred\\client_secret_979296281541-k7n60e6i7kcq1hijr30umufmis1auhgl.apps.googleusercontent.com.json",
        token_path="D:\\Agentic AI\\MCP\\cred\\token.json",
    )
    filter_response = await gmail_service.get_filter(filter_id)
    return filter_response


@mcp.tool()
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

    gmail_service = GmailService(
        creds_file_path="D:\\Agentic AI\\MCP\\cred\\client_secret_979296281541-k7n60e6i7kcq1hijr30umufmis1auhgl.apps.googleusercontent.com.json",
        token_path="D:\\Agentic AI\\MCP\\cred\\token.json",
    )
    delete_filter_response = await gmail_service.delete_filter(filter_id=filter_id)
    return delete_filter_response


@mcp.tool()
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
    # Convert string to int if needed (some LLMs pass strings)
    if max_results is not None and isinstance(max_results, str):
        max_results = int(max_results)

    gmail_service = GmailService(
        creds_file_path="D:\\Agentic AI\\MCP\\cred\\client_secret_979296281541-k7n60e6i7kcq1hijr30umufmis1auhgl.apps.googleusercontent.com.json",
        token_path="D:\\Agentic AI\\MCP\\cred\\token.json",
    )
    search_response = await gmail_service.search_emails(
        query=query, max_results=max_results
    )
    return search_response


@mcp.tool()
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

    gmail_service = GmailService(
        creds_file_path="D:\\Agentic AI\\MCP\\cred\\client_secret_979296281541-k7n60e6i7kcq1hijr30umufmis1auhgl.apps.googleusercontent.com.json",
        token_path="D:\\Agentic AI\\MCP\\cred\\token.json",
    )
    create_folder_response = await gmail_service.create_folder(name=name)
    return create_folder_response


@mcp.tool()
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

    gmail_service = GmailService(
        creds_file_path="D:\\Agentic AI\\MCP\\cred\\client_secret_979296281541-k7n60e6i7kcq1hijr30umufmis1auhgl.apps.googleusercontent.com.json",
        token_path="D:\\Agentic AI\\MCP\\cred\\token.json",
    )
    move_to_folder_response = await gmail_service.move_to_folder(
        email_id=email_id, folder_id=folder_id
    )
    return move_to_folder_response


@mcp.tool()
async def list_folders_tool():
    """
    description="List all user-created folders in Gmail."

    schema={
        "type": "object",
        "properties": {},
        "required": []
    }
    """

    gmail_service = GmailService(
        creds_file_path="D:\\Agentic AI\\MCP\\cred\\client_secret_979296281541-k7n60e6i7kcq1hijr30umufmis1auhgl.apps.googleusercontent.com.json",
        token_path="D:\\Agentic AI\\MCP\\cred\\token.json",
    )
    folders_response = await gmail_service.list_folders()
    return folders_response


@mcp.tool()
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

    gmail_service = GmailService(
        creds_file_path="D:\\Agentic AI\\MCP\\cred\\client_secret_979296281541-k7n60e6i7kcq1hijr30umufmis1auhgl.apps.googleusercontent.com.json",
        token_path="D:\\Agentic AI\\MCP\\cred\\token.json",
    )
    rename_label_response = await gmail_service.rename_label(label_id, new_name)
    return rename_label_response


@mcp.tool()
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

    gmail_service = GmailService(
        creds_file_path="D:\\Agentic AI\\MCP\\cred\\client_secret_979296281541-k7n60e6i7kcq1hijr30umufmis1auhgl.apps.googleusercontent.com.json",
        token_path="D:\\Agentic AI\\MCP\\cred\\token.json",
    )
    delete_label_response = await gmail_service.delete_label(label_id)
    return delete_label_response


@mcp.tool()
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

    gmail_service = GmailService(
        creds_file_path="D:\\Agentic AI\\MCP\\cred\\client_secret_979296281541-k7n60e6i7kcq1hijr30umufmis1auhgl.apps.googleusercontent.com.json",
        token_path="D:\\Agentic AI\\MCP\\cred\\token.json",
    )
    archive_response = await gmail_service.archive_email(email_id=email_id)
    return archive_response


@mcp.tool()
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
    # Convert string to int if needed (some LLMs pass strings)
    if isinstance(max_emails, str):
        max_emails = int(max_emails)

    gmail_service = GmailService(
        creds_file_path="D:\\Agentic AI\\MCP\\cred\\client_secret_979296281541-k7n60e6i7kcq1hijr30umufmis1auhgl.apps.googleusercontent.com.json",
        token_path="D:\\Agentic AI\\MCP\\cred\\token.json",
    )
    archive_response = await gmail_service.batch_archive(
        query=query, max_emails=max_emails
    )
    return archive_response


@mcp.tool()
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
    # Convert string to int if needed (some LLMs pass strings)
    if isinstance(max_results, str):
        max_results = int(max_results)

    gmail_service = GmailService(
        creds_file_path="D:\\Agentic AI\\MCP\\cred\\client_secret_979296281541-k7n60e6i7kcq1hijr30umufmis1auhgl.apps.googleusercontent.com.json",
        token_path="D:\\Agentic AI\\MCP\\cred\\token.json",
    )
    archived_emails_response = await gmail_service.list_archived(
        max_results=max_results
    )
    return archived_emails_response


@mcp.tool()
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

    gmail_service = GmailService(
        creds_file_path="D:\\Agentic AI\\MCP\\cred\\client_secret_979296281541-k7n60e6i7kcq1hijr30umufmis1auhgl.apps.googleusercontent.com.json",
        token_path="D:\\Agentic AI\\MCP\\cred\\token.json",
    )
    restore_response = await gmail_service.restore_to_inbox(email_id=email_id)
    return restore_response


if __name__ == "__main__":
    mcp.run()
