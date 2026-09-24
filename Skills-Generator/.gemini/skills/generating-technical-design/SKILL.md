---
name: generating-technical-design
description: Analyzes a git repository codebase and produces exhaustive technical design documents (TDD) and architecture specifications. Use when the user asks to document repository architecture, generate technical design documents, reverse-engineer system architecture from code, map out APIs and component workflows, or create system flow diagrams with Mermaid.
---

# Generating Technical Design

This skill scans, reverse-engineers, and documents git repositories into production-ready Technical Design Documents (TDD) and architecture specifications with syntax-validated Mermaid diagrams.

## Quick Start

1. Scan repository structure and dependencies:
   ```bash
   python3 scripts/scan_repo.py . --output repo_summary.json
   ```
2. Read the generated `repo_summary.json` to identify languages, frameworks, entry points, and directory layout.
3. Review framework-specific patterns in [reference/analysis-heuristics.md](reference/analysis-heuristics.md).
4. Review Mermaid syntax standards in [reference/mermaid-conventions.md](reference/mermaid-conventions.md).
5. Load the target structure from [templates/technical-design-doc.md](templates/technical-design-doc.md) and generate the comprehensive TDD.

## Workflow

Progress:
- [ ] Step 1: Scan repository layout, entry points, and manifest files
- [ ] Step 2: Trace domain models, routes, services, and external integrations
- [ ] Step 3: Load design template and Mermaid diagramming conventions
- [ ] Step 4: Draft comprehensive TDD sections with verified code references
- [ ] Step 5: Validate Mermaid diagram syntax and cross-reference endpoints/models
- [ ] Step 6: Write finalized design document to the target markdown file

### Detailed Steps

#### Step 1: Automated & Manual Repository Discovery
Run the repository scanner:
```bash
python3 scripts/scan_repo.py <path_to_repo> --output repo_summary.json
```
Inspect `repo_summary.json` for:
- Identified language stacks and package managers (`package.json`, `pyproject.toml`, `go.mod`, `Cargo.toml`, `pom.xml`, `Gemfile`).
- Top-level directory topology and entry points (`main.go`, `index.ts`, `app.py`, `src/main.rs`).
- Core dependencies indicating databases (ORM/drivers), messaging (Kafka, RabbitMQ, SQS), web frameworks, and external clients.

#### Step 2: Deep Component and Interface Inspection
Consult [reference/analysis-heuristics.md](reference/analysis-heuristics.md) to locate and trace:
- **Routes & APIs:** HTTP methods, paths, request payloads, response codes, middleware guards.
- **Data Models:** Schemas, relational mappings, primary/foreign keys, migrations.
- **Asynchronous & Event Workflows:** Queues, topics, workers, retry strategies, dead-letter queues (DLQ).
- **External Dependencies:** Third-party APIs, storage buckets, caching layers (Redis/Memcached).

#### Step 3: Align with Standard Templates & Diagramming Rules
- Refer to [templates/technical-design-doc.md](templates/technical-design-doc.md) for the mandatory document sections.
- Refer to [reference/mermaid-conventions.md](reference/mermaid-conventions.md) before writing any Mermaid block (`graph TD`, `sequenceDiagram`, `erDiagram`, or `stateDiagram-v2`). Ensure entity names avoid special characters and arrow directions are consistent.

#### Step 4: Synthesize the Technical Design Document
Draft every section thoroughly without generic placeholders:
- **System Overview & Objectives:** Business domain, problem statement, core capabilities.
- **High-Level Architecture:** Block diagram (`graph TD`) mapping clients, gateways, application modules, datastores, and message buses.
- **Component Breakdown:** Detailed role, internal modules, inputs/outputs, and error handling for each component.
- **API & Interface Specifications:** Exhaustive endpoint tables with parameters, request/response structures, and authentication requirements.
- **Data Architecture & Schema:** Database models and Entity-Relationship diagram (`erDiagram`).
- **Core Workflows & Sequence Diagrams:** End-to-end request-response and background processing flows (`sequenceDiagram`).
- **Reliability, Security & Operational Considerations:** Authentication/Authorization, rate limiting, logging, observability, failure recovery, deployment strategy.

#### Step 5: Verification & Consistency Check
Verify that:
- Every documented endpoint and schema field exists in the target code.
- All Mermaid diagrams use valid syntax (properly escaped strings, defined participants, correct syntax keywords).
- No placeholder tokens (`TODO`, `TBD`, `...`) remain in the output.

#### Step 6: Write Output File
Save the document to the user-specified path (e.g., `docs/technical-design.md` or `docs/architecture.md`).

## Reference Files

- [templates/technical-design-doc.md](templates/technical-design-doc.md): Standard structural template for full technical design documents. Read when structuring the final output.
- [reference/mermaid-conventions.md](reference/mermaid-conventions.md): Strict syntax rules, entity naming standards, and clean patterns for Mermaid diagrams. Read before drafting diagrams.
- [reference/analysis-heuristics.md](reference/analysis-heuristics.md): Detection rules for routing, schemas, state management, and worker pipelines across major languages. Read when analyzing repository source code.
- `scripts/scan_repo.py`: Run `python3 scripts/scan_repo.py <path> --output <summary.json>` to extract file trees, package dependencies, and technology profiles.

## Rules & Gotchas

1. **Ground Truth Only:** Base all architecture statements on observed code, configuration files, and migrations. If an implementation detail is absent, explicitly document it as "Not implemented in current codebase" rather than inventing behavior.
2. **Mermaid Syntax Safety:** Always wrap node labels containing spaces, parentheses, or brackets in double quotes (e.g., `id1["API Gateway (/api/v1)"]`). Do not use raw colons, semicolons, or unescaped quotes inside Mermaid labels.
3. **Exhaustive Tables:** API specification tables must include explicit HTTP methods, route paths, request payloads/query params, and status codes.
4. **Concrete Data Models:** Document entity field types, nullability, and relations directly derived from schemas (ORM models, protobufs, JSON schemas, SQL migrations).
