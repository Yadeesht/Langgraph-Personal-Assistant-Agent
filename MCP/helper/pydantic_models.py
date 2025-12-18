"""Pydantic models for Gmail API tools"""

from typing import Optional, List
from pydantic import BaseModel, EmailStr, Field, validator


class SendEmailRequest(BaseModel):
    """Send email request"""

    recipient_id: EmailStr = Field(
        ..., description="Recipient email", pattern=r"[^@]+@[^@]+\.[^@]+"
    )
    subject: str = Field(..., min_length=1, description="Email subject")
    message: str = Field(..., min_length=1, description="Email body")


class SendEmailResponse(BaseModel):
    """Send email response"""

    success: bool
    message_id: Optional[str] = None
    error: Optional[str] = None


class EmailAddress(BaseModel):
    """Email address with validation"""

    email: EmailStr


class EmailResponse(BaseModel):
    """Email response"""

    success: bool
    error: Optional[str] = None


class UnreadEmailsRequest(BaseModel):
    """Get unread emails request"""

    date: int = Field(10, ge=1, le=365, description="Days to look back")
    max_results: int = Field(20, ge=1, le=500, description="Max results")


class EmailMetadata(BaseModel):
    """Email metadata structure"""

    id: str
    thread_id: str
    snippet: str
    labels: List[str]
    size: int
    internal_date: Optional[str]
    subject: str
    from_: str = Field(..., alias="from")
    date: str
    to: str

    class Config:
        populate_by_name = True


class UnreadEmailsResponse(BaseModel):
    """Unread emails response"""

    count: int
    emails: List[EmailMetadata]


class LabelRequest(BaseModel):
    """Create/rename label request"""

    name: str = Field(..., min_length=1, max_length=225, description="Label name")

    @validator("name")
    def validate_label_name(cls, v):
        if "/" in v and v.count("/") > 5:
            raise ValueError("Label name cannot have more than 5 levels")
        return v


class LabelResponse(BaseModel):
    """Label operation response"""

    success: bool
    label_id: Optional[str] = None
    name: Optional[str] = None
    error: Optional[str] = None


class LabelInfo(BaseModel):
    """Label information"""

    id: str
    name: str
    type: str


class ListLabelsResponse(BaseModel):
    """List labels response"""

    count: int
    labels: List[LabelInfo]
    error: Optional[str] = None


class ApplyLabelRequest(BaseModel):
    """Apply/remove label request"""

    email_id: str = Field(..., description="Message ID")
    label_id: str = Field(..., description="Label ID")


class DraftRequest(BaseModel):
    """Create draft request"""

    recipient_id: EmailStr
    subject: str = Field(..., min_length=1)
    message: str = Field(..., min_length=1)


class DraftInfo(BaseModel):
    """Draft information"""

    id: str
    subject: str
    to: str


class ListDraftsResponse(BaseModel):
    """List drafts response"""

    count: int
    drafts: List[DraftInfo]
    error: Optional[str] = None


class BatchArchiveRequest(BaseModel):
    """Batch archive request"""

    query: str = Field(..., description="Gmail search query")
    max_emails: int = Field(100, ge=1, le=500, description="Max emails to archive")


class BatchArchiveResponse(BaseModel):
    """Batch archive response"""

    success: bool
    archived_count: int = 0
    total_found: int = 0
    message: Optional[str] = None
    error: Optional[str] = None


class StandardResponse(BaseModel):
    """Standard success/error response"""

    success: bool
    error: Optional[str] = None


class EmailIdRequest(BaseModel):
    """Email ID request for single email operations"""

    email_id: str = Field(..., min_length=1, description="Gmail message ID")


class ReadEmailResponse(BaseModel):
    """Read email response"""

    content: str
    subject: str
    from_: str = Field(..., alias="from")
    to: str
    date: str
    error: Optional[str] = None

    class Config:
        populate_by_name = True


class DraftResponse(BaseModel):
    """Draft creation response"""

    success: bool
    draft_id: Optional[str] = None
    error: Optional[str] = None


class FilterInfo(
    BaseModel
):  # they are not directly used but use in other filers classes
    """Filter information structure"""

    id: str
    criteria: dict
    action: dict


class ListFiltersResponse(BaseModel):
    """List filters response"""

    count: int
    filters: List[FilterInfo]
    error: Optional[str] = None


