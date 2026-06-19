import logging

from fastapi import APIRouter, Depends, Request

from ..dependencies import get_session_service
from ..services.session_service import SessionService

router = APIRouter()
logger = logging.getLogger(__name__)


@router.get("/stats", summary="Get overall performance statistics")
async def get_stats(
    request: Request,
    session_svc: SessionService = Depends(get_session_service),
):
    config = request.app.state.config
    stats = await session_svc.get_dashboard_stats(config)
    return stats


@router.get("/sessions", summary="Get session list for the dashboard")
async def get_dashboard_sessions(
    session_svc: SessionService = Depends(get_session_service),
):
    sessions = await session_svc.list_sessions()
    return [
        {
            "session_id": s["session_id"],
            "created_at": s["created_at"],
            "status": s["status"],
            "company_name": s.get("setup", {}).get("company_name"),
            "job_title": s.get("setup", {}).get("job_title"),
            "interview_type": s.get("setup", {}).get("interview_type"),
            "overall_score": s.get("overall_score"),
            "questions_answered": sum(
                1 for q in s.get("questions", []) if q.get("status") in ("answered", "evaluated")
            ),
            "total_questions": len(s.get("questions", [])),
        }
        for s in sessions
    ]
