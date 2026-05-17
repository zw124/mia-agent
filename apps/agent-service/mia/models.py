from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

MemoryTier = Literal["short_term", "long_term", "permanent"]
MemorySegment = Literal["preferences", "facts", "tasks", "relationships", "projects", "other"]


class SendBlueWebhook(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    account_email: str | None = Field(default=None, alias="accountEmail")
    content: str = ""
    is_outbound: bool = False
    status: str | None = None
    error_code: int | None = None
    error_message: str | None = None
    error_reason: str | None = None
    message_handle: str
    date_sent: str | None = None
    date_updated: str | None = None
    from_number: str | None = None
    number: str
    to_number: str | None = None
    was_downgraded: bool | None = None
    plan: str | None = None
    media_url: str | None = None
    message_type: str | None = None
    group_id: str | None = None
    participants: list[str] = Field(default_factory=list)
    send_style: str | None = None
    opted_out: bool | None = None
    error_detail: str | None = None
    sendblue_number: str | None = None
    service: str | None = None
    group_display_name: str | None = None


class TelegramUser(BaseModel):
    id: int
    is_bot: bool | None = None
    first_name: str | None = None
    username: str | None = None


class TelegramChat(BaseModel):
    id: int
    type: str | None = None
    title: str | None = None
    username: str | None = None
    first_name: str | None = None


class TelegramMessage(BaseModel):
    message_id: int
    date: int | None = None
    chat: TelegramChat
    from_user: TelegramUser | None = Field(default=None, alias="from")
    text: str | None = None
    caption: str | None = None
    voice: dict[str, Any] | None = None
    audio: dict[str, Any] | None = None


class TelegramWebhook(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    update_id: int
    message: TelegramMessage | None = None
    edited_message: TelegramMessage | None = None

class MemoryRecord(BaseModel):
    id: str
    content: str
    tier: MemoryTier
    segment: MemorySegment
    importanceScore: float
    decayRate: float
    status: str
    lastAccessedAt: float | None = None


class CourtProposal(BaseModel):
    memory_ids: list[str]
    action: Literal["delete", "merge", "keep", "manual_review"]
    proposed_content: str | None = None
    reason: str


class AdversarialRound(BaseModel):
    proposal_index: int
    argument: str
    should_keep: bool


class JudgeDecision(BaseModel):
    memory_ids: list[str]
    action: Literal["delete", "merge", "keep", "manual_review"]
    final_content: str | None = None
    reason: str


JsonDict = dict[str, Any]
