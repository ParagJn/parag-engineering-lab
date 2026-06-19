import asyncio
import json
import logging
import uuid
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional

import aiofiles

logger = logging.getLogger(__name__)


class SessionService:
    """
    JSON file-based session persistence.
    Each session is stored as <session_id>.json in the sessions directory.
    """

    def __init__(self, sessions_dir: str):
        self.sessions_dir = Path(sessions_dir)
        self.sessions_dir.mkdir(parents=True, exist_ok=True)
        self._lock = asyncio.Lock()

    def _path(self, session_id: str) -> Path:
        return self.sessions_dir / f"{session_id}.json"

    # ------------------------------------------------------------------
    # CRUD
    # ------------------------------------------------------------------

    async def create_session(self, setup_data: dict) -> dict:
        session_id = str(uuid.uuid4())
        now = datetime.now().isoformat()
        session = {
            "session_id": session_id,
            "created_at": now,
            "updated_at": now,
            "status": "setup",
            "setup": setup_data,
            "company_analysis": None,
            "questions": [],
            "overall_score": None,
            "session_summary": None,
            "error_message": None,
        }
        await self._write(session)
        logger.info("Session created: %s", session_id)
        return session

    async def get_session(self, session_id: str) -> Optional[dict]:
        path = self._path(session_id)
        if not path.exists():
            return None
        async with aiofiles.open(path, "r") as f:
            content = await f.read()
        return json.loads(content)

    async def update_session(self, session_id: str, updates: dict) -> Optional[dict]:
        async with self._lock:
            session = await self.get_session(session_id)
            if session is None:
                return None
            session.update(updates)
            session["updated_at"] = datetime.now().isoformat()
            await self._write(session)
        return session

    async def delete_session(self, session_id: str) -> bool:
        path = self._path(session_id)
        if path.exists():
            path.unlink()
            logger.info("Session deleted: %s", session_id)
            return True
        return False

    async def list_sessions(self) -> List[dict]:
        """Return all sessions sorted by creation time (newest first)."""
        sessions = []
        paths = sorted(
            self.sessions_dir.glob("*.json"),
            key=lambda p: p.stat().st_mtime,
            reverse=True,
        )
        for path in paths:
            try:
                async with aiofiles.open(path, "r") as f:
                    content = await f.read()
                sessions.append(json.loads(content))
            except (json.JSONDecodeError, OSError) as exc:
                logger.warning("Could not read session file %s: %s", path, exc)
        return sessions

    # ------------------------------------------------------------------
    # Question helpers
    # ------------------------------------------------------------------

    async def set_question_answer(
        self, session_id: str, question_id: int, answer: str
    ) -> Optional[dict]:
        """Persist a candidate's answer to a specific question."""
        async with self._lock:
            session = await self.get_session(session_id)
            if session is None:
                return None
            for q in session.get("questions", []):
                if q["question_id"] == question_id:
                    q["answer"] = answer
                    q["status"] = "answered"
                    break
            session["updated_at"] = datetime.now().isoformat()
            if session.get("status") == "ready":
                session["status"] = "in_progress"
            await self._write(session)
        return session

    async def set_question_evaluations(
        self, session_id: str, question_id: int, evaluations: dict
    ) -> Optional[dict]:
        """Store evaluation results from all three agents for one question."""
        async with self._lock:
            session = await self.get_session(session_id)
            if session is None:
                return None
            for q in session.get("questions", []):
                if q["question_id"] == question_id:
                    q["evaluations"] = evaluations
                    scores = [v.get("score", 0) for v in evaluations.values() if isinstance(v, dict)]
                    q["avg_score"] = round(sum(scores) / len(scores), 1) if scores else None
                    q["status"] = "evaluated"
                    break
            session["updated_at"] = datetime.now().isoformat()
            await self._write(session)
        return session

    async def set_consolidated_feedback(
        self, session_id: str, question_id: int, feedback: str
    ) -> Optional[dict]:
        async with self._lock:
            session = await self.get_session(session_id)
            if session is None:
                return None
            for q in session.get("questions", []):
                if q["question_id"] == question_id:
                    q["consolidated_feedback"] = feedback
                    break
            session["updated_at"] = datetime.now().isoformat()
            await self._write(session)
        return session

    # ------------------------------------------------------------------
    # Dashboard stats
    # ------------------------------------------------------------------

    async def get_dashboard_stats(self, cfg: dict) -> dict:
        dashboard_cfg = cfg.get("dashboard", {})
        sessions = await self.list_sessions()
        completed = [s for s in sessions if s.get("status") == "completed"]

        stats: dict = {
            "total_sessions": len(sessions),
            "completed_sessions": len(completed),
            "in_progress_sessions": len([s for s in sessions if s.get("status") == "in_progress"]),
            "average_score": None,
            "score_by_type": {},
            "recent_companies": [],
            "improvement_trend": [],
        }

        if not completed:
            return stats

        all_scores = []
        type_scores: Dict[str, List[float]] = {}
        seen_companies: List[str] = []

        for s in completed:
            score = s.get("overall_score")
            if score is not None:
                all_scores.append(score)
                itype = s.get("setup", {}).get("interview_type", "unknown")
                type_scores.setdefault(itype, []).append(score)

            company = s.get("setup", {}).get("company_name", "")
            if company and company not in seen_companies:
                seen_companies.append(company)

        if all_scores:
            stats["average_score"] = round(sum(all_scores) / len(all_scores), 1)

        for itype, scores in type_scores.items():
            stats["score_by_type"][itype] = {
                "average": round(sum(scores) / len(scores), 1),
                "count": len(scores),
            }

        max_companies = dashboard_cfg.get("max_recent_companies", 5)
        stats["recent_companies"] = seen_companies[:max_companies]

        trend_count = dashboard_cfg.get("trend_sessions_count", 10)
        recent = sorted(completed, key=lambda x: x.get("created_at", ""))[-trend_count:]
        stats["improvement_trend"] = [
            {
                "date": s.get("created_at", "")[:10],
                "score": s.get("overall_score"),
                "company": s.get("setup", {}).get("company_name", ""),
                "type": s.get("setup", {}).get("interview_type", ""),
            }
            for s in recent
            if s.get("overall_score") is not None
        ]

        return stats

    # ------------------------------------------------------------------
    # Internal
    # ------------------------------------------------------------------

    async def _write(self, session: dict) -> None:
        path = self._path(session["session_id"])
        async with aiofiles.open(path, "w") as f:
            await f.write(json.dumps(session, indent=2))
