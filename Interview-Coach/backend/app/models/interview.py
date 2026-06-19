from pydantic import BaseModel, Field
from typing import Optional, Dict, Any
from enum import Enum


class InterviewType(str, Enum):
    TECHNICAL = "technical"
    MANAGEMENT = "management"
    BEHAVIORAL = "behavioral"
    SALARY_NEGOTIATION = "salary_negotiation"


class SetupRequest(BaseModel):
    company_name: str = Field(..., min_length=1, max_length=200, description="Target company name")
    job_title: str = Field(..., min_length=1, max_length=200, description="Position being interviewed for")
    job_description: str = Field(..., min_length=10, max_length=5000, description="Job description or key requirements")
    years_experience: int = Field(..., ge=0, le=50, description="Candidate years of experience")
    interview_type: InterviewType = Field(..., description="Type of interview round")


class AnswerRequest(BaseModel):
    answer: str = Field(..., min_length=1, max_length=10000, description="Candidate's answer")


class Evaluation(BaseModel):
    score: int = Field(..., ge=1, le=10)
    feedback: str


class QuestionState(BaseModel):
    question_id: int
    question: str
    difficulty: str
    rationale: str
    assigned_agent: str
    answer: Optional[str] = None
    evaluations: Dict[str, Any] = {}
    consolidated_feedback: Optional[str] = None
    avg_score: Optional[float] = None
    status: str = "pending"  # pending | answered | evaluated


class SessionSetup(BaseModel):
    company_name: str
    job_title: str
    job_description: str
    years_experience: int
    interview_type: str


class Session(BaseModel):
    session_id: str
    created_at: str
    updated_at: str
    status: str  # setup | generating | ready | in_progress | completed | error
    setup: SessionSetup
    company_analysis: Optional[str] = None
    questions: list = []
    overall_score: Optional[float] = None
    session_summary: Optional[str] = None
    error_message: Optional[str] = None
