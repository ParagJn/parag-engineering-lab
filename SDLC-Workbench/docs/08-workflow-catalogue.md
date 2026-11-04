# 08 · Workflow catalogue

> Generated from `backend/app/phases/definitions/*.yaml` by `scripts/render_catalogue.py`. **Do not edit by hand:**
> change the YAML, then run the script. A test fails if this file and the YAML disagree.

The lifecycle has 7 phases and 28 artefacts, 18 of them required. A **required**
artefact cannot be switched off in the wizard and must have content before its phase can be approved. An
artefact in a later **wave** waits for the ones in earlier waves; everything inside a wave runs in parallel.
Deploy and BAU Handover are this prototype's own design; the source material stops at Code & Test.

## At a glance

| # | Phase | Approver | Artefacts | Required | Parallel waves |
| --- | --- | --- | --- | --- | --- |
| 0 | Setup | business engineer | 1 | 1 | 1 |
| 1 | Requirements | business engineer | 7 | 6 | 4 |
| 2 | Design | business engineer | 3 | 2 | 3 |
| 3 | Architecture | technical lead | 5 | 3 | 3 |
| 4 | Build & Test | technical lead | 1 | 1 | 1 |
| 5 | Deploy | deployment engineer | 5 | 3 | 3 |
| 6 | BAU handover | BAU lead | 6 | 2 | 2 |

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

Get the tested product running somewhere, and prove it is running.  
Approved by: **deployment engineer**.

| Artefact | Required | Wave | Waits for | Agent role | ID prefix | What it is |
| --- | --- | --- | --- | --- | --- | --- |
| Deployment plan | yes | 1 | - | devops_engineer | DEP-PLN | Where it runs, in what order things happen, and how to go back if it goes wrong. |
| Infrastructure as code | yes | 2 | Deployment plan | devops_engineer | DEP-IAC | The container and infrastructure files that describe the environment. |
| Release notes | yes | 2 | Deployment plan | devops_engineer | DEP-REL | What is in this release, in words the business can read. |
| CI/CD pipeline | no | 2 | Deployment plan | devops_engineer | DEP-CI | The automated steps that build, test and release the product. |
| Deployment verification | no | 3 | Infrastructure as code | devops_engineer | DEP-VER | Checks run against the running product to show the release worked. |

## 6 · BAU handover

Hand the running product to the people who will support it day to day.  
Approved by: **BAU lead**.

| Artefact | Required | Wave | Waits for | Agent role | ID prefix | What it is |
| --- | --- | --- | --- | --- | --- | --- |
| Runbook | yes | 1 | - | handover_author | HND-RUN | Step-by-step instructions for operating and recovering the product. |
| Support guide | yes | 1 | - | handover_author | HND-SUP | How to triage and resolve the problems users are likely to report. |
| SLOs and alerts | no | 2 | Runbook | handover_author | HND-SLO | The service levels promised and the alerts that tell support when they are at risk. |
| Knowledge-transfer pack | no | 2 | Runbook, Support guide | handover_author | HND-KT | What the support team needs to learn, in the order they need to learn it. |
| Hypercare plan | no | 2 | Runbook | handover_author | HND-HYP | Extra support in the first weeks after go-live, and when it ends. |
| Handover sign-off | no | 2 | Runbook, Support guide | handover_author | HND-SGN | The record that support accepts the product, with who signed and when. |
