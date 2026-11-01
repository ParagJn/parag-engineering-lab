# 00 · Analysis of the source deck

Source: a 10-slide consulting deck, "Software Development Life Cycle with Agentic AI" (Feb 2026), describing a product that automates the SDLC with coordinated AI agents. This file is paraphrased analysis for planning. It is background only and should stay out of the public repo unless the user decides otherwise.

## 1. What the deck argues

**Problem.** Delivery is slow and inconsistent for three reasons: manual coordination and hand-offs, fragmented tools per phase, and unstandardised artefacts with poor shared context.

**Claimed cost of the problem** (vendor figures, unsourced): ~70% of effort on low-complexity work, phases stretched by 2–20 days of manual alignment, production defects up to 100× costlier than ones caught at requirements/design.

**Claimed benefits** (vendor figures): large productivity gain, 30–40% smaller teams, 60–70% less effort. One tile reads "<70%", which is almost certainly a typo for "up to 70%". **Do not present any of these as results of our prototype.** The prototype should measure its own numbers (elapsed time, tokens, cost, human-edit rate).

## 2. The three pillars

| # | Pillar | Meaning |
|---|---|---|
| 1 | Unified multi-agent SDLC orchestration | Specialised agents per discipline, one environment, structured hand-offs, parallel execution, skills that mirror human roles |
| 2 | Context-grounded engineering | A "context studio" holds validated, continuously updated project knowledge; every agent output is grounded in it; approved artefacts are re-ingested |
| 3 | Human-in-the-loop within existing tools | People review, edit and approve in the tools they already use; refinements feed back into agent memory; AI and human inputs are both traceable |

## 3. Process model seen in the screens

Phases with an approval status chip (Approved / Review): **0 Setup → 1 Requirement → 2 Design → 3 Architecture → 4 Code & Test.**

| Phase | Artefacts |
|---|---|
| Requirement | personas, problem statements, vision/objectives, functional + non-functional requirements, epics/features |
| Design | user journey, low-fidelity wireframes, high-fidelity wireframes |
| Architecture | component overview, flow diagrams, use-case diagram, high-level design, low-level design |
| Code & Test | database repo, backend repo, frontend repo |

A 5-step project wizard configures a run: basic details → execution mode → agentic workflow (describe the project, tick which artefacts per phase) → context & tools → project connectors (tracker, document store, source control).

Control loop: app → backend starts the workflow → agentic backend executes → generated artefacts wait for approval → approved artefacts are re-ingested into the context store → next phase.

## 4. Architecture seen (slide 9), reduced to layers

- **Context layer:** document upload and ingestion pipelines, context assembly and retrieval, dynamic memory, knowledge-base management, exposed to agents through a gateway (MCP-style).
- **Orchestration runtime:** an orchestrator reads phase / process / prompt definitions and drives one agent per discipline (planning, design, architecture, development, devops, security). Planning/design/architecture use a deep-agent framework; development/devops/security use coding-agent models. Each agent has skills and a human-in-the-loop hook. A sandbox provides session isolation, filesystem, memory, shell and web search.
- **Tool layer (MCP gateway):** document store, tracker, design tool, source control, object storage, infrastructure-as-code.
- **Cross-cutting:** notifications (paging/chat), LLM observability and tracing, metering/FinOps, evaluation, DevSecOps, AI governance, data governance.
- **App layer:** web interface + REST API + background jobs on a customer-chosen hyperscaler.
- **Personas around the pipeline:** business engineers, technical engineers, FinOps engineers, deployment engineers.

Slide 4 draws the pipeline as Plan → Requirement → Design → Develop → Test → Deploy → Operate.

## 5. Gaps between the deck and what you asked for

| Your ask | Deck coverage | Consequence |
|---|---|---|
| Start → deployment | Detailed to Code & Test. Deploy/Operate appear only as pipeline stages plus a DevOps agent and an IaC tool | **Deploy phase must be designed by us** |
| BAU handover | Not covered at all | **Designed by us:** runbook, SLOs/alerts, KT pack, hypercare, sign-off, plus a "day-2 incident" loop back into change |
| Sonnet, Haiku, OpenAI, Gemini | Deck uses coding-agent models for dev/devops/security and a framework for the rest | **We define the routing** (see `03-agents-and-models.md`); all four reached through ICA |
| Demoable | Product screenshots only | **Needs replay mode, reset and a scripted run** (see `04-demo-scenario.md`) |
| Unit tests every step | n/a | Testing strategy in `06-testing-strategy.md` |

## 6. Keep / simulate / cut

| Keep (real) | Simulate (clearly labelled) | Cut |
|---|---|---|
| Phase state machine with approval gates | Document store, tracker and source-control connectors as local stand-ins behind the same interface | Real SharePoint / Jira / Figma / GitHub integration |
| Parallel artefact generation | Cloud deployment (generate IaC, deploy to a local target, dry-run the cloud apply) | Multi-tenant auth, RBAC beyond a few demo roles |
| Context store with retrieval, citations, re-ingest loop | Day-2 incident | Hyperscaler-specific hosting |
| Skills as editable files | Notifications feed | Third-party observability products (built-in traces instead) |
| Multi-model routing and cross-model review | | Pixel-matching the original UI |
| Generated app that actually builds and passes its own tests | | |
| Traces, token and cost metering | | |
| Versioned artefacts, audit trail, traceability IDs | | |

## 7. Ideas the deck implies but doesn't show, worth adding

1. **Visible review independence:** Sonnet reviews everything and each review says whether it was independent of the author's model family. (Originally "never the same family"; changed 2026-10-27 at the user's request.)
2. **Replay mode:** record LLM responses and replay them offline so the demo is fast, free and deterministic. Live mode stays available.
3. **Traceability matrix:** requirement → design → component → code → test → deployment, with IDs carried through every artefact.
4. **Real-vs-simulated badges** on every connector and step, for demo credibility.
