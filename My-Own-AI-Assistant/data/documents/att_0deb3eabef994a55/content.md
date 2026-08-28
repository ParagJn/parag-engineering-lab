# Control_Framework_-_Upgrade-ROM_Statement_of_Work.docx

**Type:** application/vnd.openxmlformats-officedocument.wordprocessingml.document

---

Statement of Work

Control Framework - Upgrade-ROM

# Statement of Work: Control Framework - Upgrade-ROM

Customer: Ausnet

Project Name: Control Framework - Upgrade-ROM

Document Type: Statement of Work (SoW)

---

1.1 Background and Context

Ausnet's Data & Analytics (DnA) platform relies on a Control Framework that orchestrates approximately 600 Python-based data processing jobs across integrated systems, databases, and scheduling components (Control-M). This framework is the backbone of data ingestion, transformation, and delivery operations that support critical business intelligence and analytics capabilities across the organization. Over time, the underlying Python runtime, associated libraries, and orchestration tooling have aged, with several components approaching or reaching end-of-life status.

Continuing to operate on legacy Python versions and outdated libraries exposes Ausnet to increasing operational, security, and compatibility risks. Deprecated libraries can introduce vulnerabilities, and unsupported runtimes create technical debt that impedes future enhancements. Additionally, integration with newer systems and modern data platforms becomes progressively challenging as the technology stack falls behind current standards.

This project — the Control Framework Upgrade (Upgrade-ROM) — has been initiated to modernize the Python runtime environment (targeting Python 3.14.x, subject to confirmation at project commencement), refresh dependent libraries, replace deprecated libraries with modern equivalents, and validate that all ~600 Python jobs continue to function correctly post-upgrade. Control-M scheduler upgrades and dependent orchestration components are also within scope.

The engagement is scoped as a version-upgrade activity only, with no changes to business logic. The upgrade will follow a "big bang" deployment strategy — as recommended by Ausnet — to ensure the legacy Python runtime can be fully decommissioned and the upgrade validated cleanly, reducing risk of dual-version operation.

---

1.2 Scope

1.2.1 Python Runtime and Library Upgrade

Scope Overview

This scope covers the upgrade of the Python runtime that underpins the Control Framework to the agreed target version (recommended: Python 3.14.x), along with associated library upgrades, deprecated library replacements, and remediation of compatibility issues surfaced by the version change.

Scope of Work

Confirm target Python version at project commencement in collaboration with Ausnet BAU/DnA team

Compile inventory of Python jobs (~600) and shared code modules leveraging BAU-provided breakdown

Compile inventory of dependent Python libraries, including identification of deprecated / end-of-life libraries (list to be extracted by BAU team)

Upgrade libraries to versions compatible with target Python runtime

Replace deprecated libraries with supported equivalents (like-for-like functionality; no business logic changes)

Remediate syntax, API, and compatibility issues introduced by the Python version upgrade

Update shared code modules referenced by multiple jobs

Key Outcomes

All ~600 Python jobs successfully compiled and executing on the target Python version

Zero deprecated / end-of-life libraries remaining in the upgraded environment

Documented list of library upgrades and replacements

Legacy Python version fully decommissioned post-cutover

1.2.2 Control-M and Integration Component Alignment

Scope Overview

This scope covers alignment of Control-M scheduled jobs, associated shell scripts, cron entries, database connectivity, and integrating systems with the upgraded Python environment.

Scope of Work

Review Control-M job definitions calling Python programs and update interpreter paths / references as required

Review associated cron jobs and shell scripts wrapping Python execution

Validate database connectivity (drivers, connectors) under the upgraded runtime

Validate connectivity to integrating systems referenced by the Control Framework

Reference the Control Framework design and Job ID Ranges documentation on Confluence to ensure coverage

Key Outcomes

Control-M and associated schedulers correctly invoking upgraded Python jobs

Database and integration connectivity fully validated

No orphaned or misconfigured job references post-upgrade

1.2.3 Testing and Validation

Scope Overview

This scope covers technical and functional validation of the upgraded Control Framework, including regression testing of data loads and informal observation of performance characteristics.

Scope of Work

Develop Test Plan and Test Cases covering unit, system, and regression testing

Execute technical validation — each Python job executes to completion without error

Execute functional validation — data loads produce expected outputs (in consultation with BAU team, referencing Job ID Ranges)

Monitor performance during regression testing; investigate any significant degradation

Capture defects, remediate, and re-test

Produce Test Summary Reports per phase

Support User Acceptance Testing (UAT) executed by Ausnet BAU team

Key Outcomes

All jobs pass technical and functional regression testing

Signed-off Test Summary Reports per phase

No unresolved High/Critical defects at deployment

Ausnet BAU team acceptance obtained

1.2.4 Deployment and Transition

Scope Overview

This scope covers the big-bang deployment of the upgraded Control Framework into production, followed by hypercare and transition back to BAU operations.

Scope of Work

Develop Deployment Plan and Deployment Run Sheet

Coordinate deployment window with Ausnet stakeholders

Execute big-bang production cutover

Decommission the legacy Python runtime post-successful validation

Provide hypercare support for a defined stabilization window

Deliver As-Built documentation, Operational Manual, and Release Notes

Transition to Ausnet BAU DnA team; conduct Post-Implementation Review

Key Outcomes

Successful production cutover with no rollback required

Legacy runtime fully removed

BAU team operating the upgraded framework independently

Formal project closure with Service Acceptance signed

---

1.3 Out of Scope

---

1.4 Deliverables and Work Products

---

1.5 Risks

---

1.6 Dependencies

---

1.7 RACI Matrix

---

*End of Statement of Work*