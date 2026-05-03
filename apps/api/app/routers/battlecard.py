import asyncio
import uuid

from fastapi import APIRouter, BackgroundTasks, HTTPException, Response
from fastapi.responses import FileResponse

from app.db.database import create_run, delete_run, get_run, list_recent_runs, reset_run
from app.models.schemas import (
    BattlecardRunResponse,
    GenerateBattlecardRequest,
    GenerateBattlecardResponse,
)
from app.services.pipeline import pipeline_service
from app.services.pdf_export import generate_pdf
from app.db.database import update_run


router = APIRouter(prefix="/api/battlecard", tags=["battlecard"])


def _run_pipeline_sync(run_id: str, competitor_name: str, force_refresh: bool = False, mode: str = "live") -> None:
    asyncio.run(pipeline_service.run(run_id, competitor_name, force_refresh=force_refresh, mode=mode))


def _regenerate_pdf_sync(run_id: str) -> None:
    run = get_run(run_id)
    if run is None:
        return
    markdown = run.get("markdown")
    competitor = run.get("competitor_name") or "battlecard"
    if not markdown:
        return
    pdf_path = generate_pdf(markdown, run_id, competitor)
    if pdf_path:
        update_run(run_id, pdf_path=pdf_path)


def _confidence_from_run(run: dict) -> dict[str, object]:
    payload = run.get("json_output") or {}
    summary = payload.get("summary") if isinstance(payload, dict) else {}
    if not isinstance(summary, dict):
        summary = {}

    return {
        "confidence_score": summary.get("confidence_score"),
        "confidence_label": summary.get("confidence_label"),
        "confidence_factors": summary.get("confidence_factors"),
        "confidence_explanation": summary.get("confidence_explanation"),
    }


@router.post("/generate", response_model=GenerateBattlecardResponse)
def generate_battlecard(request: GenerateBattlecardRequest, background_tasks: BackgroundTasks) -> GenerateBattlecardResponse:
    competitor = request.competitor_name.strip()
    if len(competitor) < 2:
        raise HTTPException(status_code=400, detail="Invalid competitor name")

    run_id = str(uuid.uuid4())
    create_run(run_id, competitor)
    background_tasks.add_task(_run_pipeline_sync, run_id, competitor, False, request.mode)
    return GenerateBattlecardResponse(run_id=run_id, status="queued")


@router.get("/{run_id}", response_model=BattlecardRunResponse)
def get_battlecard(run_id: str) -> BattlecardRunResponse:
    run = get_run(run_id)
    if run is None:
        raise HTTPException(status_code=404, detail="Run not found")

    confidence = _confidence_from_run(run)

    return BattlecardRunResponse(
        id=run["id"],
        competitor_name=run["competitor_name"],
        canonical_domain=run.get("canonical_domain"),
        status=run["status"],
        error_message=run.get("error_message"),
        markdown=run.get("markdown"),
        battlecard=run.get("json_output") or {},
        sources=run.get("sources_json") or [],
        snippets=run.get("snippets_json") or [],
        events=run.get("events") or [],
        pdf_path=run.get("pdf_path"),
        confidence_score=confidence["confidence_score"],
        confidence_label=confidence["confidence_label"],
        confidence_factors=confidence["confidence_factors"],
        confidence_explanation=confidence["confidence_explanation"],
        created_at=run["created_at"],
        updated_at=run["updated_at"],
    )


@router.get("/{run_id}/pdf")
def get_battlecard_pdf(run_id: str) -> FileResponse:
    run = get_run(run_id)
    if run is None:
        raise HTTPException(status_code=404, detail="Run not found")
    if not run.get("pdf_path"):
        raise HTTPException(status_code=404, detail="PDF not available")

    pdf_path = run["pdf_path"]
    filename = f"battlecard-{run['competitor_name'].replace(' ', '-').lower()}.pdf"
    return FileResponse(pdf_path, media_type="application/pdf", filename=filename)


@router.post("/{run_id}/pdf/regenerate")
def regenerate_battlecard_pdf(run_id: str, background_tasks: BackgroundTasks) -> dict:
    run = get_run(run_id)
    if run is None:
        raise HTTPException(status_code=404, detail="Run not found")
    if not run.get("markdown"):
        raise HTTPException(status_code=400, detail="No markdown available for run")

    background_tasks.add_task(_regenerate_pdf_sync, run_id)
    return {"run_id": run_id, "status": "regenerating"}


@router.post("/{run_id}/refresh")
def refresh_battlecard(run_id: str, background_tasks: BackgroundTasks) -> dict:
    run = get_run(run_id)
    if run is None:
        raise HTTPException(status_code=404, detail="Run not found")

    reset_run(run_id)
    background_tasks.add_task(_run_pipeline_sync, run_id, run["competitor_name"], True)
    return {"run_id": run_id, "status": "queued"}


@router.delete("/{run_id}", status_code=204)
def remove_battlecard(run_id: str) -> Response:
    run = get_run(run_id)
    if run is None:
        raise HTTPException(status_code=404, detail="Run not found")

    delete_run(run_id)
    return Response(status_code=204)


@router.get("/recent/list")
def recent_runs() -> dict:
    return {"runs": list_recent_runs(limit=10)}