class FilterIdRequest(BaseModel):
    """Filter ID request"""

    filter_id: str = Field(..., min_length=1, description="Filter ID")


class SearchEmailsRequest(BaseModel):
    """Search emails request"""

    query: str = Field(..., min_length=1, description="Gmail search query")
    max_results: Optional[int] = Field(None, ge=1, le=500, description="Max results")


class SearchEmailsResponse(BaseModel):
    """Search emails response"""

    count: int
    emails: List[dict]
    error: Optional[str] = None


class FolderRequest(BaseModel):
    """Create folder request"""

    name: str = Field(..., min_length=1, max_length=225, description="Folder name")


class FolderResponse(BaseModel):
    """Folder operation response"""

    success: bool
    folder_id: Optional[str] = None
    name: Optional[str] = None
    error: Optional[str] = None


class MoveToFolderRequest(BaseModel):
    """Move email to folder request"""

    email_id: str = Field(..., min_length=1, description="Gmail message ID")
    folder_id: str = Field(..., min_length=1, description="Folder/Label ID")


class FolderInfo(BaseModel):
    """Folder information"""

    id: str
    name: str


class ListFoldersResponse(BaseModel):
    """List folders response"""

    count: int
    folders: List[FolderInfo]
    error: Optional[str] = None


class RenameLabelRequest(BaseModel):
    """Rename label request"""

    label_id: str = Field(..., min_length=1, description="Label ID to rename")
    new_name: str = Field(
        ..., min_length=1, max_length=225, description="New label name"
    )

    @validator("new_name")
    def validate_label_name(cls, v):
        if "/" in v and v.count("/") > 5:
            raise ValueError("Label name cannot have more than 5 levels")
        return v


class ListArchivedRequest(BaseModel):
    """List archived emails request"""

    max_results: int = Field(100, ge=1, le=500, description="Max results")


class SearchByLabelRequest(BaseModel):
    """Search by label request"""

    label_id: str = Field(..., min_length=1, description="Label ID to search")


class SearchByLabelResponse(BaseModel):
    """Search by label response"""

    count: int
    messages: List[dict]
    error: Optional[str] = None


# ============================Google Chat Models=========================


class ListSpacesRequest(BaseModel):
    """List Google Chat spaces request"""

    page_size: int = Field(100, ge=1, le=1000, description="Max number of spaces")
    space_type: str = Field(
        "all",
        description="Type of spaces: 'all', 'room', or 'dm'",
        pattern="^(all|room|dm)$",
    )


class SpaceInfo(BaseModel):
    """Google Chat space information"""

    name: str
    display_name: str
    space_type: str


class ListSpacesResponse(BaseModel):
    """List spaces response"""

    count: int
    spaces: List[SpaceInfo]
    space_type_filter: str
    error: Optional[str] = None


class GetMessagesRequest(BaseModel):
    """Get messages from a space request"""

    space_id: str = Field(..., min_length=1, description="Space ID (spaces/...)")
    page_size: int = Field(50, ge=1, le=1000, description="Max number of messages")
    order_by: str = Field(
        "createTime desc",
        description="Sort order for messages",
        pattern="^createTime (asc|desc)$",
    )


class MessageInfo(BaseModel):
    """Google Chat message information"""

    name: str
    sender: str
    create_time: str
    text: str


class GetMessagesResponse(BaseModel):
    """Get messages response"""

    count: int
    space_name: str
    space_id: str
    messages: List[MessageInfo]
    error: Optional[str] = None


class SendMessageRequest(BaseModel):
    """Send message to a space request"""

    space_id: str = Field(..., min_length=1, description="Space ID (spaces/...)")
    message_text: str = Field(
        ..., min_length=1, max_length=4096, description="Message text content"
    )
    thread_key: Optional[str] = Field(
        None, description="Optional thread key for replies"
    )


class SendMessageResponse(BaseModel):
    """Send message response"""

    success: bool
    message_id: Optional[str] = None
    space_id: Optional[str] = None
    thread_id: Optional[str] = None
    error: Optional[str] = None


class SearchMessagesRequest(BaseModel):
    """Search messages request"""

    query: str = Field(..., min_length=1, description="Search query text")
    space_id: Optional[str] = Field(
        None, description="Optional space ID to limit search"
    )
    page_size: int = Field(25, ge=1, le=100, description="Max results per space")


