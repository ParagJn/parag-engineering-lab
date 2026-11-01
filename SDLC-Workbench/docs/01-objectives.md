# 01 · Vision and objectives

## Vision

Give a short project brief and some reference documents, and watch a team of specialised AI agents take it through requirements, design, architecture, build and test, deployment and BAU handover. Humans approve at each gate, every output is grounded in project context and traceable, and the result is a running application plus its handover pack.

## Objectives

Each objective has an ID that step specs and tests refer to.

| ID | Objective | Acceptance (how we know) |
|---|---|---|
| **O1** | **Full lifecycle.** Seven phases: Setup, Requirements, Design, Architecture, Build & Test, Deploy, BAU Handover, each with defined artefacts and an approval gate | One project runs end to end with no manual file shuffling; each phase shows its artefacts and gate status |
| **O2** | **Multi-agent, multi-model.** Role-specialised agents on Sonnet, Haiku, OpenAI and Gemini, routed by a config table | Every LLM call is tagged with agent + model; all four families are used in a normal run; changing the routing is a config edit, not a code edit |
| **O3** | **Visible review independence.** Sonnet reviews every artefact (user decision, 2026-10-27). Each review is labelled **independent** (author was OpenAI or Gemini) or **same family** (author was Sonnet or Haiku), never hidden. If the reviewer can't run, the user chooses another model family | Verdict computed in code from the author's *served* model and tested; reviewer findings and the label are shown on the artefact |
| **O4** | **Context-grounded.** Project context store with retrieval; agents cite what they used; approved artefacts are re-ingested | Each generated artefact lists its source chunks; an edit approved in phase N is retrievable in phase N+1 |
| **O5** | **Human in the loop.** Approve, reject with feedback, or edit directly; feedback is kept as project memory | Rejection triggers a re-run that includes the feedback; every version records who/what produced it |
| **O6** | **Parallel work.** Artefacts in a phase, and the DB/backend/frontend builds, run concurrently | Wall-clock for a phase is visibly less than the sum of its parts; no shared-state corruption (tested) |
| **O7** | **Real output.** The generated application builds, its generated tests run and pass, and the deployed app responds | Test run results come from actually executing the code, not from the model's claim |
| **O8** | **Traceability and governance.** IDs flow requirement → design → component → code → test → release; versioned artefacts; audit log | Traceability matrix view; coverage gaps are flagged (e.g. a requirement with no test) |
| **O9** | **Security guardrails.** Secret and PII scanning on all artefacts and code; a security review gate before deploy | A planted fake secret in a test fixture is caught; deploy is blocked until the gate passes |
| **O10** | **Observability and cost.** Trace of every call (agent, model, tokens, latency, cost) with a run inspector | Per-phase and per-model cost view; failed calls and retries visible |
| **O11** | **Configurable.** Phases, artefacts, agents and skills defined in YAML/Markdown | Adding an artefact type requires no Python change beyond (at most) a schema |
| **O12** | **Demoable.** Replay mode, one-click reset, guided run-of-show, clear real-vs-simulated labels | A cold start to a finished 15–20 min demo works offline with replay; the same flow works live with keys |
| **O13** | **Tested at every step.** Unit tests gate each step; no network in unit tests | `pytest` is green at the end of every step; a live smoke suite exists but is opt-in |

## Non-goals (explicitly out)

- Real SharePoint, Jira, Figma or GitHub integrations. Local stand-ins behind the same interface instead, labelled simulated.
- Real cloud deployment. Generate infrastructure-as-code and deploy to a local target; cloud apply is a dry run.
- Authentication, multi-tenancy, fine-grained RBAC. A few demo roles at most.
- Production-grade scale, HA, or hardening of the workbench itself. It is a prototype.
- Reproducing the source product's UI or branding.
- Claiming the source deck's productivity or team-size percentages as our results.

## Personas the demo speaks to

- **Business engineer / product owner:** writes the brief, reviews requirements and design.
- **Technical lead:** reviews architecture, code and test results.
- **Deployment engineer:** approves the release and the deploy.
- **BAU / support lead:** receives the handover pack and sees the incident loop.
- **FinOps:** looks at the cost-by-model view.
