from __future__ import annotations

import asyncio
from textwrap import dedent

from .config import Settings
from .llm_clients import AgentResult, build_provider_agents, normalize_provider


MODE_INSTRUCTIONS = {
    "summarize": "Summarize the document for executives. Preserve structure, key decisions, risks, economics, and next steps.",
    "identify_gaps": "Identify gaps that materially affect execution. Avoid cosmetic criticism. Tie every point to evidence in the document.",
    "give_suggestions": "Suggest practical changes that improve the path from current state to target state. Keep recommendations subtle, defensible, and business-oriented.",
}

AGENT_TIMEOUT_SECONDS = 240
ANALYSIS_DOC_LIMIT = 80_000
CHAT_DOC_LIMIT = 60_000
CHAT_ANALYSIS_LIMIT = 30_000
CHAT_HISTORY_TURNS = 10


def _clip(text: str, limit: int = ANALYSIS_DOC_LIMIT) -> str:
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


def _combined_agent_output(mode: str, results: dict[str, AgentResult]) -> str:
    titles = {
        "architect": "Strategy Architect",
        "challenger": "Cost and Execution Challenge",
        "validator": "Validation Notes",
    }
    sections = [f"# Strategy Analysis\n\nSelected mode: **{mode.replace('_', ' ').title()}**"]
    for key, title in titles.items():
        if results[key].ok:
            sections.append(f"## {title}\n\n{results[key].content}")
    sections.append(
        "## Synthesis Note\n\nThe final synthesis step was not available. The sections above preserve the successful agent outputs directly."
    )
    return "\n\n".join(sections)


async def safe_complete(agent, system: str, user: str, max_tokens: int = 4000) -> AgentResult:
    name = getattr(agent, "name", agent.__class__.__name__)
    try:
        return await asyncio.wait_for(agent.complete(system, user, max_tokens=max_tokens), timeout=AGENT_TIMEOUT_SECONDS)
    except asyncio.TimeoutError:
        return AgentResult(agent=name, content=f"Timed out after {AGENT_TIMEOUT_SECONDS}s", ok=False)
    except Exception as exc:
        return AgentResult(agent=name, content=str(exc) or exc.__class__.__name__, ok=False)