class SearchMessageInfo(BaseModel):
    """Search result message information"""

    sender: str
    create_time: str
    text: str
    space_name: str


class SearchMessagesResponse(BaseModel):
    """Search messages response"""

    count: int
    query: str
    context: str
    messages: List[SearchMessageInfo]
    error: Optional[str] = None


# Google Calendar Models


class CalendarInfo(BaseModel):
    """Calendar information"""

    id: str
    summary: str
    description: Optional[str] = None
    timeZone: str
    accessRole: str
    primary: bool = False


class ListCalendarsResponse(BaseModel):
    """List calendars response"""

    status: str
    count: int
    calendars: List[CalendarInfo]
    error: Optional[str] = None


class ReminderItem(BaseModel):
    """Calendar reminder item"""

    method: str = Field(..., pattern="^(popup|email)$", description="Reminder method")
    minutes: int = Field(..., ge=0, le=40320, description="Minutes before event")


class GetEventsRequest(BaseModel):
    """Get events request"""

    calendar_id: str = Field("primary", min_length=1, description="Calendar ID")
    event_id: Optional[str] = Field(None, description="Specific event ID")
    time_min: Optional[str] = Field(None, description="Start time (RFC3339)")
    time_max: Optional[str] = Field(None, description="End time (RFC3339)")
    max_results: int = Field(25, ge=1, le=2500, description="Max number of events")
    query: Optional[str] = Field(None, description="Search query")
    detailed: bool = Field(False, description="Return detailed information")
    include_attachments: bool = Field(False, description="Include attachment info")


class GetEventsResponse(BaseModel):
    """Get events response"""

    status: str
    message: str
    event_id: Optional[str] = None
    error: Optional[str] = None


class CreateEventRequest(BaseModel):
    """Create event request"""

    summary: str = Field(..., min_length=1, max_length=1024, description="Event title")
    start_time: str = Field(..., min_length=1, description="Start time in IST")
    end_time: str = Field(..., min_length=1, description="End time in IST")
    calendar_id: str = Field("primary", min_length=1, description="Calendar ID")
    description: Optional[str] = Field(
        None, max_length=8192, description="Event description"
    )
    location: Optional[str] = Field(None, max_length=1024, description="Event location")
    attendees: Optional[List[str]] = Field(None, description="Attendee emails")
    attachments: Optional[List[str]] = Field(None, description="Drive file URLs/IDs")
    add_google_meet: bool = Field(False, description="Add Google Meet link")
    reminders: Optional[List[ReminderItem]] = Field(
        None, max_items=5, description="Custom reminders"
    )
    use_default_reminders: bool = Field(True, description="Use default reminders")
    transparency: Optional[str] = Field(
        None, pattern="^(opaque|transparent)$", description="Busy/free status"
    )

    @validator("attendees")
    def validate_attendees(cls, v):
        if v and len(v) > 200:
            raise ValueError("Maximum 200 attendees allowed")
        return v


class CreateEventResponse(BaseModel):
    """Create event response"""

    status: str
    message: str
    error: Optional[str] = None


class ModifyEventRequest(BaseModel):
    """Modify event request"""

    event_id: str = Field(..., min_length=1, description="Event ID to modify")
    calendar_id: str = Field("primary", min_length=1, description="Calendar ID")
    summary: Optional[str] = Field(None, max_length=1024, description="New event title")
    start_time: Optional[str] = Field(None, description="New start time in IST")
    end_time: Optional[str] = Field(None, description="New end time in IST")
    description: Optional[str] = Field(
        None, max_length=8192, description="New description"
    )
    location: Optional[str] = Field(None, max_length=1024, description="New location")
    attendees: Optional[List[str]] = Field(None, description="New attendee emails")
    add_google_meet: Optional[bool] = Field(None, description="Add/remove Google Meet")
    reminders: Optional[List[ReminderItem]] = Field(
        None, max_items=5, description="New reminders"
    )
    use_default_reminders: Optional[bool] = Field(
        None, description="Use default reminders"
    )
    transparency: Optional[str] = Field(
        None, pattern="^(opaque|transparent)$", description="Busy/free status"
    )

    @validator("attendees")
    def validate_attendees(cls, v):
        if v and len(v) > 200:
            raise ValueError("Maximum 200 attendees allowed")
        return v


