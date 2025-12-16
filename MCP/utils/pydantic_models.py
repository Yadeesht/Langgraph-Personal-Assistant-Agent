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
