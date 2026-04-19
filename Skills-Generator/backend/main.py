import os
import io
import json
import uuid
import shutil
import zipfile
from datetime import datetime
from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, StreamingResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from dotenv import load_dotenv

import openai
import anthropic
import google.generativeai as genai

# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------
BASE_DIR = Path(__file__).resolve().parent.parent
load_dotenv(dotenv_path=BASE_DIR / ".env")

SKILLS_DIR = BASE_DIR / "skills"
ARCHIVE_DIR = SKILLS_DIR / ".archive"
SKILLS_DIR.mkdir(exist_ok=True)
ARCHIVE_DIR.mkdir(exist_ok=True)

METADATA_FILE = SKILLS_DIR / ".metadata.json"

# LLM clients
azure_openai_client = openai.AzureOpenAI(
    azure_endpoint=os.getenv("AZURE_OPENAI_GPT54_BASE"),
    api_key=os.getenv("AZURE_OPENAI_GPT54_KEY"),
    api_version=os.getenv("AZURE_OPENAI_GPT54_VERSION"),
)
anthropic_client = anthropic.Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))
genai.configure(api_key=os.getenv("GEMINI_API_KEY"))

# ---------------------------------------------------------------------------
# FastAPI app
# ---------------------------------------------------------------------------
app = FastAPI(title="Skills Generator")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ---------------------------------------------------------------------------
# Metadata helpers
# ---------------------------------------------------------------------------

def _load_meta() -> dict:
    if METADATA_FILE.exists():
        return json.loads(METADATA_FILE.read_text())
    return {}


def _save_meta(data: dict):
    METADATA_FILE.write_text(json.dumps(data, indent=2))


def _skill_file(m: dict) -> Path:
    """Return the path to the skill content file, handling both old and new formats."""
    # New format: skill_dir/SKILL.md
    if "skill_dir" in m:
        return SKILLS_DIR / m["skill_dir"] / "SKILL.md"
    # Legacy format: flat file
    return SKILLS_DIR / m["filename"]


# ---------------------------------------------------------------------------
# LLM helpers
# ---------------------------------------------------------------------------
GENERATE_PROMPT = """You are an expert AI skill/prompt engineer. Convert the user's idea into a fully structured, professional skill definition for the **{platform}** platform.

Output ONLY raw markdown in exactly this structure (no code fences):

---
name: skill-name-in-kebab-case
description: One-line description of the skill.
license: Complete terms in LICENSE.txt
---

# Skill Title

## Overview

2-3 sentence overview of what this skill does and who it's for.

**Keywords**: comma, separated, keywords

## Core Framework

### [Section Name]
- Key point
- Key point

(Add sections as needed)

## Features

- Feature 1
- Feature 2

## Output Format

- Describe the expected output

## Instructions

- Instruction 1
- Instruction 2

## Constraints

- Constraint 1
- Constraint 2

---
User's idea:
{thought}
"""

USAGE_NOTES_PROMPT = """You are a friendly AI instructor. Given the skill definition below, generate a concise **"How to Use This Skill"** guide for someone who has never used AI skills before.

Format your response as:

## How to Use This Skill

A 1-2 sentence summary of what this skill does in plain language.

### Getting Started
1. Step-by-step instructions (3-5 steps)
2. Keep each step to one short sentence

### Example Prompt
Provide one ready-to-use example prompt the user can copy-paste.

### Tips for Best Results
- 3-4 practical tips
- Written for beginners

---
Skill definition:
{skill_content}
"""

TEST_PROMPT = """You are testing an AI skill. Given the skill definition below, create a realistic test case, execute it by producing the expected output, and evaluate the result.

Format your response as:

## Test Case
**Input:** A realistic test input for this skill

## Expected Behavior
What the skill should do with this input

## Test Output
The actual output the skill would produce

## Test Result
✅ PASS — Brief explanation

---
Skill definition:
{skill_content}
"""