class ModifyEventResponse(BaseModel):
    """Modify event response"""

    status: str
    message: str
    event_id: str
    error: Optional[str] = None


class DeleteEventRequest(BaseModel):
    """Delete event request"""

    event_id: str = Field(..., min_length=1, description="Event ID to delete")
    calendar_id: str = Field("primary", min_length=1, description="Calendar ID")


class DeleteEventResponse(BaseModel):
    """Delete event response"""

    status: str
    message: str
    event_id: str
    error: Optional[str] = None


# ========================= Google Tasks Models =================================


class TaskListInfo(BaseModel):
    """Task list information"""

    id: str
    title: str
    updated: Optional[str] = None


class ListTaskListsRequest(BaseModel):
    """List task lists request"""

    max_results: int = Field(
        1000, ge=1, le=1000, description="Max number of task lists"
    )
    page_token: Optional[str] = Field(None, description="Token for pagination")


class ListTaskListsResponse(BaseModel):
    """List task lists response"""

    status: str
    count: int
    task_lists: List[TaskListInfo]
    next_page_token: Optional[str] = None
    error: Optional[str] = None


class GetTaskListRequest(BaseModel):
    """Get task list request"""

    task_list_id: str = Field(..., min_length=1, description="Task list ID")


class GetTaskListResponse(BaseModel):
    """Get task list response"""

    status: str
    task_list: Optional[TaskListInfo] = None
    error: Optional[str] = None


class CreateTaskListRequest(BaseModel):
    """Create task list request"""

    title: str = Field(
        ..., min_length=1, max_length=1024, description="Task list title"
    )


class CreateTaskListResponse(BaseModel):
    """Create task list response"""

    status: str
    message: str
    task_list_id: Optional[str] = None
    error: Optional[str] = None


class UpdateTaskListRequest(BaseModel):
    """Update task list request"""

    task_list_id: str = Field(..., min_length=1, description="Task list ID")
    title: str = Field(..., min_length=1, max_length=1024, description="New title")


class UpdateTaskListResponse(BaseModel):
    """Update task list response"""

    status: str
    message: str
    task_list_id: str
    error: Optional[str] = None


class DeleteTaskListRequest(BaseModel):
    """Delete task list request"""

    task_list_id: str = Field(..., min_length=1, description="Task list ID to delete")


class DeleteTaskListResponse(BaseModel):
    """Delete task list response"""

    status: str
    message: str
    error: Optional[str] = None


class ListTasksRequest(BaseModel):
    """List tasks request"""

    task_list_id: str = Field(..., min_length=1, description="Task list ID")
    max_results: int = Field(20, ge=1, le=10000, description="Max number of tasks")
    page_token: Optional[str] = Field(None, description="Pagination token")
    show_completed: bool = Field(True, description="Include completed tasks")
    show_deleted: bool = Field(False, description="Include deleted tasks")
    show_hidden: bool = Field(False, description="Include hidden tasks")
    show_assigned: bool = Field(False, description="Include assigned tasks")
    completed_max: Optional[str] = Field(
        None, description="Upper bound for completion date"
    )
    completed_min: Optional[str] = Field(
        None, description="Lower bound for completion date"
    )
    due_max: Optional[str] = Field(None, description="Upper bound for due date")
    due_min: Optional[str] = Field(None, description="Lower bound for due date")
    updated_min: Optional[str] = Field(
        None, description="Lower bound for last modification"
    )


class ListTasksResponse(BaseModel):
    """List tasks response"""

    status: str
    message: str
    error: Optional[str] = None


class GetTaskRequest(BaseModel):
    """Get task request"""

    task_list_id: str = Field(..., min_length=1, description="Task list ID")
    task_id: str = Field(..., min_length=1, description="Task ID")


class GetTaskResponse(BaseModel):
    """Get task response"""

    status: str
    message: str
    error: Optional[str] = None


class CreateTaskRequest(BaseModel):
    """Create task request"""

    task_list_id: str = Field(..., min_length=1, description="Task list ID")
    title: str = Field(..., min_length=1, max_length=1024, description="Task title")
    notes: Optional[str] = Field(None, max_length=8192, description="Task notes")
    due: Optional[str] = Field(None, description="Due date (RFC 3339)")
    parent: Optional[str] = Field(None, description="Parent task ID for subtasks")
    previous: Optional[str] = Field(None, description="Previous sibling task ID")


