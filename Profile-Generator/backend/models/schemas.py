from pydantic import BaseModel
from typing import Optional, List


class GenerateRequest(BaseModel):
    session_id: str
    links: List[str] = []


class ProfileData(BaseModel):
    name: str = ""
    title: str = ""
    email: str = ""
    phone: str = ""
    location: str = ""
    linkedin: str = ""
    github: str = ""
    summary: str = ""
    experience: list = []
    education: list = []
    skills: list = []
    certifications: list = []
    projects: list = []
    achievements: list = []


class JobStatus(BaseModel):
    job_id: str
    status: str  # idle | parsing | extracting | generating | done | error
    progress: int = 0
    step_message: str = ""
    error: Optional[str] = None
    result: Optional[dict] = None
