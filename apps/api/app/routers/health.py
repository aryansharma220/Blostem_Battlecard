from datetime import datetime, timezone

from fastapi import APIRouter

from app.models.schemas import HealthResponse


router = APIRouter(prefix="/api", tags=["health"])


@router.get("/health", response_model=HealthResponse)
def health() -> HealthResponse:
    return HealthResponse(status="ok", time=datetime.now(timezone.utc))
