from __future__ import annotations

import asyncio
from textwrap import dedent

from .config import Settings
from .llm_clients import AgentResult, AzureChatAgent, SapCompletionAgent


MODE_INSTRUCTIONS = {
    "summarize": "Summarize the document for executives. Preserve structure, key decisions, risks, economics, and next steps.",
    "identify_gaps": "Identify gaps that materially affect execution. Avoid cosmetic criticism. Tie every point to evidence in the document.",
    "give_suggestions": "Suggest practical changes that improve the path from current state to target state. Keep recommendations subtle, defensible, and business-oriented.",
}


def _clip(text: str, limit: int = 80_000) -> str:
    return text[:limit]


def _fallback(mode: str, instruction: str, document_text: str) -> str:
    doc_hint = document_text[:3000]
    return dedent(
        f"""
        # Strategy Analysis

        The external model endpoints were not reachable or not configured, so this draft is based on local document extraction and the selected mode: **{mode.replace("_", " ").title()}**.

        ## Recommended Review Lens

        - Anchor every recommendation to the target-state objective, not to presentation polish.
        - Separate near-term containment from long-term platform migration so interim work does not create avoidable rework.
        - Add cost and turnaround measures to each initiative: expected run cost, build effort, migration treatment, and decision owner.
        - Prefer source-aligned or virtualized patterns for new reporting where possible, and reserve legacy platform changes for remediation of existing assets.
        - Add a cloud-cost workstream covering right-sizing, reserved capacity timing, storage lifecycle tiers, observability budgets, and chargeback/showback.

        ## Prompt Applied

        {instruction or "No additional prompt was provided."}

        ## Extract Preview Used

        {doc_hint}
        """
    ).strip()


def _combined_agent_output(mode: str, first_pass: AgentResult, cost_challenge: AgentResult, validation: AgentResult) -> str:
    sections = [f"# Strategy Analysis\n\nSelected mode: **{mode.replace('_', ' ').title()}**"]
    if first_pass.ok:
        sections.append(f"## Anthropic Strategy Architect\n\n{first_pass.content}")
    if cost_challenge.ok:
        sections.append(f"## Gemini Cost and Execution Challenge\n\n{cost_challenge.content}")
    if validation.ok:
        sections.append(f"## GPT Validation Notes\n\n{validation.content}")
    sections.append(
        "## Synthesis Note\n\nThe primary model analysis completed, but the final GPT synthesis step was not available. The sections above preserve the successful agent outputs directly."
    )
    return "\n\n".join(sections)


def build_agents(settings: Settings, thinking_mode: bool = True) -> tuple[SapCompletionAgent, SapCompletionAgent, AzureChatAgent, AzureChatAgent]:
    anthropic = SapCompletionAgent(
        settings,
        name="Anthropic Strategy Architect",
        model=settings.sap_anthropic_model,
        thinking=thinking_mode,
    )
    gemini = SapCompletionAgent(
        settings,
        name="Gemini Cost and Execution Challenger",
        model=settings.sap_gemini_model,
        thinking=False,
    )
    gpt54 = AzureChatAgent(
        "GPT-5.4 Strategy Synthesizer",
        settings.azure_openai_gpt54_base,
        settings.azure_openai_gpt54_key,
        settings.azure_openai_gpt54_version,
        settings.azure_openai_gpt54_deployment,
    )
    codex = AzureChatAgent(
        "GPT-5.3 Codex Validator",
        settings.azure_openai_gpt53codex_base,
        settings.azure_openai_gpt53codex_key,
        settings.azure_openai_gpt53codex_version,
        settings.azure_openai_gpt53codex_deployment,
    )
    return anthropic, gemini, gpt54, codex


async def safe_complete(agent, system: str, user: str, max_tokens: int = 4000) -> AgentResult:
    try:
        return await agent.complete(system, user, max_tokens=max_tokens)
    except Exception as exc:
        return AgentResult(agent=getattr(agent, "name", agent.__class__.__name__), content=str(exc), ok=False)