async def _call_llm(platform: str, prompt: str) -> str:
    if platform == "chatgpt":
        resp = azure_openai_client.chat.completions.create(
            model=os.getenv("AZURE_OPENAI_GPT54_DEPLOYMENT", "gpt-5.4-common"),
            messages=[{"role": "user", "content": prompt}],
            reasoning_effort="high",
        )
        return resp.choices[0].message.content
    elif platform == "anthropic":
        resp = anthropic_client.messages.create(
            model="claude-sonnet-4-20250514",
            max_tokens=4000,
            messages=[{"role": "user", "content": prompt}],
        )
        return resp.content[0].text
    elif platform == "gemini":
        model = genai.GenerativeModel("gemini-2.0-flash")
        resp = model.generate_content(prompt)
        return resp.text
    raise HTTPException(status_code=400, detail="Invalid platform")


def _save_skill(content: str, platform: str, thought: str, skill_id: str | None = None) -> dict:
    # Parse name from front-matter
    skill_name = "untitled-skill"
    for line in content.splitlines():
        stripped = line.strip()
        if stripped.startswith("name:"):
            skill_name = stripped.split(":", 1)[1].strip()
            break

    skill_id = skill_id or uuid.uuid4().hex[:8]

    # Save as a directory with SKILL.md (Anthropic-compatible format)
    skill_dir = SKILLS_DIR / skill_name
    skill_dir.mkdir(exist_ok=True)
    (skill_dir / "SKILL.md").write_text(content)

    # For Anthropic skills, also copy to .claude/skills/ inside the project
    if platform == "anthropic":
        claude_skills_dir = BASE_DIR / ".claude" / "skills" / skill_name
        claude_skills_dir.mkdir(parents=True, exist_ok=True)
        (claude_skills_dir / "SKILL.md").write_text(content)

    meta = _load_meta()
    meta[skill_id] = {
        "id": skill_id,
        "name": skill_name,
        "skill_dir": skill_name,
        "platform": platform,
        "thought": thought,
        "created_at": datetime.now().isoformat(),
        "archived": False,
        "usage_notes": "",
    }
    _save_meta(meta)
    return {"id": skill_id, "name": skill_name, "content": content, "skill_dir": skill_name, "platform": platform, "usage_notes": ""}


# ---------------------------------------------------------------------------
# Request models
# ---------------------------------------------------------------------------

class GenerateRequest(BaseModel):
    thought: str
    platform: str  # anthropic | gemini | chatgpt


# ---------------------------------------------------------------------------
# API routes
# ---------------------------------------------------------------------------

@app.post("/api/generate")
async def generate_skill(req: GenerateRequest):
    prompt = GENERATE_PROMPT.format(platform=req.platform, thought=req.thought)
    try:
        content = await _call_llm(req.platform, prompt)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    result = _save_skill(content, req.platform, req.thought)

    # Generate usage notes
    try:
        notes_prompt = USAGE_NOTES_PROMPT.format(skill_content=content)
        usage_notes = await _call_llm(req.platform, notes_prompt)
        meta = _load_meta()
        meta[result["id"]]["usage_notes"] = usage_notes
        _save_meta(meta)
        result["usage_notes"] = usage_notes
    except Exception:
        pass  # Non-critical — skill is already saved
    return result


@app.get("/api/skills")
async def list_skills():
    meta = _load_meta()
    out = []
    for sid, m in meta.items():
        if m.get("archived"):
            continue
        fp = _skill_file(m)
        content = fp.read_text() if fp.exists() else ""
        out.append({**m, "content": content})
    return sorted(out, key=lambda x: x.get("created_at", ""), reverse=True)


@app.get("/api/skills/{skill_id}")
async def get_skill(skill_id: str):
    meta = _load_meta()
    if skill_id not in meta:
        raise HTTPException(status_code=404, detail="Skill not found")
    m = meta[skill_id]
    fp = _skill_file(m)
    content = fp.read_text() if fp.exists() else ""
    return {**m, "content": content, "usage_notes": m.get("usage_notes", "")}


@app.delete("/api/skills/{skill_id}")
async def delete_skill(skill_id: str):
    meta = _load_meta()
    if skill_id not in meta:
        raise HTTPException(status_code=404, detail="Skill not found")
    m = meta[skill_id]
    skill_name = m.get("skill_dir", m.get("name", ""))
    # Remove skill directory (or legacy file)
    skill_dir = SKILLS_DIR / skill_name
    if skill_dir.is_dir():
        shutil.rmtree(str(skill_dir))
    elif "filename" in m:
        fp = SKILLS_DIR / m["filename"]
        if fp.exists():
            fp.unlink()
    # Also remove from .claude/skills/ if present
    claude_skill_dir = BASE_DIR / ".claude" / "skills" / skill_name
    if claude_skill_dir.is_dir():
        shutil.rmtree(str(claude_skill_dir))
    del meta[skill_id]
    _save_meta(meta)
    return {"status": "deleted"}


