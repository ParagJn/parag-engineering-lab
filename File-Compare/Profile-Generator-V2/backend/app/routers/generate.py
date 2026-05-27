from __future__ import annotations

import json
import uuid
from pathlib import Path

import aiofiles
from fastapi import APIRouter, BackgroundTasks, HTTPException
from fastapi.responses import FileResponse

from app.models.schemas import GenerateRequest
from app.services.ats_optimizer import compute_ats_report, enrich_profile_with_keywords
from app.services.link_fetcher import fetch_link_text
from app.services.parser import parse_file
from app.services.profile_builder import build_profile
from app.services.llm_refiner import maybe_refine_profile_with_openai
from app.services.renderer import render_html_cv, render_markdown_cv
from app.state import JOBS, OUTPUT_DIR, UPLOAD_DIR, JobState

router = APIRouter()


def update_job(job_id: str, **kwargs):
    job = JOBS.get(job_id)
    if not job:
        return
    for key, value in kwargs.items():
        setattr(job, key, value)


async def collect_uploaded_text(session_id: str) -> str:
    if not session_id:
        return ""
    session_dir = UPLOAD_DIR / session_id
    if not session_dir.exists():
        return ""

    blocks: list[str] = []
    for path in session_dir.iterdir():
        if not path.is_file():
            continue
        async with aiofiles.open(path, "rb") as f:
            raw = await f.read()
        parsed = parse_file(path.name, raw)
        if parsed:
            blocks.append(f"### File: {path.name}\n{parsed}\n")
    return "\n\n".join(blocks)


async def collect_links_text(links: list[str]) -> str:
    if not links:
        return ""
    blocks: list[str] = []
    for link in links:
        link = (link or "").strip()
        if not link:
            continue
        content = await fetch_link_text(link)
        if content:
            blocks.append(f"### Link: {link}\n{content}\n")
    return "\n\n".join(blocks)


async def write_artifacts(job_id: str, payload: dict):
    out = OUTPUT_DIR / job_id
    out.mkdir(parents=True, exist_ok=True)

    async with aiofiles.open(out / "profile.json", "w", encoding="utf-8") as f:
        await f.write(json.dumps(payload["profile_json"], indent=2, ensure_ascii=False))
    async with aiofiles.open(out / "cv.md", "w", encoding="utf-8") as f:
        await f.write(payload["cv_markdown"])
    async with aiofiles.open(out / "cv.html", "w", encoding="utf-8") as f:
        await f.write(payload["cv_html"])
    async with aiofiles.open(out / "evidence.txt", "w", encoding="utf-8") as f:
        await f.write(payload["evidence_text"])
    async with aiofiles.open(out / "ats_report.json", "w", encoding="utf-8") as f:
        await f.write(json.dumps(payload["ats_report"], indent=2, ensure_ascii=False))


async def run_pipeline(job_id: str, request: GenerateRequest):
    try:
        update_job(job_id, status="ingesting", progress=10, step_message="Reading uploaded files and links...")
        file_text = await collect_uploaded_text(request.session_id)
        link_text = await collect_links_text(request.links)
        evidence = "\n\n".join(x for x in [file_text, link_text, request.job_description] if x.strip()).strip()

        if not evidence:
            raise ValueError("No usable content found in uploaded files, links, or job description.")

        update_job(job_id, status="extracting", progress=35, step_message="Extracting profile evidence and role signals...")
        profile = build_profile(evidence, target_role=request.target_role, target_company=request.target_company)
        profile = await maybe_refine_profile_with_openai(
            profile=profile,
            evidence_text=evidence,
            target_role=request.target_role,
            target_company=request.target_company,
        )

        update_job(job_id, status="optimizing", progress=60, step_message="Applying ATS keyword optimization...")
        ats_report = compute_ats_report(
            profile=profile,
            evidence_text=evidence,
            target_role=request.target_role,
            job_description=request.job_description,
        )
        profile = enrich_profile_with_keywords(profile, ats_report)

        update_job(job_id, status="rendering", progress=80, step_message="Rendering professional CV outputs...")
        markdown_cv = render_markdown_cv(profile, ats_report, request.target_role, request.target_company)
        html_cv = render_html_cv(markdown_cv, profile, ats_report)

        result_payload = {
            "job_id": job_id,
            "profile_json": profile,
            "cv_markdown": markdown_cv,
            "cv_html": html_cv,
            "evidence_text": evidence,
            "ats_report": ats_report,
        }

        await write_artifacts(job_id, result_payload)

        update_job(
            job_id,
            status="done",
            progress=100,
            step_message="CV and ATS report ready.",
            result=result_payload,
        )
    except Exception as exc:
        update_job(job_id, status="error", progress=100, step_message="Generation failed.", error=str(exc))


@router.post("/generate")
async def generate(payload: GenerateRequest, background_tasks: BackgroundTasks):
    if not payload.session_id and not payload.links and not payload.job_description.strip():
        raise HTTPException(status_code=400, detail="Provide at least one file, link, or job description.")

    job_id = str(uuid.uuid4())
    JOBS[job_id] = JobState(job_id=job_id)
    background_tasks.add_task(run_pipeline, job_id, payload)
    return {"job_id": job_id}


@router.get("/status/{job_id}")
async def status(job_id: str):
    job = JOBS.get(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")

    return {
        "job_id": job.job_id,
        "status": job.status,
        "progress": job.progress,
        "step_message": job.step_message,
        "error": job.error,
        "done": job.status in {"done", "error"},
    }


@router.get("/result/{job_id}")
async def result(job_id: str):
    job = JOBS.get(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    if job.status != "done" or not job.result:
        raise HTTPException(status_code=400, detail="Result not ready")
    return job.result


@router.get("/download/{job_id}/{kind}")
async def download(job_id: str, kind: str):
    mapping = {
        "html": "cv.html",
        "markdown": "cv.md",
        "json": "profile.json",
        "txt": "evidence.txt",
    }
    if kind not in mapping:
        raise HTTPException(status_code=400, detail=f"Invalid kind. Use one of {list(mapping.keys())}")

    path = OUTPUT_DIR / job_id / mapping[kind]
    if not path.exists():
        raise HTTPException(status_code=404, detail="File not found")

    media = {
        "html": "text/html",
        "markdown": "text/markdown",
        "json": "application/json",
        "txt": "text/plain",
    }[kind]

    return FileResponse(path, media_type=media, filename=path.name)
