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
            "root_session_id": session_id,   # original is its own root
            "attempt_number": 1,
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

    async def create_reattempt(self, source_session_id: str) -> Optional[dict]:
        """
        Create a fresh re-attempt using the same questions as an existing session.
        The new session:
          - reuses all questions (answers/evaluations reset to pending)
          - links to the original via root_session_id
          - gets attempt_number = (max in chain) + 1
          - starts at status 'ready' (no generation needed)
        """
        source = await self.get_session(source_session_id)
        if not source:
            return None

        root_id = source.get("root_session_id", source_session_id)

        # Find the highest attempt number already in this chain
        all_sessions = await self.list_sessions()
        chain = [
            s for s in all_sessions
            if s.get("root_session_id", s["session_id"]) == root_id
        ]
        max_attempt = max((s.get("attempt_number", 1) for s in chain), default=1)

        session_id = str(uuid.uuid4())
        now = datetime.now().isoformat()

        # Copy questions with all progress wiped
        reset_questions = [
            {
                "question_id": q["question_id"],
                "question": q["question"],
                "difficulty": q.get("difficulty", "medium"),
                "rationale": q.get("rationale", ""),
                "assigned_agent": q.get("assigned_agent", "gpt"),
                "answer": None,
                "evaluations": {},
                "consolidated_feedback": None,
                "avg_score": None,
                "status": "pending",
            }
            for q in source.get("questions", [])
            if q.get("status") not in ("generating",)  # skip unfinished placeholders
        ]

        session = {
            "session_id": session_id,
            "root_session_id": root_id,
            "attempt_number": max_attempt + 1,
            "created_at": now,
            "updated_at": now,
            "status": "ready",
            "setup": source["setup"],
            "company_analysis": source.get("company_analysis"),
            "questions": reset_questions,
            "overall_score": None,
            "session_summary": None,
            "error_message": None,
        }
        await self._write(session)
        logger.info(
            "Re-attempt #%d created: %s (root: %s)",
            session["attempt_number"], session_id, root_id,
        )
        return session

    async def get_attempt_chain(self, session_id: str) -> List[dict]:
        """
        Return all sessions in the same attempt chain, sorted by attempt_number.
        Backward-compatible: sessions without root_session_id are treated as their own root.
        """
        session = await self.get_session(session_id)
        if not session:
            return []
        root_id = session.get("root_session_id", session_id)
        all_sessions = await self.list_sessions()
        chain = [
            s for s in all_sessions
            if s.get("root_session_id", s["session_id"]) == root_id
        ]
        return sorted(chain, key=lambda x: x.get("attempt_number", 1))

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

    async def update_question_batch(
        self, session_id: str, indices: list, refined_questions: list
    ) -> Optional[dict]:
        """
        Update a batch of questions (by 0-based list index) with their refined versions
        and set their status to 'pending'.  Thread-safe via the session lock.

        Also advances the session status:
          - First batch done  → 'partial_ready'  (user can start answering Q1-3)
          - Both batches done → 'ready'
        """
        async with self._lock:
            session = await self.get_session(session_id)
            if not session:
                return None
            questions = session.get("questions", [])
            for list_idx, q_data in zip(indices, refined_questions):
                if list_idx < len(questions):
                    questions[list_idx].update(
                        {
                            "question": q_data.get(
                                "question", questions[list_idx].get("question", "")
                            ),
                            "difficulty": q_data.get("difficulty", "medium"),
                            "rationale": q_data.get("rationale", ""),
                            "status": "pending",
                        }
                    )
            # Advance overall session status
            pending_count = sum(1 for q in questions if q["status"] == "pending")
            total = len(questions)
            if pending_count >= total:
                session["status"] = "ready"
            elif pending_count >= 3:
                session["status"] = "partial_ready"
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
