from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from app.models.report import ReportStatus, ReportTargetType


class ReportCreateRequest(BaseModel):
    target_type: ReportTargetType
    target_id: int = Field(gt=0)
    reason_code: str = Field(min_length=2, max_length=50)
    reason_text: str | None = Field(default=None, max_length=2000)


class ReportResolveRequest(BaseModel):
    action: str = Field(min_length=4, max_length=20)
    resolution_note: str | None = Field(default=None, max_length=2000)
    moderation_action: str | None = Field(default=None, max_length=40)


class ReportAttachmentItem(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    report_id: int
    file_name: str
    original_name: str
    mime_type: str
    file_size: int
    file_path: str
    created_at: datetime


class ReportResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    reporter_user_id: int
    target_type: ReportTargetType
    target_id: int
    target_conversation_id: int | None
    target_listing_id: int | None = None
    reason_code: str
    reason_text: str | None
    attachments: list[ReportAttachmentItem]
    status: ReportStatus
    resolution_note: str | None
    reviewed_by_admin_id: int | None
    created_at: datetime
    reviewed_at: datetime | None


class ReportListResponse(BaseModel):
    items: list[ReportResponse]
    page: int
    page_size: int
    total_items: int
    total_pages: int
