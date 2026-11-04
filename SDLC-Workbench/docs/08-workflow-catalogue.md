# 08 · Workflow catalogue

> Generated from `backend/app/phases/definitions/*.yaml` by `scripts/render_catalogue.py`. **Do not edit by hand:**
> change the YAML, then run the script. A test fails if this file and the YAML disagree.

The lifecycle has 7 phases and 28 artefacts, 17 of them required, 5 of them not enabled, 2 done by hand. A **required**
artefact cannot be switched off in the wizard and must have content before its phase can be approved. An
artefact in a later **wave** waits for the ones in earlier waves; everything inside a wave runs in parallel.
An artefact that is **not enabled** is part of the design but never runs, is never required and is never reviewed; its reason is given
under its phase, and it can be switched on later by changing its definition and adding its skill.
An artefact **done by hand** (the deployment verification) has no agent and no skill: a person works through it, it is never run, and approval does not wait for it.
Deploy and BAU Handover are this prototype's own design; the source material stops at Code & Test.

## At a glance

| # | Phase | Approver | Artefacts | Required | Parallel waves |
| --- | --- | --- | --- | --- | --- |
| 0 | Setup | business engineer | 1 | 1 | 1 |
| 1 | Requirements | business engineer | 7 | 6 | 4 |
| 2 | Design | business engineer | 3 | 2 | 3 |
| 3 | Architecture | technical lead | 5 | 3 | 3 |
| 4 | Build & Test | technical lead | 1 | 1 | 1 |
| 5 | Deploy | deployment engineer | 2 | 2 | 2 |
| 6 | BAU handover | BAU lead | 2 | 2 | 2 |

## 0 · Setup

Agree what is being built, for whom, and how the project will run.  
Approved by: **business engineer**.

| Artefact | Required | Wave | Waits for | Agent role | ID prefix | What it is |
| --- | --- | --- | --- | --- | --- | --- |
| Project charter | yes | 1 | - | orchestrator | SET-CHR | Scope, goals, constraints, stakeholders and how success will be judged. |

## 1 · Requirements

Capture who the product is for and what it must do.  
Approved by: **business engineer**.

| Artefact | Required | Wave | Waits for | Agent role | ID prefix | What it is |
| --- | --- | --- | --- | --- | --- | --- |
| Personas | yes | 1 | - | requirements_analyst | REQ-PER | Who will use the product and what each of them needs. |
| Problem statement | yes | 1 | - | requirements_analyst | REQ-PRB | The problem being solved, in the users' words, and why it matters. |
| Vision and objectives | yes | 2 | Problem statement | requirements_analyst | REQ-VIS | Where the product is heading and the measurable objectives that say it got there. |
| Functional requirements | yes | 2 | Personas, Problem statement | requirements_analyst | REQ-F | What the product must do, one numbered requirement at a time. |
| Non-functional requirements | yes | 2 | Problem statement | requirements_analyst | REQ-NF | Performance, security, availability and the other qualities the product must have. |
| Epics and features | yes | 3 | Functional requirements, Non-functional requirements | requirements_analyst | REQ-EPC | Requirements grouped into epics and features that can be planned and built. |
| User stories | no | 4 | Epics and features | backlog_splitter | REQ-US | Features broken down into small stories with acceptance criteria. |

## 2 · Design

Work out how people will use the product, before deciding how it is built.  
Approved by: **business engineer**.

| Artefact | Required | Wave | Waits for | Agent role | ID prefix | What it is |
| --- | --- | --- | --- | --- | --- | --- |
| User journey | yes | 1 | - | ux_designer | DES-UJ | How each persona moves through the product to get something done. |
| Low-fidelity wireframes | yes | 2 | User journey | ux_designer | DES-LF | Rough layouts of each screen, to agree structure before visual design. |
| High-fidelity wireframes | no | 3 | Low-fidelity wireframes | ux_designer | DES-HF | Detailed, styled screens ready for the front-end build. |

## 3 · Architecture

Decide the parts of the system, how they fit together, and the detail needed to build them.  
Approved by: **technical lead**.