class CreateTaskResponse(BaseModel):
    """Create task response"""

    status: str
    message: str
    task_id: Optional[str] = None
    error: Optional[str] = None


class UpdateTaskRequest(BaseModel):
    """Update task request"""

    task_list_id: str = Field(..., min_length=1, description="Task list ID")
    task_id: str = Field(..., min_length=1, description="Task ID to update")
    title: Optional[str] = Field(None, max_length=1024, description="New title")
    notes: Optional[str] = Field(None, max_length=8192, description="New notes")
    status: Optional[str] = Field(
        None, pattern="^(needsAction|completed)$", description="Task status"
    )
    due: Optional[str] = Field(None, description="New due date (RFC 3339)")


class UpdateTaskResponse(BaseModel):
    """Update task response"""

    status: str
    message: str
    task_id: str
    error: Optional[str] = None


class DeleteTaskRequest(BaseModel):
    """Delete task request"""

    task_list_id: str = Field(..., min_length=1, description="Task list ID")
    task_id: str = Field(..., min_length=1, description="Task ID to delete")


class DeleteTaskResponse(BaseModel):
    """Delete task response"""

    status: str
    message: str
    error: Optional[str] = None


class MoveTaskRequest(BaseModel):
    """Move task request"""

    task_list_id: str = Field(..., min_length=1, description="Source task list ID")
    task_id: str = Field(..., min_length=1, description="Task ID to move")
    parent: Optional[str] = Field(None, description="New parent task ID")
    previous: Optional[str] = Field(None, description="New previous sibling ID")
    destination_task_list: Optional[str] = Field(
        None, description="Destination task list ID"
    )


class MoveTaskResponse(BaseModel):
    """Move task response"""

    status: str
    message: str
    error: Optional[str] = None


class ClearCompletedTasksRequest(BaseModel):
    """Clear completed tasks request"""

    task_list_id: str = Field(..., min_length=1, description="Task list ID")


class ClearCompletedTasksResponse(BaseModel):
    """Clear completed tasks response"""

    status: str
    message: str
    error: Optional[str] = None


# ========================= Google Slides Models =================================


class CreatePresentationRequest(BaseModel):
    """Create presentation request"""

    title: str = Field(
        "Untitled Presentation",
        min_length=1,
        max_length=255,
        description="Presentation title",
    )


class CreatePresentationResponse(BaseModel):
    """Create presentation response"""

    status: str
    message: str
    presentation_id: Optional[str] = None
    error: Optional[str] = None


class GetPresentationRequest(BaseModel):
    """Get presentation request"""

    presentation_id: str = Field(..., min_length=1, description="Presentation ID")


class GetPresentationResponse(BaseModel):
    """Get presentation response"""

    status: str
    message: str
    error: Optional[str] = None


class BatchUpdateRequest(BaseModel):
    """Batch update request item"""

    # This is a flexible model that accepts any dict structure
    # since Google Slides API accepts various request types
    pass


class BatchUpdatePresentationRequest(BaseModel):
    """Batch update presentation request"""

    presentation_id: str = Field(..., min_length=1, description="Presentation ID")
    requests: List[dict] = Field(
        ..., min_items=1, description="List of update requests"
    )


class BatchUpdatePresentationResponse(BaseModel):
    """Batch update presentation response"""

    status: str
    message: str
    error: Optional[str] = None


class GetPageRequest(BaseModel):
    """Get page request"""

    presentation_id: str = Field(..., min_length=1, description="Presentation ID")
    page_object_id: str = Field(..., min_length=1, description="Page object ID")


class GetPageResponse(BaseModel):
    """Get page response"""

    status: str
    message: str
    error: Optional[str] = None


class GetPageThumbnailRequest(BaseModel):
    """Get page thumbnail request"""

    presentation_id: str = Field(..., min_length=1, description="Presentation ID")
    page_object_id: str = Field(..., min_length=1, description="Page object ID")
    thumbnail_size: str = Field(
        "MEDIUM", pattern="^(LARGE|MEDIUM|SMALL)$", description="Thumbnail size"
    )


class GetPageThumbnailResponse(BaseModel):
    """Get page thumbnail response"""

    status: str
    message: str
    thumbnail_url: Optional[str] = None
    error: Optional[str] = None