async def analyze_document(
    settings: Settings,
    mode: str,
    instruction: str,
    document_text: str,
    thinking_mode: bool = True,
    provider: str = "ibm_ica",
) -> dict:
    mode = mode if mode in MODE_INSTRUCTIONS else "give_suggestions"
    provider = normalize_provider(provider)
    agents = build_provider_agents(settings, provider, thinking_mode=thinking_mode)
    clipped_doc = _clip(document_text)
    truncated = len(document_text) > len(clipped_doc)

    system = dedent(
        """
        You are a senior data architecture, information management, and transformation strategy advisor.
        Be constructive and precise. Do not invent slide numbers or facts. The document text contains
        [Page N] / [Slide N] markers; cite them when you reference specific content, and only cite markers that exist.
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

    architect, challenger, validator = await asyncio.gather(
        safe_complete(agents["architect"], system, base_user + "\n\nThink deeply before answering. Focus on target-state journey, interim choices, and where subtle changes unlock better outcomes.", max_tokens=9000),
        safe_complete(agents["challenger"], system, base_user + "\n\nChallenge the plan from cost, cloud infrastructure, implementation effort, and faster turnaround perspectives. Only raise points that materially improve execution.", max_tokens=5500),
        safe_complete(agents["validator"], system, base_user + "\n\nProduce a validation checklist and call out weak assumptions.", max_tokens=3500),
    )
    results = {"architect": architect, "challenger": challenger, "validator": validator}
    trace = [architect.to_dict(), challenger.to_dict(), validator.to_dict()]
    notes: list[str] = []
    if truncated:
        notes.append(f"Document is {len(document_text):,} characters; only the first {ANALYSIS_DOC_LIMIT:,} were analysed.")

    successful = [(label, r) for label, r in (
        ("Anthropic-style analysis", architect),
        ("Cost/execution challenge", challenger),
        ("Validator notes", validator),
    ) if r.ok]

    if successful:
        # Failed agents are excluded so raw error strings never reach the synthesizer.
        inputs = "\n\n".join(f"{label}:\n{r.content}" for label, r in successful)
        synthesis_prompt = dedent(
            f"""
            Produce the final response for the user in Markdown.

            Requirements:
            - Use bullet points where helpful.
            - Include document page/slide references only when supported by the extracted text.
            - Include suggestions for final objective, implementation cost, faster turnaround, and cloud infrastructure cost savings.
            - Explain why each suggestion is better than the likely default.
            - Acknowledge strong existing material instead of forcing changes.
            - Do not mention which analyst produced which point.

            {inputs}
            """
        ).strip()
        final = await safe_complete(agents["synthesizer"], system, synthesis_prompt, max_tokens=7000)
        trace.append(final.to_dict())
        failed = [r.agent for r in (architect, challenger, validator) if not r.ok]
        if failed:
            notes.append("Some agents failed and were excluded: " + ", ".join(failed) + ".")
        if final.ok:
            return {"content": final.content, "agents": trace, "provider": provider, **({"warning": " ".join(notes)} if notes else {})}
        notes.append("Final synthesis was unavailable; returned the successful agent outputs directly.")
        return {"content": _combined_agent_output(mode, results), "agents": trace, "provider": provider, "warning": " ".join(notes)}

    notes.append("External model calls failed or were not configured; returned local fallback analysis.")
    return {
        "content": _fallback(mode, instruction, document_text),
        "agents": trace,
        "provider": provider,
        "warning": " ".join(notes),
    }


async def chat_about_analysis(
    settings: Settings,
    question: str,
    document_text: str,
    analysis: str,
    history: list[dict[str, str]] | None = None,
    provider: str = "ibm_ica",
) -> dict:
    provider = normalize_provider(provider)
    agents = build_provider_agents(settings, provider, thinking_mode=False)
    system = dedent(
        f"""
        You answer follow-up questions about a document analysis. Be concise, evidence-led, and practical.
        Cite [Page N] / [Slide N] markers only when they exist in the document text.

        Existing analysis:
        {analysis[:CHAT_ANALYSIS_LIMIT]}

        Document text:
        {document_text[:CHAT_DOC_LIMIT]}
        """
    ).strip()

    turns = [
        {"role": m["role"], "content": m["content"]}
        for m in (history or [])
        if m.get("role") in {"user", "assistant"} and m.get("content")
    ][-CHAT_HISTORY_TURNS * 2:]
    messages = turns + [{"role": "user", "content": question}]

    async def _ask(agent) -> AgentResult:
        name = getattr(agent, "name", agent.__class__.__name__)
        try:
            if hasattr(agent, "chat_messages"):
                coro = agent.chat_messages(system, messages, max_tokens=3000)
            else:  # single-turn providers: flatten the history into one prompt
                transcript = "\n\n".join(f"{m['role'].title()}: {m['content']}" for m in messages)
                coro = agent.complete(system, transcript, max_tokens=3000)
            return await asyncio.wait_for(coro, timeout=AGENT_TIMEOUT_SECONDS)
        except asyncio.TimeoutError:
            return AgentResult(agent=name, content=f"Timed out after {AGENT_TIMEOUT_SECONDS}s", ok=False)
        except Exception as exc:
            return AgentResult(agent=name, content=str(exc) or exc.__class__.__name__, ok=False)

    # synthesizer first, validator as backup (both Azure on SAP, both ICA on ICA)
    primary = await _ask(agents["synthesizer"])
    if primary.ok:
        return {"content": primary.content, "agents": [primary.to_dict()], "provider": provider}
    backup = await _ask(agents["validator"])
    if backup.ok:
        return {"content": backup.content, "agents": [primary.to_dict(), backup.to_dict()], "provider": provider}
    return {
        "content": "I could not reach the configured model endpoints for this follow-up. Please check backend environment variables and try again.",
        "agents": [primary.to_dict(), backup.to_dict()],
        "provider": provider,
    }
