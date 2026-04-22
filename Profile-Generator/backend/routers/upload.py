"""
Upload router — accepts up to 3 documents (PDF, DOCX, HTML) and returns a session_id
for use in the generate endpoint.
"""
import os
import uuid
import aiofiles
import logging
from pathlib import Path
from fastapi import APIRouter, File, UploadFile, HTTPException
from fastapi.responses import JSONResponse
from typing import List

logger = logging.getLogger(__name__)

router = APIRouter()

ALLOWED_TYPES = {
    "application/pdf": ".pdf",
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document": ".docx",
    "application/msword": ".doc",
    "text/html": ".html",
}
ALLOWED_EXTENSIONS = {".pdf", ".docx", ".doc", ".html", ".htm"}
MAX_FILES = 3
MAX_FILE_SIZE_MB = 20

UPLOAD_DIR = Path(__file__).resolve().parent.parent.parent / "uploads"
UPLOAD_DIR.mkdir(parents=True, exist_ok=True)


@router.post("/upload")
async def upload_documents(files: List[UploadFile] = File(...)):
    if len(files) > MAX_FILES:
        raise HTTPException(
            status_code=400,
            detail=f"Maximum {MAX_FILES} files allowed. You sent {len(files)}.",
        )

    session_id = str(uuid.uuid4())
    session_dir = UPLOAD_DIR / session_id
    session_dir.mkdir(parents=True, exist_ok=True)

    uploaded = []
    for file in files:
        ext = Path(file.filename or "").suffix.lower()
        if ext not in ALLOWED_EXTENSIONS:
            raise HTTPException(
                status_code=400,
                detail=f"'{file.filename}' is not allowed. Supported: PDF, DOCX, HTML.",
            )

        content = await file.read()
        size_mb = len(content) / (1024 * 1024)
        if size_mb > MAX_FILE_SIZE_MB:
            raise HTTPException(
                status_code=400,
                detail=f"'{file.filename}' exceeds {MAX_FILE_SIZE_MB} MB limit.",
            )

        safe_name = f"{uuid.uuid4().hex}{ext}"
        dest = session_dir / safe_name
        async with aiofiles.open(dest, "wb") as f:
            await f.write(content)

        uploaded.append({"original": file.filename, "saved": safe_name, "size_kb": round(len(content) / 1024, 1)})
        logger.info(f"Uploaded: {file.filename} → {safe_name}")

    return JSONResponse({"session_id": session_id, "files": uploaded})