async def analyze_document(settings: Settings, mode: str, instruction: str, document_text: str, thinking_mode: bool = True) -> dict:
    mode = mode if mode in MODE_INSTRUCTIONS else "give_suggestions"
    anthropic, gemini, gpt54, codex = build_agents(settings, thinking_mode=thinking_mode)
    clipped_doc = _clip(document_text)

    system = dedent(
        """
        You are a senior data architecture, information management, and transformation strategy advisor.
        Be constructive and precise. Do not invent slide numbers or facts. If slide or page markers exist, cite them.
        Focus on how to reach the target state, reduce cost, shorten turnaround, and avoid interim technical debt.
        """
    ).strip()
    base_user = dedent(
        f"""
        Selected review mode: {mode}
        Mode instruction: {MODE_INSTRUCTIONS[mode]}

        User instruction:
        {instruction}

        Document text:
        {clipped_doc}
        """
    ).strip()

    first_pass, cost_challenge, validation = await asyncio.gather(
        safe_complete(anthropic, system, base_user + "\n\nThink deeply before answering. Focus on target-state journey, interim choices, and where subtle changes unlock better outcomes.", max_tokens=9000),
        safe_complete(gemini, system, base_user + "\n\nChallenge the plan from cost, cloud infrastructure, implementation effort, and faster turnaround perspectives. Only raise points that materially improve execution.", max_tokens=5500),
        safe_complete(codex, system, base_user + "\n\nProduce a validation checklist and call out weak assumptions.", max_tokens=3500),
    )

    if first_pass.ok or cost_challenge.ok or validation.ok:
        synthesis_prompt = dedent(
            f"""
            Produce the final response for the user in Markdown.

            Requirements:
            - Use bullet points where helpful.
            - Include document page/slide references only when supported by the extracted text.
            - Include suggestions for final objective, implementation cost, faster turnaround, and cloud infrastructure cost savings.
            - Explain why each suggestion is better than the likely default.
            - Acknowledge strong existing material instead of forcing changes.

            Anthropic-style analysis:
            {first_pass.content}

            Gemini cost/execution challenge:
            {cost_challenge.content}

            GPT validator notes:
            {validation.content}
            """
        ).strip()
        final = await safe_complete(gpt54, system, synthesis_prompt, max_tokens=7000)
        if final.ok:
            return {"content": final.content, "agents": [first_pass.__dict__, cost_challenge.__dict__, validation.__dict__, final.__dict__]}
        return {
            "content": _combined_agent_output(mode, first_pass, cost_challenge, validation),
            "agents": [first_pass.__dict__, cost_challenge.__dict__, validation.__dict__, final.__dict__],
            "warning": "Final GPT synthesis was unavailable; returned the successful Anthropic/Gemini agent outputs directly.",
        }

    return {
        "content": _fallback(mode, instruction, document_text),
        "agents": [first_pass.__dict__, cost_challenge.__dict__, validation.__dict__],
        "warning": "External model calls failed or were not configured; returned local fallback analysis.",
    }


async def chat_about_analysis(settings: Settings, question: str, document_text: str, analysis: str) -> dict:
    _, _, gpt54, codex = build_agents(settings)
    system = "You answer follow-up questions about a document analysis. Be concise, evidence-led, and practical."
    prompt = dedent(
        f"""
        Existing analysis:
        {analysis[:40_000]}

        Document text:
        {document_text[:40_000]}

        Follow-up question:
        {question}
        """
    ).strip()
    primary = await safe_complete(gpt54, system, prompt, max_tokens=3000)
    if primary.ok:
        return {"content": primary.content, "agents": [primary.__dict__]}
    backup = await safe_complete(codex, system, prompt, max_tokens=3000)
    if backup.ok:
        return {"content": backup.content, "agents": [primary.__dict__, backup.__dict__]}
    return {"content": "I could not reach the configured model endpoints for this follow-up. Please check backend environment variables and try again.", "agents": [primary.__dict__, backup.__dict__]}
