"""
Generate router — orchestrates the full pipeline:
  1. Parse uploaded documents
  2. Fetch GitHub data if links contain GitHub URLs
  3. Gemini extracts structured profile JSON
  4. Claude generates CV HTML + LinkedIn HTML
  5. Playwright renders CV HTML → PDF
  6. Store results; serve via /status and /result endpoints
"""
import asyncio
import json
import logging
import uuid
from pathlib import Path
from typing import Optional

import aiofiles
from fastapi import APIRouter, BackgroundTasks, HTTPException
from fastapi.responses import FileResponse, JSONResponse

from services.parser import parse_file
from services.ai_service import (
    extract_profile_with_gemini,
    generate_cv_outputs_with_claude,
    refine_outputs_with_claude,
    fetch_github_profile,
    extract_github_username,
)
from services.pdf_export import html_to_pdf

logger = logging.getLogger(__name__)
router = APIRouter()

# In-memory job store (fine for local single-user app)
JOBS: dict[str, dict] = {}

UPLOAD_DIR = Path(__file__).resolve().parent.parent.parent / "uploads"
OUTPUT_DIR = Path(__file__).resolve().parent.parent.parent / "output"
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)


def _update_job(job_id: str, **kwargs):
    if job_id in JOBS:
        JOBS[job_id].update(kwargs)


# ─────────────────────────────────────────────
# Background pipeline
# ─────────────────────────────────────────────

async def _run_pipeline(job_id: str, session_id: str, links: list[str]):
    try:
        # ── Step 1: Parse documents ──────────────────────
        _update_job(job_id, status="parsing", progress=10, step_message="Parsing uploaded documents…")
        session_dir = UPLOAD_DIR / session_id
        doc_texts = []

        if session_dir.exists():
            for fpath in session_dir.iterdir():
                if fpath.is_file():
                    async with aiofiles.open(fpath, "rb") as f:
                        raw = await f.read()
                    text = parse_file(fpath.name, raw)
                    if text:
                        doc_texts.append(f"=== Document: {fpath.name} ===\n{text}")
                        logger.info(f"Parsed {fpath.name}: {len(text)} chars")

        # ── Step 2: Fetch linked profiles ────────────────
        _update_job(job_id, status="fetching", progress=25, step_message="Fetching data from public links…")
        link_texts = []
        for link in links:
            link = link.strip()
            if not link:
                continue
            username = extract_github_username(link)
            if username:
                gh_text = await fetch_github_profile(username)
                if gh_text:
                    link_texts.append(f"=== GitHub Profile: {link} ===\n{gh_text}")
            else:
                link_texts.append(f"=== Public Link: {link} ===\n(manual review required)")

        combined_text = "\n\n".join(doc_texts + link_texts)
        if not combined_text.strip():
            _update_job(job_id, status="error", error="No content could be extracted from the provided documents or links.")
            return

        # ── Step 3: Gemini extraction ────────────────────
        _update_job(job_id, status="extracting", progress=45, step_message="Gemini is extracting your profile data…")
        loop = asyncio.get_running_loop()
        profile_data = await loop.run_in_executor(None, _sync_gemini, combined_text)

        _update_job(job_id, step_message="Profile data extracted successfully.", progress=55, profile_data=profile_data)

        # ── Step 4: Claude generation ────────────────────
        _update_job(job_id, status="generating", progress=60, step_message="Claude is crafting your HTML CV and LinkedIn profile…")
        outputs = await loop.run_in_executor(None, _sync_claude, profile_data)

        cv_html = outputs["cv_html"]
        linkedin_html = outputs["linkedin_html"]
        _update_job(job_id, step_message="HTML outputs generated.", progress=80)

        # ── Step 5: PDF export ───────────────────────────
        _update_job(job_id, status="exporting", progress=85, step_message="Rendering PDF with Playwright…")
        out_dir = OUTPUT_DIR / job_id
        out_dir.mkdir(parents=True, exist_ok=True)

        cv_html_path = out_dir / "cv.html"
        linkedin_html_path = out_dir / "linkedin.html"
        pdf_path = out_dir / "cv.pdf"

        async with aiofiles.open(cv_html_path, "w", encoding="utf-8") as f:
            await f.write(cv_html)
        async with aiofiles.open(linkedin_html_path, "w", encoding="utf-8") as f:
            await f.write(linkedin_html)

        pdf_ok = await html_to_pdf(cv_html, str(pdf_path))

        # ── Step 6: Done ─────────────────────────────────
        _update_job(
            job_id,
            status="done",
            progress=100,
            step_message="All outputs ready!",
            result={
                "cv_html": cv_html,
                "linkedin_html": linkedin_html,
                "pdf_ready": pdf_ok,
                "job_id": job_id,
                "profile_name": profile_data.get("name", ""),
            },
        )
        logger.info(f"Job {job_id} completed successfully.")

    except Exception as e:
        logger.exception(f"Pipeline error for job {job_id}: {e}")
        _update_job(job_id, status="error", error=str(e))


def _sync_gemini(combined_text: str) -> dict:
    """Run Gemini extraction synchronously (for thread executor)."""
    import asyncio as _asyncio

    loop = _asyncio.new_event_loop()
    try:
        return loop.run_until_complete(extract_profile_with_gemini(combined_text))
    finally:
        loop.close()