# ========================= Google Sheets Models =================================


class ListSpreadsheetsRequest(BaseModel):
    """List spreadsheets request"""

    max_results: int = Field(
        25, ge=1, le=1000, description="Max number of spreadsheets"
    )


class SpreadsheetInfo(BaseModel):
    """Spreadsheet information"""

    id: str
    name: str
    modified_time: str
    web_view_link: Optional[str] = None


class ListSpreadsheetsResponse(BaseModel):
    """List spreadsheets response"""

    status: str
    message: str
    count: int
    spreadsheets: List[SpreadsheetInfo]
    error: Optional[str] = None


class GetSpreadsheetInfoRequest(BaseModel):
    """Get spreadsheet info request"""

    spreadsheet_id: str = Field(..., min_length=1, description="Spreadsheet ID")


class GetSpreadsheetInfoResponse(BaseModel):
    """Get spreadsheet info response"""

    status: str
    message: str
    error: Optional[str] = None


class ReadSheetValuesRequest(BaseModel):
    """Read sheet values request"""

    spreadsheet_id: str = Field(..., min_length=1, description="Spreadsheet ID")
    range_name: str = Field("A1:Z1000", min_length=1, description="A1 notation range")


class ReadSheetValuesResponse(BaseModel):
    """Read sheet values response"""

    status: str
    message: str
    error: Optional[str] = None


class ModifySheetValuesRequest(BaseModel):
    """Modify sheet values request"""

    spreadsheet_id: str = Field(..., min_length=1, description="Spreadsheet ID")
    range_name: str = Field(..., min_length=1, description="A1 notation range")
    values: Optional[str] = Field(None, description="Values as JSON string or list")
    value_input_option: str = Field(
        "USER_ENTERED",
        pattern="^(USER_ENTERED|RAW)$",
        description="How to interpret input",
    )
    clear_values: bool = Field(False, description="Clear values instead of updating")


class ModifySheetValuesResponse(BaseModel):
    """Modify sheet values response"""

    status: str
    message: str
    error: Optional[str] = None


class FormatSheetRangeRequest(BaseModel):
    """Format sheet range request"""

    spreadsheet_id: str = Field(..., min_length=1, description="Spreadsheet ID")
    range_name: str = Field(..., min_length=1, description="A1 notation range")
    background_color: Optional[str] = Field(
        None, description="Background color in hex format (#RRGGBB)"
    )
    text_color: Optional[str] = Field(
        None, description="Text color in hex format (#RRGGBB)"
    )
    number_format_type: Optional[str] = Field(
        None, description="Number format type (NUMBER, CURRENCY, etc.)"
    )
    number_format_pattern: Optional[str] = Field(
        None, description="Number format pattern"
    )


class FormatSheetRangeResponse(BaseModel):
    """Format sheet range response"""

    status: str
    message: str
    error: Optional[str] = None


class AddConditionalFormattingRequest(BaseModel):
    """Add conditional formatting request"""

    spreadsheet_id: str = Field(..., min_length=1, description="Spreadsheet ID")
    range_name: str = Field(..., min_length=1, description="A1 notation range")
    condition_type: str = Field(..., min_length=1, description="Condition type")
    condition_values: Optional[str] = Field(
        None, description="Condition values as JSON string or list"
    )
    background_color: Optional[str] = Field(
        None, description="Background color in hex format (#RRGGBB)"
    )
    text_color: Optional[str] = Field(
        None, description="Text color in hex format (#RRGGBB)"
    )
    rule_index: Optional[int] = Field(None, description="Rule index for insertion")
    gradient_points: Optional[str] = Field(
        None, description="Gradient points as JSON string or list"
    )


class AddConditionalFormattingResponse(BaseModel):
    """Add conditional formatting response"""

    status: str
    message: str
    error: Optional[str] = None


class UpdateConditionalFormattingRequest(BaseModel):
    """Update conditional formatting request"""

    spreadsheet_id: str = Field(..., min_length=1, description="Spreadsheet ID")
    rule_index: int = Field(..., ge=0, description="Rule index to update")
    range_name: Optional[str] = Field(None, description="A1 notation range")
    condition_type: Optional[str] = Field(None, description="Condition type")
    condition_values: Optional[str] = Field(
        None, description="Condition values as JSON string or list"
    )
    background_color: Optional[str] = Field(
        None, description="Background color in hex format (#RRGGBB)"
    )
    text_color: Optional[str] = Field(
        None, description="Text color in hex format (#RRGGBB)"
    )
    sheet_name: Optional[str] = Field(None, description="Sheet name")
    gradient_points: Optional[str] = Field(
        None, description="Gradient points as JSON string or list"
    )


