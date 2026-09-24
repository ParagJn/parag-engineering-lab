"""
Skill generation pipeline and eval runner.

generate_events() and test_events() are async generators of progress events
that main.py streams to the browser as Server-Sent Events:

    {"type": "stage", "stage": "design", "message": "..."}
    {"type": "done", "skill": {...}}
    {"type": "error", "status": 502, "detail": "..."}
"""

import asyncio
import json
import logging
import re

import prompts as P
import skill_spec as spec
import skill_store
from bundle import BundleError, parse_bundle, serialize_bundle, set_skill_name, slugify, strip_fields
from config import config
from model_service import ModelConfigError, ModelRateLimitError, get_model_service
from validator import load_evals, validate_bundle

logger = logging.getLogger(__name__)

_JSON_OBJ_RE = re.compile(r"\{.*\}", re.DOTALL)
EVAL_CONCURRENCY = 2


class PipelineError(Exception):
    def __init__(self, status: int, detail: str):
        super().__init__(detail)
        self.status = status
        self.detail = detail


def _stage(stage: str, message: str, **extra) -> dict:
    return {"type": "stage", "stage": stage, "message": message, **extra}


async def call_llm(platform: str, prompt: str, *, system: str | None = None,
                   max_tokens: int | None = None) -> str:
    if platform not in config.MODEL_CHOICES:
        raise PipelineError(400, f"Invalid platform: {platform}")
    try:
        return await get_model_service().generate(prompt, platform, system=system, max_tokens=max_tokens)
    except ModelConfigError as e:
        raise PipelineError(500, str(e))
    except ModelRateLimitError as e:
        raise PipelineError(429, f"IBM ICA rate limit: {e}")
    except RuntimeError as e:
        raise PipelineError(502, str(e))


def parse_json(text: str) -> dict | None:
    text = (text or "").strip()
    text = re.sub(r"^```(?:json)?\s*\n|\n```\s*$", "", text)
    for candidate in (text, *(_JSON_OBJ_RE.findall(text)[:1])):
        try:
            data = json.loads(candidate)
            if isinstance(data, dict):
                return data
        except json.JSONDecodeError:
            continue
    return None


def _normalize_options(options: dict | None) -> dict:
    options = options or {}
    return {
        "invocation": options.get("invocation") if options.get("invocation") in P.INVOCATION_HINTS else "auto",
        "scripts": options.get("scripts") if options.get("scripts") in P.SCRIPT_HINTS else "auto",
        "script_language": options.get("script_language")
        if options.get("script_language") in ("python", "bash", "node") else "python",
    }


def _frontmatter_guide(platform: str) -> str:
    return P.CLAUDE_CODE_FRONTMATTER if platform == "anthropic" else P.SPEC_ONLY_FRONTMATTER


# ---------------------------------------------------------------------------
# Generation
# ---------------------------------------------------------------------------

async def _blueprint(platform: str, thought: str, options: dict) -> dict:
    prompt = P.render(
        P.BLUEPRINT_PROMPT,
        platform=P.platform_name(platform),
        guide=P.AUTHORING_GUIDE,
        frontmatter=_frontmatter_guide(platform),
        invocation=P.INVOCATION_HINTS[options["invocation"]] if platform == "anthropic"
        else "Default (Claude Code invocation fields are not available on this platform).",
        scripts=P.SCRIPT_HINTS[options["scripts"]] if platform in spec.BUNDLE_PLATFORMS
        else "No scripts — single instructions file.",
        language=options["script_language"],
        thought=thought,
    )
    for attempt in range(2):
        text = await call_llm(platform, prompt, max_tokens=config.MAX_TOKENS)
        data = parse_json(text)
        if data and data.get("name"):
            return data
        logger.warning("Blueprint was not valid JSON (attempt %d)", attempt + 1)
        prompt += "\n\nIMPORTANT: your previous reply was not valid JSON. Return ONLY the JSON object."
    raise PipelineError(502, "The model did not return a valid skill blueprint. Please try again.")


def _post_process(files: dict[str, str], platform: str, name: str) -> tuple[dict[str, str], list[str]]:
    """Deterministic fixes: name = folder name, strip unsupported frontmatter fields."""
    notes = []
    if spec.SKILL_FILE in files:
        files[spec.SKILL_FILE] = set_skill_name(files[spec.SKILL_FILE], name)
        if platform != "anthropic":
            content, removed = strip_fields(files[spec.SKILL_FILE], spec.ALLOWED_FIELDS[platform])
            if removed:
                files[spec.SKILL_FILE] = content
                notes.append(f"Removed unsupported frontmatter fields: {', '.join(removed)}")
    if platform not in spec.BUNDLE_PLATFORMS:
        extra = [p for p in files if p != spec.SKILL_FILE]
        for p in extra:
            del files[p]
        if extra:
            notes.append(f"Dropped extra files for single-file platform: {', '.join(extra)}")
    return files, notes


