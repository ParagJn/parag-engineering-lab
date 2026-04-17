"""Morning Edition — FastAPI Backend."""

import os
import json
import re
from datetime import datetime

from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse
from pydantic import BaseModel

# Load .env from project root
load_dotenv(os.path.join(os.path.dirname(__file__), "..", ".env"))

from sources import get_all_sources, get_source
from fetcher import fetch_rss_stories, enrich_stories_with_gemini
from curator import curate_magazine
from magazine import generate_magazine_html

app = FastAPI(title="Morning Edition API", version="1.0.0")

ARCHIVE_DIR = os.path.join(os.path.dirname(__file__), "..", "Archive")
os.makedirs(ARCHIVE_DIR, exist_ok=True)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/api/sources")
async def list_sources():
    """Return available news sources."""
    return {"sources": get_all_sources()}


class GenerateRequest(BaseModel):
    source_ids: list[str]


@app.post("/api/generate")
async def generate_magazine(req: GenerateRequest):
    """Generate the morning edition magazine from one or more sources."""
    if not req.source_ids:
        raise HTTPException(status_code=400, detail="At least one source is required")

    resolved_sources = []
    for sid in req.source_ids:
        source = get_source(sid)
        if not source:
            raise HTTPException(status_code=400, detail=f"Unknown source: {sid}")
        resolved_sources.append((sid, source))

    try:
        # Step 1: Fetch stories from all sources in parallel
        import asyncio
        fetch_tasks = [fetch_rss_stories(src["feed_url"]) for _, src in resolved_sources]
        all_results = await asyncio.gather(*fetch_tasks, return_exceptions=True)

        all_stories = []
        for (sid, src), result in zip(resolved_sources, all_results):
            if isinstance(result, Exception) or not result:
                continue
            # Tag each story with its source
            for story in result:
                story["_source_name"] = src["name"]
                story["_source_id"] = sid
            all_stories.extend(result)

        if not all_stories:
            raise HTTPException(status_code=502, detail="No stories fetched from any source")

        # Build combined source name for display
        source_names = [src["name"] for _, src in resolved_sources]
        combined_source = " + ".join(source_names)

        # Step 2: Enrich with Gemini (search & categorize)
        enriched = await enrich_stories_with_gemini(all_stories, combined_source)

        # Step 3: Curate with Anthropic Claude
        edition_date = datetime.now().strftime("%A, %B %d, %Y")
        magazine_data = await curate_magazine(enriched, combined_source, edition_date)

        # Step 4: Render HTML
        html = generate_magazine_html(magazine_data, combined_source)

        # Step 5: Save to Archive
        now = datetime.now()
        safe_source = re.sub(r'[^a-zA-Z0-9]', '-', combined_source).strip('-')
        filename = f"{now.strftime('%Y-%m-%d_%H-%M-%S')}_{safe_source}.html"
        filepath = os.path.join(ARCHIVE_DIR, filename)
        with open(filepath, "w", encoding="utf-8") as f:
            f.write(html)

        # Save metadata alongside
        meta = {
            "filename": filename,
            "title": magazine_data.get("magazine_title", "Morning Edition"),
            "source": combined_source,
            "source_ids": req.source_ids,
            "date": now.strftime("%a, %b %d, %Y"),
            "time": now.strftime("%I:%M %p"),
            "story_count": len(magazine_data.get("stories", [])),
            "created_at": now.isoformat(),
        }
        meta_path = filepath.replace(".html", ".json")
        with open(meta_path, "w", encoding="utf-8") as f:
            json.dump(meta, f, indent=2)

        return {
            "html": html,
            "title": magazine_data.get("magazine_title", "Morning Edition"),
            "story_count": len(magazine_data.get("stories", [])),
            "archive_file": filename,
            "source_ids": req.source_ids,
        }

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/generate/html", response_class=HTMLResponse)
async def generate_magazine_html_endpoint(req: GenerateRequest):
    """Generate and return raw HTML directly."""
    result = await generate_magazine(req)
    return HTMLResponse(content=result["html"])


# ── Archive Endpoints ──


@app.get("/api/archive")
async def list_archive():
    """List all archived magazines, newest first."""
    entries = []
    for fname in sorted(os.listdir(ARCHIVE_DIR), reverse=True):
        if not fname.endswith(".json"):
            continue
        meta_path = os.path.join(ARCHIVE_DIR, fname)
        try:
            with open(meta_path, "r", encoding="utf-8") as f:
                meta = json.load(f)
            entries.append(meta)
        except (json.JSONDecodeError, OSError):
            continue
    return {"archive": entries}


@app.get("/api/archive/{filename}", response_class=HTMLResponse)
async def get_archived_magazine(filename: str):
    """Serve an archived magazine HTML file."""
    # Sanitize filename to prevent path traversal
    safe_name = os.path.basename(filename)
    if not safe_name.endswith(".html"):
        raise HTTPException(status_code=400, detail="Invalid filename")
    filepath = os.path.join(ARCHIVE_DIR, safe_name)
    if not os.path.isfile(filepath):
        raise HTTPException(status_code=404, detail="Archive not found")
    with open(filepath, "r", encoding="utf-8") as f:
        return HTMLResponse(content=f.read())


@app.delete("/api/archive/{filename}")
async def delete_archived_magazine(filename: str):
    """Delete an archived magazine."""
    safe_name = os.path.basename(filename)
    html_path = os.path.join(ARCHIVE_DIR, safe_name)
    meta_path = html_path.replace(".html", ".json")
    if not os.path.isfile(html_path):
        raise HTTPException(status_code=404, detail="Archive not found")
    os.remove(html_path)
    if os.path.isfile(meta_path):
        os.remove(meta_path)
    return {"deleted": safe_name}


@app.delete("/api/archive")
async def clear_archive():
    """Delete all archived magazines."""
    count = 0
    for fname in os.listdir(ARCHIVE_DIR):
        fpath = os.path.join(ARCHIVE_DIR, fname)
        if os.path.isfile(fpath):
            os.remove(fpath)
            count += 1
    return {"deleted_count": count}