class UpdateConditionalFormattingResponse(BaseModel):
    """Update conditional formatting response"""

    status: str
    message: str
    error: Optional[str] = None


class DeleteConditionalFormattingRequest(BaseModel):
    """Delete conditional formatting request"""

    spreadsheet_id: str = Field(..., min_length=1, description="Spreadsheet ID")
    rule_index: int = Field(..., ge=0, description="Rule index to delete")
    sheet_name: Optional[str] = Field(None, description="Sheet name")


class DeleteConditionalFormattingResponse(BaseModel):
    """Delete conditional formatting response"""

    status: str
    message: str
    error: Optional[str] = None


class CreateSpreadsheetRequest(BaseModel):
    """Create spreadsheet request"""

    title: str = Field(
        ..., min_length=1, max_length=400, description="Spreadsheet title"
    )
    sheet_names: Optional[List[str]] = Field(
        None, description="Optional list of sheet names"
    )


class CreateSpreadsheetResponse(BaseModel):
    """Create spreadsheet response"""

    status: str
    message: str
    spreadsheet_id: Optional[str] = None
    error: Optional[str] = None


class CreateSheetRequest(BaseModel):
    """Create sheet request"""

    spreadsheet_id: str = Field(..., min_length=1, description="Spreadsheet ID")
    sheet_name: str = Field(..., min_length=1, max_length=100, description="Sheet name")


class CreateSheetResponse(BaseModel):
    """Create sheet response"""

    status: str
    message: str
    error: Optional[str] = None


# ========================= Google Forms Models =================================


class CreateFormRequest(BaseModel):
    """Create form request"""

    title: str = Field(..., min_length=1, max_length=255, description="Form title")
    description: Optional[str] = Field(
        None, max_length=4096, description="Form description"
    )
    document_title: Optional[str] = Field(
        None, max_length=255, description="Document title (browser tab)"
    )


class CreateFormResponse(BaseModel):
    """Create form response"""

    status: str
    message: str
    form_id: Optional[str] = None
    edit_url: Optional[str] = None
    responder_url: Optional[str] = None
    error: Optional[str] = None


class GetFormRequest(BaseModel):
    """Get form request"""

    user_google_email: str = Field(..., description="User's Google email")
    form_id: str = Field(..., min_length=1, description="Form ID")


class GetFormResponse(BaseModel):
    """Get form response"""

    status: str
    message: str
    error: Optional[str] = None


class SetPublishSettingsRequest(BaseModel):
    """Set publish settings request"""

    form_id: str = Field(..., min_length=1, description="Form ID")
    publish_as_template: bool = Field(False, description="Publish as template")
    require_authentication: bool = Field(False, description="Require authentication")


class SetPublishSettingsResponse(BaseModel):
    """Set publish settings response"""

    status: str
    message: str
    error: Optional[str] = None


class GetFormResponseRequest(BaseModel):
    """Get form response request"""

    form_id: str = Field(..., min_length=1, description="Form ID")
    response_id: str = Field(..., min_length=1, description="Response ID")


class GetFormResponseResponse(BaseModel):
    """Get form response response"""

    status: str
    message: str
    error: Optional[str] = None


class ListFormResponsesRequest(BaseModel):
    """List form responses request"""

    form_id: str = Field(..., min_length=1, description="Form ID")
    page_size: int = Field(10, ge=1, le=100, description="Maximum number of responses")
    page_token: Optional[str] = Field(None, description="Pagination token")


class ListFormResponsesResponse(BaseModel):
    """List form responses response"""

    status: str
    message: str
    error: Optional[str] = None
    """Create sheet request"""

    spreadsheet_id: str = Field(..., min_length=1, description="Spreadsheet ID")
    sheet_name: str = Field(..., min_length=1, max_length=100, description="Sheet name")


class CreateSheetResponse(BaseModel):
    """Create sheet response"""

    status: str
    message: str
    sheet_id: Optional[int] = None
    error: Optional[str] = None
