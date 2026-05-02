from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


class GenerateBattlecardRequest(BaseModel):
    competitor_name: str = Field(min_length=2, max_length=120)


class GenerateBattlecardResponse(BaseModel):
    run_id: str
    status: str


class PipelineEvent(BaseModel):
    stage: str
    message: str
    progress: int
    created_at: datetime


class SourceItem(BaseModel):
    id: str
    url: str
    title: str
    source_type: str
    published_at: str | None = None
    score: float = 0.0


class BattlecardRunResponse(BaseModel):
    id: str
    competitor_name: str
    canonical_domain: str | None = None
    status: str
    error_message: str | None = None
    markdown: str | None = None
    battlecard: dict[str, Any] | None = None
    sources: list[dict[str, Any]] = []
    snippets: list[dict[str, Any]] = []
    events: list[dict[str, Any]] = []
    pdf_path: str | None = None
    created_at: datetime
    updated_at: datetime


class HealthResponse(BaseModel):
    status: str
    time: datetime
