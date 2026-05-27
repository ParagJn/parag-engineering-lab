from pydantic import BaseModel, Field, HttpUrl


class LinkItem(BaseModel):
    url: HttpUrl


class GenerateRequest(BaseModel):
    session_id: str = ""
    links: list[str] = Field(default_factory=list)
    target_role: str = ""
    target_company: str = ""
    job_description: str = ""


class ATSReport(BaseModel):
    score: int
    matched_keywords: list[str]
    missing_keywords: list[str]
    recommended_keywords: list[str]
    section_tips: list[str]


class GenerateResult(BaseModel):
    job_id: str
    profile_json: dict
    cv_markdown: str
    cv_html: str
    evidence_text: str
    ats_report: ATSReport


class JobStatusResponse(BaseModel):
    job_id: str
    status: str
    progress: int
    step_message: str
    error: str | None = None
    done: bool = False


class UploadResponse(BaseModel):
    session_id: str
    file_count: int