async def _write_bundle(platform: str, thought: str, blueprint: dict, name: str) -> tuple[dict, list[str]]:
    template = P.BUNDLE_PROMPT if platform in spec.BUNDLE_PLATFORMS else P.SINGLE_FILE_PROMPT
    prompt = P.render(
        template,
        platform=P.platform_name(platform),
        guide=P.AUTHORING_GUIDE,
        frontmatter=_frontmatter_guide(platform),
        blueprint=json.dumps(blueprint, indent=2),
        thought=thought,
        name=name,
    )
    text = await call_llm(platform, prompt, max_tokens=config.GENERATION_MAX_TOKENS)
    files, rejected = parse_bundle(text)
    if spec.SKILL_FILE not in files:
        raise PipelineError(502, "The model's output did not include a SKILL.md. Please try again.")
    return files, rejected


async def _repair(platform: str, files: dict[str, str], errors: list[str]) -> dict[str, str]:
    prompt = P.render(
        P.REPAIR_PROMPT,
        platform=P.platform_name(platform),
        frontmatter=_frontmatter_guide(platform),
        errors="\n".join(f"- {e}" for e in errors),
        bundle=serialize_bundle(files),
    )
    text = await call_llm(platform, prompt, max_tokens=config.GENERATION_MAX_TOKENS)
    repaired, _ = parse_bundle(text)
    # A partial reply must never lose files — keep anything the model left out
    if spec.SKILL_FILE not in repaired:
        return files
    return {**files, **repaired}


async def usage_notes(platform: str, name: str, files: dict[str, str]) -> str:
    """Non-critical — a failure here shouldn't lose the skill."""
    invoke = {
        "anthropic": f"In Claude Code, type `/{name}` (plus any arguments), or just describe the task and Claude loads it automatically when the description matches.",
        "gemini": "In Gemini CLI, describe the task; the skill is activated when its description matches.",
        "chatgpt": "Chat with the Custom GPT as usual.",
    }[platform]
    prompt = P.render(
        P.USAGE_NOTES_PROMPT,
        platform=P.platform_name(platform),
        name=name,
        file_list=", ".join(f"`{p}`" for p in files),
        install_hint=P.render(P.INSTALL_HINTS[platform], name=name),
        invoke_hint=invoke,
        skill_content=files.get(spec.SKILL_FILE, ""),
    )
    try:
        return await call_llm(platform, prompt)
    except PipelineError as e:
        logger.warning("Usage notes generation failed: %s", e.detail)
        return ""


async def generate_events(platform: str, thought: str, options: dict | None = None,
                          skill_id: str | None = None):
    """Blueprint -> write files -> validate -> repair (≤N rounds) -> usage notes -> save."""
    try:
        if platform not in config.MODEL_CHOICES:
            raise PipelineError(400, f"Invalid platform: {platform}")
        options = _normalize_options(options)
        bundle_mode = platform in spec.BUNDLE_PLATFORMS

        yield _stage("design", "Designing the skill (name, triggers, files, evals)…")
        blueprint = await _blueprint(platform, thought, options)
        name = slugify(blueprint.get("name", ""))
        planned = [f.get("path") for f in blueprint.get("files", []) if isinstance(f, dict)]
        yield _stage("design", f"Planned `{name}` with {len(planned) or 1} file(s)", done=True,
                     files=planned if bundle_mode else [spec.SKILL_FILE])

        yield _stage("write", "Writing SKILL.md" + (", references, scripts and evals…" if bundle_mode else "…"))
        files, rejected = await _write_bundle(platform, thought, blueprint, name)
        files, notes = _post_process(files, platform, name)
        msg = f"Wrote {len(files)} file(s)"
        if rejected:
            msg += f"; skipped unsafe paths: {', '.join(rejected)}"
        yield _stage("write", msg, done=True, files=list(files))

        report = validate_bundle(files, platform)
        yield _stage("validate", _report_line(report), done=True, report=report)

        for round_no in range(1, config.MAX_REPAIR_ROUNDS + 1):
            if report["ok"]:
                break
            yield _stage("repair", f"Fixing {len(report['errors'])} error(s) — round {round_no}…")
            files = await _repair(platform, files, report["errors"])
            files, more = _post_process(files, platform, name)
            notes += more
            report = validate_bundle(files, platform)
            yield _stage("repair", _report_line(report), done=True, report=report)

        yield _stage("notes", "Writing the usage guide…")
        notes_md = await usage_notes(platform, name, files)
        yield _stage("notes", "Usage guide ready", done=True)

        skill = skill_store.save_skill(
            files, platform, thought, notes_md, skill_id,
            options={**options, "blueprint": blueprint, "post_process": notes},
            format_version=spec.FORMAT_VERSION,
        )
        yield _stage("save", f"Saved as `{skill['skill_dir']}`", done=True)
        yield {"type": "done", "skill": skill}
    except PipelineError as e:
        yield {"type": "error", "status": e.status, "detail": e.detail}
    except BundleError as e:
        yield {"type": "error", "status": 502, "detail": str(e)}
    except Exception as e:  # noqa: BLE001 — surface anything unexpected to the UI
        logger.exception("Generation failed")
        yield {"type": "error", "status": 500, "detail": f"Unexpected error: {e}"}