| Artefact | Required | Wave | Waits for | Agent role | ID prefix | What it is |
| --- | --- | --- | --- | --- | --- | --- |
| Component overview | yes | 1 | - | solution_architect | ARC-CMP | The main parts of the system and what each one is responsible for. |
| High-level design | yes | 2 | Component overview | solution_architect | ARC-HLD | How the parts fit together, with data, interfaces, technology choices and key decisions. |
| Low-level design | yes | 3 | High-level design | solution_architect | ARC-LLD | Endpoints, tables and rules detailed enough to build from. |
| Flow diagram | no | 3 | High-level design | diagram_author | ARC-FLW | A diagram of how a request and its data move through the system. |
| Use-case diagram | no | 2 | Component overview | diagram_author | ARC-UCD | A diagram of who does what with the system. |

## 4 · Build & Test

Write the instruction files a person gives to a coding tool (Copilot, Claude, GPT or Gemini) so that tool builds the application. This system does not write the application.  
Approved by: **technical lead**.

| Artefact | Required | Wave | Waits for | Agent role | ID prefix | What it is |
| --- | --- | --- | --- | --- | --- | --- |
| Build instructions | yes | 1 | - | solution_architect | BLD-INS | One set of Markdown instruction files for a coding tool - a foundation file, one file for each use case, and the acceptance tests - each pointing at the design items it builds. |

## 5 · Deploy

Plan the release, say what is in it, and check by hand that it worked.  
Approved by: **deployment engineer**.

| Artefact | Required | Wave | Waits for | Agent role | ID prefix | What it is |
| --- | --- | --- | --- | --- | --- | --- |
| Deployment plan | yes | 1 | - | devops_engineer | DEP-PLN | Where it runs, in what order things happen, and how to go back if it goes wrong. |
| Release notes | yes | 2 | Deployment plan | devops_engineer | DEP-REL | What is in this release, in words the business can read. |

**Done by hand** (no agent, no skill; a person works through it):

| Artefact | ID prefix | What it is |
| --- | --- | --- |
| Deployment verification | DEP-VER | Checks a person works through by hand, with a go or no-go for each. No model is used. |

**Not enabled** (part of the design, never run):

| Artefact | Agent role | ID prefix | Why it is not enabled |
| --- | --- | --- | --- |
| Infrastructure as code | devops_engineer | DEP-IAC | Not enabled. The product is built and run outside this tool, so there is nothing for it to describe yet. It can be switched on later. |
| CI/CD pipeline | devops_engineer | DEP-CI | Not enabled. No automated build or release is wanted yet. It can be switched on later. |

## 6 · BAU handover

Hand the running product to the people who will support it day to day, and record that they accept it.  
Approved by: **BAU lead**.

| Artefact | Required | Wave | Waits for | Agent role | ID prefix | What it is |
| --- | --- | --- | --- | --- | --- | --- |
| Runbook | yes | 1 | - | handover_author | HND-RUN | Step-by-step instructions for operating and recovering the product. |
| Hypercare plan | yes | 2 | Runbook | handover_author | HND-HYP | Extra support in the first weeks after go-live, and when it ends. |

**Done by hand** (no agent, no skill; a person works through it):

| Artefact | ID prefix | What it is |
| --- | --- | --- |
| Handover sign-off | HND-SGN | Statements a named person accepts or does not accept, one by one, to record that support takes the product. No model is used. |

**Not enabled** (part of the design, never run):

| Artefact | Agent role | ID prefix | Why it is not enabled |
| --- | --- | --- | --- |
| Support guide | handover_author | HND-SUP | Not enabled. Not needed yet; the runbook covers day-to-day problems. It can be switched on later. |
| SLOs and alerts | handover_author | HND-SLO | Not enabled. No alerting is set up for a product built and run outside this tool. It can be switched on later. |
| Knowledge-transfer pack | handover_author | HND-KT | Not enabled. Not needed yet; the runbook and the sign-off cover what support must know. It can be switched on later. |
