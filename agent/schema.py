"""Heal agent output (PRD F6). The submit_diagnosis tool's input schema is built from this."""
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class Diagnosis(BaseModel):
    model_config = ConfigDict(extra="forbid")

    cause_category: Literal["script", "site", "infra", "unknown"]
    cause_detail: Literal["selector_changed", "popup_modal", "login_changed", "slow_page", "site_down", "other"]
    failing_step: str | None
    evidence: list[str] = Field(description="Short strings pointing at DOM or screenshot facts")
    confidence: float = Field(ge=0.0, le=1.0)
    patch: str | None = Field(description="Unified diff against the script, or null")
    touches_data_write: bool
    proposed_decision: Literal["auto_apply", "escalate"]
    reasoning: str = Field(description="Plain text, under 200 words")
