# Databricks Runtime Upgrade.pdf

**Type:** application/pdf (scanned, 4 page(s))

_This PDF has no text layer (scanned or image-only). Each page was read by an image-reading model, so you are seeing its transcription, which may contain reading errors._

---

## Page 1

# Databricks Runtime Upgrade – Title Slide (Page 1 of 4)

This page is a title/cover slide in 16:9 landscape format with a white background. Large bold headline text is left-aligned in the left and centre of the slide. Along the right side, a decorative pattern of pale blue vertical rounded bars forms a staggered checkerboard layout, and part of it sits behind the headline text. The slide has no logos, charts, or other imagery.

## Transcribed Text

**DataBricks Runtime** *(bright blue, bold)*

**UPGRADED** *(very large, bold, dark navy, all caps)*

AusNet DnA Platform *(smaller, dark navy, regular weight)*

## Visual / Design Details

- **Headline line 1:** "DataBricks Runtime" is in a heavy sans-serif font in bright blue. The capitalization "DataBricks" appears exactly like this on the slide.
- **Headline line 2:** "UPGRADED" is the largest text on the slide. It is in a heavy sans-serif font in dark navy.
- **Subtitle:** "AusNet DnA Platform" sits below the headline in a smaller dark navy font.
- **Decorative pattern (right side):**
  - The pattern is made of groups of 5 thin, pale blue, vertical, round-ended bars.
  - The groups are arranged in 5 staggered rows, with 2 groups per row, for 10 groups in total.
  - The groups alternate between left and right offsets, which creates a checkerboard effect.
  - Some bars pass behind the "Runtime" and "UPGRADED" text.

*Inference:* This appears to be the cover page of a document or presentation about a Databricks Runtime version upgrade on AusNet's Data and Analytics (DnA) platform.

## Page 2

# Page 2: Solution Approach (Technical Strategy)

This page is a presentation-style slide with a white background. At the top is a small blue, letter-spaced label, "TECHNICAL STRATEGY", followed by a large dark navy heading, "Solution Approach". Below the heading is a row of three light-grey rounded cards. Each card has a small blue icon in a pale blue circle, a bold title and a short description.

At the bottom is a larger light-grey rounded panel titled "Scope of Work". It shows three numbered steps in blue circles, arranged left to right.

---

**TECHNICAL STRATEGY**

# Solution Approach

## Cards (top row)

| Icon | Title | Description |
|---|---|---|
| Code symbol `</>` | **Runtime Modernisation** | Spark 3.2 → 4.0, Python 3.8 → 3.12, Scala 2.12 → 2.13 with full API compatibility validation |
| Git branch/merge symbol | **Blue-Green Deploy** | Parallel runtime clusters with instant rollback capability — zero downtime, zero data loss |
| Checked checkbox | **6-Category Remediation** | 32 notebooks fixed across API changes, connector migration, syntax and config updates |

## Scope of Work

The three steps are arranged in a left-to-right sequence:

1. **Assessment**: 225 production notebooks scanned for breaking changes across Spark, Python and Scala
2. **Remediation**: 32 notebooks updated — EventHub → Kafka migration, deprecated API replacement, config alignment
3. **Validation**: Full regression across Dev, Test and Prod with 100% pass rate and zero Sev 1 - 4 defects

## Page 3

This is a presentation slide (page 3 of 4) from a document titled "Databricks Runtime Upgrade." It has a white background, a small blue uppercase eyebrow label, and a large dark navy headline. Below the headline are six light-grey rounded cards in a 3×2 grid. Each card has a blue vertical accent bar on its left edge, a numbered blue circle (1–6), a bold dark heading, and a short description. The cards describe categories of changes made during the upgrade remediation.

---

**REMEDIATION FRAMEWORK**

# Six Categories of Change

### Row 1

**1: API Breaking Changes**
Deprecated Spark 3.x APIs replaced with Spark 4.0 equivalents across DataFrame and SQL operations

**2: Connector Migration**
EventHub connector deprecated — 11 notebooks migrated to Kafka-based streaming API

**3: Syntax Updates**
Python 3.12 syntax enforcement — f-string changes, type hint updates and deprecation removals

### Row 2

**4: Config Alignment**
Spark config keys renamed or removed in 4.0 — cluster policies and job configs updated

**5: Scala Cross-Build**
Scala 2.12 → 2.13 migration with binary-incompatible library rebuilds and import fixes

**6: Security Patches**
Credential handling and secret scope access patterns updated to current Databricks standards

---

| # | Category | Description |
|---|----------|-------------|
| 1 | API Breaking Changes | Deprecated Spark 3.x APIs replaced with Spark 4.0 equivalents across DataFrame and SQL operations |
| 2 | Connector Migration | EventHub connector deprecated — 11 notebooks migrated to Kafka-based streaming API |
| 3 | Syntax Updates | Python 3.12 syntax enforcement — f-string changes, type hint updates and deprecation removals |
| 4 | Config Alignment | Spark config keys renamed or removed in 4.0 — cluster policies and job configs updated |
| 5 | Scala Cross-Build | Scala 2.12 → 2.13 migration with binary-incompatible library rebuilds and import fixes |
| 6 | Security Patches | Credential handling and secret scope access patterns updated to current Databricks standards |

## Page 4

**Overview:** This is page 4 of a presentation-style PDF titled "Databricks Runtime Upgrade." The slide is a go-live summary titled "Upgrade at a Glance." It has a white background with faint pale-blue vertical rounded bar patterns. At the top is a row of three KPI cards. The first card is bright blue with white text; the other two are light grey. Below the KPI row are two large light-grey panels. The left panel covers "What We Delivered" and "Business Outcomes." The right panel covers "Challenges Overcome," with each item in a pale yellow box marked by an orange warning icon.

---

GO-LIVE SUMMARY *(small blue uppercase label)*

# Upgrade at a Glance

## Key Metrics

| Metric | Value | Card styling |
|---|---|---|
| TEST PASS RATE | 100% | Blue card, white text |
| NOTEBOOKS VALIDATED | 225 | Grey card, value in blue |
| OUTSTANDING DEFECTS | 0 | Grey card, value in green |

---

## What We Delivered
*(Each item is marked with a blue arrow "→".)*

- → Spark 3.2 → 4.0, Python 3.8 → 3.12, Scala 2.12 → 2.13
- → 32 notebooks remediated across 6 change categories
- → Blue-green deployment with proven rollback capability
- → Zero data loss, zero business disruption

## Business Outcomes
*(Each item is marked with a green circled checkmark.)*

- ✅ Modern LTS runtime with extended support
- ✅ Photon-enabled clusters for faster queries
- ✅ Security and compliance posture restored

---

## Challenges Overcome
*(Each item appears in a pale yellow box with an orange warning-triangle icon ⚠.)*

- ⚠ Environment sync issues between Dev, Test and Prod delayed code promotion by 7 days
- ⚠ Oracle and SQL Server connectivity required IT escalation across environments
- ⚠ EventHub connector deprecated — migrated 11 notebooks to Kafka API
- ⚠ 5 pre-existing production issues identified and isolated from project scope