def _report_line(report: dict) -> str:
    e, w, p = len(report["errors"]), len(report["warnings"]), len(report["passed"])
    return f"{'✓ Valid' if report['ok'] else f'{e} error(s)'} · {w} warning(s) · {p} check(s) passed"


# ---------------------------------------------------------------------------
# Evals
# ---------------------------------------------------------------------------

def _skill_context(files: dict[str, str]) -> str:
    """SKILL.md plus every other file, as Claude would see them after reading."""
    parts = [files.get(spec.SKILL_FILE, "")]
    for path, content in files.items():
        if path in (spec.SKILL_FILE, spec.EVALS_FILE):
            continue
        label = "SCRIPT SOURCE (cannot be executed in this test)" if spec.script_language(path) else "FILE"
        parts.append(f"--- {label}: {path} ---\n{content}")
    return "\n\n".join(parts)


async def _run_eval(platform: str, name: str, context: str, scenario: dict, index: int) -> dict:
    behaviors = [str(b) for b in scenario.get("expected_behavior", [])]
    system = P.render(P.EVAL_RUN_SYSTEM, platform=P.platform_name(platform), name=name, skill_content=context)
    response = await call_llm(platform, scenario["query"], system=system, max_tokens=config.MAX_TOKENS)
    grade_prompt = P.render(
        P.EVAL_GRADE_PROMPT,
        query=scenario["query"],
        behaviors="\n".join(f"{i}. {b}" for i, b in enumerate(behaviors, 1)),
        response=response,
    )
    grade = parse_json(await call_llm(platform, grade_prompt)) or {}
    results = grade.get("results") if isinstance(grade.get("results"), list) else []
    if not results:
        results = [{"behavior": b, "pass": False, "reason": "Grader returned no verdict"} for b in behaviors]
    passed = sum(1 for r in results if r.get("pass") is True)
    return {
        "index": index,
        "query": scenario["query"],
        "response": response,
        "results": results,
        "passed": passed,
        "total": len(results),
        "overall_pass": bool(grade.get("overall_pass")) and passed == len(results),
        "suggestions": grade.get("suggestions") or [],
    }


async def test_events(skill_id: str):
    """Static checks, then run each eval scenario with the skill loaded and grade it."""
    try:
        m, files = skill_store.get_bundle(skill_id)
        platform, name = m["platform"], m["skill_dir"] or m["name"]
        if not files:
            raise PipelineError(404, "Skill files not found")

        report = validate_bundle(files, platform)
        yield _stage("static", _report_line(report) + " (scripts are syntax-checked, never executed)",
                     done=True, report=report)

        evals = load_evals(files)
        if not evals:
            hint = "Upgrade to a full bundle to get evals/evals.json." if m.get("format_version", 1) < 2 \
                else "Add scenarios to evals/evals.json."
            yield {"type": "done", "result": {"static": report, "evals": [], "summary": f"No eval scenarios. {hint}"}}
            return

        yield _stage("evals", f"Running {len(evals)} eval scenario(s) with the skill loaded…")
        context = _skill_context(files)
        sem = asyncio.Semaphore(EVAL_CONCURRENCY)

        async def run(i: int, scenario: dict) -> dict:
            async with sem:
                return await _run_eval(platform, name, context, scenario, i)

        results = []
        for task in asyncio.as_completed([run(i, e) for i, e in enumerate(evals, 1)]):
            result = await task
            results.append(result)
            yield {"type": "eval", "eval": result}

        results.sort(key=lambda r: r["index"])
        n_pass = sum(r["overall_pass"] for r in results)
        summary = {
            "static": report,
            "evals": results,
            "passed": n_pass,
            "total": len(results),
            "summary": f"{n_pass}/{len(results)} scenarios passed",
        }
        skill_store.set_eval_results(skill_id, {k: v for k, v in summary.items() if k != "static"})
        yield {"type": "done", "result": summary}
    except skill_store.SkillNotFound:
        yield {"type": "error", "status": 404, "detail": "Skill not found"}
    except PipelineError as e:
        yield {"type": "error", "status": e.status, "detail": e.detail}
    except Exception as e:  # noqa: BLE001
        logger.exception("Test failed")
        yield {"type": "error", "status": 500, "detail": f"Unexpected error: {e}"}