def _sync_claude(profile_data: dict) -> dict:
    """Run Claude generation synchronously (for thread executor)."""
    import asyncio as _asyncio

    loop = _asyncio.new_event_loop()
    try:
        return loop.run_until_complete(generate_cv_outputs_with_claude(profile_data))
    finally:
        loop.close()


def _sync_claude_refine(profile_data: dict, cv_html: str, linkedin_html: str, instructions: str) -> dict:
    """Run Claude refinement synchronously (for thread executor)."""
    import asyncio as _asyncio

    loop = _asyncio.new_event_loop()
    try:
        return loop.run_until_complete(
            refine_outputs_with_claude(profile_data, cv_html, linkedin_html, instructions)
        )
    finally:
        loop.close()


async def _run_refinement(job_id: str, instructions: str):
    job = JOBS[job_id]
    profile_data = job.get("profile_data", {})
    old_result = job.get("result", {})
    try:
        _update_job(job_id, status="refining", progress=30, step_message="Claude is applying your changes…")
        loop = asyncio.get_running_loop()
        outputs = await loop.run_in_executor(
            None, _sync_claude_refine,
            profile_data,
            old_result.get("cv_html", ""),
            old_result.get("linkedin_html", ""),
            instructions,
        )
        _update_job(job_id, status="exporting", progress=80, step_message="Rendering updated PDF…")
        out_dir = OUTPUT_DIR / job_id
        async with aiofiles.open(out_dir / "cv.html", "w", encoding="utf-8") as f:
            await f.write(outputs["cv_html"])
        async with aiofiles.open(out_dir / "linkedin.html", "w", encoding="utf-8") as f:
            await f.write(outputs["linkedin_html"])
        pdf_ok = await html_to_pdf(outputs["cv_html"], str(out_dir / "cv.pdf"))
        new_result = {**old_result, **outputs, "pdf_ready": pdf_ok}
        _update_job(job_id, status="done", progress=100, step_message="Changes applied!", result=new_result)
        logger.info(f"Refinement for job {job_id} completed.")
    except Exception as e:
        logger.exception(f"Refinement error for job {job_id}: {e}")
        JOBS[job_id].update({"status": "done", "error": str(e), "result": old_result})


# ─────────────────────────────────────────────
# Endpoints
# ─────────────────────────────────────────────

@router.post("/generate")
async def start_generation(payload: dict, background_tasks: BackgroundTasks):
    session_id = payload.get("session_id", "")
    links = payload.get("links", [])

    job_id = str(uuid.uuid4())
    JOBS[job_id] = {
        "job_id": job_id,
        "status": "queued",
        "progress": 0,
        "step_message": "Job queued…",
        "error": None,
        "result": None,
    }
    background_tasks.add_task(_run_pipeline, job_id, session_id, links)
    return JSONResponse({"job_id": job_id})


@router.post("/refine")
async def refine_generation(payload: dict, background_tasks: BackgroundTasks):
    job_id = payload.get("job_id", "")
    instructions = payload.get("instructions", "").strip()
    if not job_id:
        raise HTTPException(status_code=400, detail="job_id is required")
    if not instructions:
        raise HTTPException(status_code=400, detail="instructions are required")
    job = JOBS.get(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    if job["status"] != "done":
        raise HTTPException(status_code=400, detail="Job must be complete before refining")
    JOBS[job_id].update({
        "status": "refining",
        "progress": 10,
        "step_message": "Starting refinement…",
        "error": None,
    })
    background_tasks.add_task(_run_refinement, job_id, instructions)
    return JSONResponse({"job_id": job_id})


@router.get("/status/{job_id}")
async def get_status(job_id: str):
    job = JOBS.get(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    # Return status without the full HTML to keep it light
    return {
        "job_id": job_id,
        "status": job["status"],
        "progress": job["progress"],
        "step_message": job["step_message"],
        "error": job["error"],
        "done": job["status"] == "done",
    }


@router.get("/result/{job_id}")
async def get_result(job_id: str):
    job = JOBS.get(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    if job["status"] != "done":
        raise HTTPException(status_code=202, detail="Job not yet complete")
    return JSONResponse(job["result"])


@router.get("/download/{job_id}/pdf")
async def download_pdf(job_id: str):
    pdf_path = OUTPUT_DIR / job_id / "cv.pdf"
    if not pdf_path.exists():
        raise HTTPException(status_code=404, detail="PDF not found")
    return FileResponse(
        path=str(pdf_path),
        media_type="application/pdf",
        filename="profile-cv.pdf",
    )


@router.get("/download/{job_id}/cv-html")
async def download_cv_html(job_id: str):
    html_path = OUTPUT_DIR / job_id / "cv.html"
    if not html_path.exists():
        raise HTTPException(status_code=404, detail="CV HTML not found")
    return FileResponse(
        path=str(html_path),
        media_type="text/html",
        filename="profile-cv.html",
    )


@router.get("/download/{job_id}/linkedin-html")
async def download_linkedin_html(job_id: str):
    html_path = OUTPUT_DIR / job_id / "linkedin.html"
    if not html_path.exists():
        raise HTTPException(status_code=404, detail="LinkedIn HTML not found")
    return FileResponse(
        path=str(html_path),
        media_type="text/html",
        filename="profile-linkedin.html",
    )
