import asyncio
from datetime import datetime, timezone

from app import config
from app.llm_clients import LLMError, call_claude, call_gemini
from app.operations import OPERATIONS
from app.schemas import GenerateRequest, GenerateResponse


def build_prompt(payload: GenerateRequest) -> str:
    operation = OPERATIONS.get(payload.operation)
    if not operation:
        allowed = ", ".join(sorted(OPERATIONS.keys()))
        raise ValueError(f"Unknown operation '{payload.operation}'. Allowed: {allowed}")

    return (
        f"Operation: {operation['label']}\n"
        f"Instruction: {operation['prompt']}\n\n"
        f"Niche: {payload.niche}\n"
        f"Primary Platform: {payload.platform}\n"
        f"Target Audience: {payload.audience or 'Not provided'}\n"
        f"Metrics/Stats: {payload.metrics or 'Not provided'}\n"
        f"Extra Context: {payload.extra_context or 'Not provided'}\n\n"
        "Output rules:\n"
        "1) Provide practical, implementation-level guidance.\n"
        "2) Use headings and bullet points.\n"
        "3) Include examples/templates where relevant.\n"
        "4) End with a short execution checklist."
    )


def synthesize(gemini_output: str, claude_output: str) -> str:
    return (
        "# Unified Multi-Agent Output\n\n"
        "## Strategic Synthesis\n"
        "Both models were run in parallel. Use this consolidated structure to execute quickly.\n\n"
        "## Gemini Contribution\n"
        f"{gemini_output}\n\n"
        "## Claude Contribution\n"
        f"{claude_output}\n\n"
        "## Action Merge\n"
        "1. Take the shared recommendations present in both outputs as your baseline strategy.\n"
        "2. Use model-specific ideas as A/B test variants across content cycles.\n"
        "3. Track performance weekly and prune low-performing formats or hooks."
    )


async def run_multi_agent(payload: GenerateRequest) -> GenerateResponse:
    prompt = build_prompt(payload)

    gemini_task = asyncio.create_task(call_gemini(prompt))
    claude_task = asyncio.create_task(call_claude(prompt))

    gemini_output = ""
    claude_output = ""

    gemini_result, claude_result = await asyncio.gather(
        gemini_task,
        claude_task,
        return_exceptions=True
    )

    if isinstance(gemini_result, Exception):
        if isinstance(gemini_result, LLMError):
            gemini_output = str(gemini_result)
        else:
            gemini_output = f"Gemini call failed: {gemini_result}"
    else:
        gemini_output = gemini_result

    if isinstance(claude_result, Exception):
        if isinstance(claude_result, LLMError):
            claude_output = str(claude_result)
        else:
            claude_output = f"Claude call failed: {claude_result}"
    else:
        claude_output = claude_result

    return GenerateResponse(
        operation=payload.operation,
        prompt_preview=prompt,
        gemini_output=gemini_output,
        claude_output=claude_output,
        synthesized_output=synthesize(gemini_output, claude_output),
        metadata={
            "gemini_model": config.GEMINI["model"],
            "claude_model": config.CLAUDE["model"],
            "generated_at_utc": datetime.now(timezone.utc).isoformat()
        }
    )