@app.post("/api/skills/{skill_id}/archive")
async def archive_skill(skill_id: str):
    meta = _load_meta()
    if skill_id not in meta:
        raise HTTPException(status_code=404, detail="Skill not found")
    m = meta[skill_id]
    skill_dir = SKILLS_DIR / m.get("skill_dir", m.get("name", ""))
    dst = ARCHIVE_DIR / m.get("skill_dir", m.get("name", ""))
    if skill_dir.is_dir():
        shutil.move(str(skill_dir), str(dst))
    elif "filename" in m:
        src = SKILLS_DIR / m["filename"]
        if src.exists():
            shutil.move(str(src), str(ARCHIVE_DIR / m["filename"]))
    meta[skill_id]["archived"] = True
    _save_meta(meta)
    return {"status": "archived"}


@app.post("/api/skills/{skill_id}/regenerate")
async def regenerate_skill(skill_id: str):
    meta = _load_meta()
    if skill_id not in meta:
        raise HTTPException(status_code=404, detail="Skill not found")
    m = meta[skill_id]
    thought, platform = m["thought"], m["platform"]

    # Remove old artefacts
    old_skill_name = m.get("skill_dir", m.get("name", ""))
    old_dir = SKILLS_DIR / old_skill_name
    if old_dir.is_dir():
        shutil.rmtree(str(old_dir))
    elif "filename" in m:
        old_fp = SKILLS_DIR / m["filename"]
        if old_fp.exists():
            old_fp.unlink()
    # Also remove old .claude/skills/ entry if present
    old_claude_dir = BASE_DIR / ".claude" / "skills" / old_skill_name
    if old_claude_dir.is_dir():
        shutil.rmtree(str(old_claude_dir))
    del meta[skill_id]
    _save_meta(meta)

    prompt = GENERATE_PROMPT.format(platform=platform, thought=thought)
    try:
        content = await _call_llm(platform, prompt)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    result = _save_skill(content, platform, thought)

    # Generate usage notes
    try:
        notes_prompt = USAGE_NOTES_PROMPT.format(skill_content=content)
        usage_notes = await _call_llm(platform, notes_prompt)
        meta = _load_meta()
        meta[result["id"]]["usage_notes"] = usage_notes
        _save_meta(meta)
        result["usage_notes"] = usage_notes
    except Exception:
        pass
    return result


@app.get("/api/skills/{skill_id}/download")
async def download_skill(skill_id: str):
    meta = _load_meta()
    if skill_id not in meta:
        raise HTTPException(status_code=404, detail="Skill not found")
    m = meta[skill_id]
    skill_name = m["name"]
    fp = _skill_file(m)
    if not fp.exists():
        raise HTTPException(status_code=404, detail="Skill file not found")

    # Create a zip in memory: skill-name/SKILL.md
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        zf.writestr(f"{skill_name}/SKILL.md", fp.read_text())
    buf.seek(0)
    return StreamingResponse(
        buf,
        media_type="application/zip",
        headers={"Content-Disposition": f'attachment; filename="{skill_name}.zip"'},
    )


@app.post("/api/skills/{skill_id}/test")
async def test_skill(skill_id: str):
    meta = _load_meta()
    if skill_id not in meta:
        raise HTTPException(status_code=404, detail="Skill not found")
    m = meta[skill_id]
    fp = _skill_file(m)
    if not fp.exists():
        raise HTTPException(status_code=404, detail="Skill file not found")

    prompt = TEST_PROMPT.format(skill_content=fp.read_text())
    try:
        result = await _call_llm(m["platform"], prompt)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    return {"test_result": result, "platform": m["platform"]}


# ---------------------------------------------------------------------------
# Serve frontend
# ---------------------------------------------------------------------------
FRONTEND_DIR = BASE_DIR / "frontend" / "public"

app.mount("/static", StaticFiles(directory=str(FRONTEND_DIR)), name="static")


@app.get("/")
async def root():
    return FileResponse(str(FRONTEND_DIR / "index.html"))
