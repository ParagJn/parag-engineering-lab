import logging
from typing import List

from fastapi import APIRouter, Depends, HTTPException

from ..dependencies import get_session_service
from ..services.session_service import SessionService

router = APIRouter()
logger = logging.getLogger(__name__)


@router.get("/", summary="List all sessions")
async def list_sessions(session_svc: SessionService = Depends(get_session_service)):
    sessions = await session_svc.list_sessions()
    # Return lightweight summaries
    return [
        {
            "session_id": s["session_id"],
            "root_session_id": s.get("root_session_id", s["session_id"]),
            "attempt_number": s.get("attempt_number", 1),
            "created_at": s["created_at"],
            "updated_at": s["updated_at"],
            "status": s["status"],
            "company_name": s.get("setup", {}).get("company_name"),
            "job_title": s.get("setup", {}).get("job_title"),
            "interview_type": s.get("setup", {}).get("interview_type"),
            "years_experience": s.get("setup", {}).get("years_experience"),
            "overall_score": s.get("overall_score"),
            "questions_answered": sum(
                1 for q in s.get("questions", []) if q.get("status") in ("answered", "evaluated")
            ),
            "total_questions": len(s.get("questions", [])),
        }
        for s in sessions
    ]


@router.get("/{session_id}", summary="Get a session by ID")
async def get_session(session_id: str, session_svc: SessionService = Depends(get_session_service)):
    session = await session_svc.get_session(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
    return session


@router.delete("/{session_id}", summary="Delete a session")
async def delete_session(session_id: str, session_svc: SessionService = Depends(get_session_service)):
    deleted = await session_svc.delete_session(session_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Session not found")
    return {"message": "Session deleted successfully"}


@router.get("/{session_id}/chain", summary="Get all attempts in the same interview chain")
async def get_chain(session_id: str, session_svc: SessionService = Depends(get_session_service)):
    chain = await session_svc.get_attempt_chain(session_id)
    if not chain:
        raise HTTPException(status_code=404, detail="Session not found")
    return [
        {
            "session_id": s["session_id"],
            "attempt_number": s.get("attempt_number", 1),
            "created_at": s["created_at"],
            "status": s["status"],
            "overall_score": s.get("overall_score"),
            "questions_answered": sum(
                1 for q in s.get("questions", []) if q.get("status") in ("answered", "evaluated")
            ),
            "total_questions": len(s.get("questions", [])),
        }
        for s in chain
    ]
