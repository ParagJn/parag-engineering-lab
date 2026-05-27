from __future__ import annotations

import uuid
from pathlib import Path

import aiofiles
from fastapi import APIRouter, File, HTTPException, UploadFile

from app.models.schemas import UploadResponse
from app.services.parser import ALLOWED_EXTENSIONS
from app.state import UPLOAD_DIR

router = APIRouter()


@router.post("/upload", response_model=UploadResponse)
async def upload_files(files: list[UploadFile] = File(...)):
    if not files:
        raise HTTPException(status_code=400, detail="At least one file is required.")

    session_id = str(uuid.uuid4())
    session_path = UPLOAD_DIR / session_id
    session_path.mkdir(parents=True, exist_ok=True)

    accepted = 0
    for file in files:
        ext = Path(file.filename or "").suffix.lower()
        if ext not in ALLOWED_EXTENSIONS:
            continue

        destination = session_path / (file.filename or f"file-{accepted}{ext}")
        content = await file.read()
        async with aiofiles.open(destination, "wb") as out:
            await out.write(content)
        accepted += 1

    if accepted == 0:
        raise HTTPException(status_code=400, detail=f"No supported files found. Allowed: {sorted(ALLOWED_EXTENSIONS)}")

    return UploadResponse(session_id=session_id, file_count=accepted)
