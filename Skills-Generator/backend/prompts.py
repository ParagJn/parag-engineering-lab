"""
Prompt templates sent to the IBM ICA model.

Templates use {{placeholder}} tokens filled by render() — plain str.format
would choke on the JSON and ${CLAUDE_SKILL_DIR} examples inside them.
"""

PLATFORM_NAMES = {
    "anthropic": "Claude Code (Agent Skills folder with SKILL.md)",
    "gemini": "Gemini CLI (Agent Skills folder with SKILL.md)",
    "chatgpt": "OpenAI ChatGPT (Custom GPT instructions)",
}


def platform_name(platform: str) -> str:
    return PLATFORM_NAMES.get(platform, platform)


def render(template: str, **values) -> str:
    for key, value in values.items():
        template = template.replace("{{" + key + "}}", str(value))
    return template


# ---------------------------------------------------------------------------
# Shared authoring guide (condensed from Anthropic's skill best practices)
# ---------------------------------------------------------------------------

AUTHORING_GUIDE = """## How good skills are written

**Discovery.** Only `name` and `description` are pre-loaded; Claude reads SKILL.md only when the description matches the task. So the description must say WHAT the skill does AND WHEN to use it, in third person, with the concrete words a user would type ("Use when the user asks to…, mentions…, or works with…"). Never "I can…" or "You can…".

**Concise.** Claude is already smart. Only add context it doesn't have: domain rules, exact formats, decision criteria, gotchas. No filler, no motivational text, no explaining what a PDF is.

**Degrees of freedom.** Fragile or exact tasks (file formats, calculations, migrations) → exact steps and scripts, "run exactly this". Judgement tasks (writing, review, analysis) → heuristics, criteria and examples, not rigid scripts.

**Progressive disclosure.** SKILL.md is the overview and workflow (under 500 lines, ideally under 200). Put detailed material in separate files and link each one DIRECTLY from SKILL.md with a markdown link and a note on WHEN to read it, e.g. "For the scoring rubric, see [reference/rubric.md](reference/rubric.md)". Never nest references (a reference file must not send Claude to yet another file). Any reference file over 100 lines starts with a "## Contents" list.

**Workflows.** Break multi-step work into numbered steps with a copyable checklist:
```
Progress:
- [ ] Step 1: …
- [ ] Step 2: …
```
Add feedback loops for quality-critical work: do → validate (script or checklist) → fix → re-validate, and only then continue.

**Templates and examples.** When output format matters, give an exact template (strict: "ALWAYS use this structure") or a flexible default. Show 1–3 concrete input → output examples.

**Scripts (when they add reliability).** Use a script for anything deterministic, repetitive or error-prone (parsing, validating, transforming, computing, scaffolding). Scripts:
- Are complete and runnable. No placeholders, TODOs or "implement here".
- Start with a shebang, take arguments via argparse / "$1" / process.argv, and print `--help` usage.
- Solve problems rather than punt to Claude: handle errors explicitly and print clear, actionable messages to stderr with a non-zero exit code.
- Prefer the standard library. If a package is needed, say so in SKILL.md ("Requires: `pip install pypdf`").
- Contain no magic numbers without a comment explaining the value.
- Print structured, easy-to-read results (JSON or clear lines) that Claude can act on.
In SKILL.md, reference scripts with `${CLAUDE_SKILL_DIR}/scripts/<file>` and make the intent explicit: "Run `python3 ${CLAUDE_SKILL_DIR}/scripts/check.py input.md`" (execute) vs "See scripts/x.py for the algorithm" (read). State what the output looks like and what to do with it.

**Style.** Forward slashes in every path. One term per concept, used consistently. No dates or "currently" statements that will go stale. Imperative voice ("Read…", "Run…", "Ask…").
"""

CLAUDE_CODE_FRONTMATTER = """## Frontmatter available on Claude Code

Required: `name` (lowercase-hyphen, ≤64 chars, no "anthropic"/"claude", should equal the folder name; gerund form preferred e.g. `reviewing-pull-requests`), `description` (≤1024 chars, third person, what + when, no XML tags).

Optional, use only when they help:
- `when_to_use`: extra trigger phrases / example requests.
- `argument-hint`: shown in autocomplete, e.g. `[file] [format]`.
- `arguments`: list of named positional args, e.g. `[file, format]` → use `$file`, `$format` in the body. Or use `$ARGUMENTS` (all args) / `$0`, `$1`.
- `disable-model-invocation: true`: only the user can run it via /name (use for actions with side effects: deploy, commit, send, delete).
- `user-invocable: false`: hidden from the / menu; background knowledge Claude loads automatically.
- `allowed-tools`: tools pre-approved while the skill is active, e.g. `Read Grep Bash(python3 ${CLAUDE_SKILL_DIR}/scripts/*)`. Keep it minimal and scoped.

Substitutions in the body: `$ARGUMENTS`, `$0…$N`, named `$arg`, `${CLAUDE_SKILL_DIR}` (the skill folder), `${CLAUDE_PROJECT_DIR}`.
"""

SPEC_ONLY_FRONTMATTER = """## Frontmatter for this platform

Use ONLY these fields: `name` (lowercase-hyphen, ≤64 chars, no "anthropic"/"claude", equal to the folder name; gerund form preferred), `description` (≤1024 chars, third person, what + when, no XML), and optionally `license`, `compatibility`, `metadata`, `allowed-tools`. Do NOT use Claude Code-only fields (arguments, argument-hint, disable-model-invocation, user-invocable, when_to_use, model, context, …). Refer to scripts with paths relative to the skill folder, e.g. `scripts/check.py`.
"""

INVOCATION_HINTS = {
    "auto": "Claude may load it automatically when relevant AND the user can run it as /name. Use default invocation settings.",
    "slash-only": "Only the user runs it as /name <args> (set `disable-model-invocation: true`), with `argument-hint` and `$ARGUMENTS`/named arguments.",
    "background": "Background knowledge only: Claude loads it automatically when relevant; hide it from the / menu (`user-invocable: false`).",
}

SCRIPT_HINTS = {
    "auto": "Include scripts only where they make results more reliable (deterministic checks, parsing, transforming, computing). A pure judgement/writing skill may have none, but a validation/checker script is often valuable.",
    "yes": "Include at least one genuinely useful executable script (e.g. a validator/checker for the output, a parser, a generator).",
    "no": "Do not include any scripts; use reference files, templates and checklists instead.",
}

# ---------------------------------------------------------------------------
# Step 1 — blueprint
# ---------------------------------------------------------------------------

BLUEPRINT_PROMPT = """You are an expert Agent Skills architect. Design a skill bundle for **{{platform}}** from the user's idea. Do not write the files yet — produce the blueprint.

{{guide}}

{{frontmatter}}

## Choices the user made
- Invocation: {{invocation}}
- Scripts: {{scripts}}
- Preferred script language: {{language}}

## Bundle layout options
- `SKILL.md` (required): frontmatter + overview + workflow + links.
- `reference/<topic>.md`: detailed rules, rubrics, domain knowledge, API notes (loaded on demand).
- `examples.md`: input → output examples.
- `templates/<file>`: output templates (markdown/json/etc).
- `scripts/<file>.py|.sh|.js`: executable helpers.
- `evals/evals.json`: exactly 3 realistic test scenarios (always included).

Only plan files that earn their place. Keep the bundle small and focused (typically 3–8 files).

## Output
Return ONLY a JSON object (no code fence, no commentary) with this shape:
{
  "name": "gerund-kebab-case-name",
  "description": "Third-person what + when, ≤1024 chars, with concrete trigger words.",
  "when_to_use": "Optional extra trigger phrases (Claude Code only, else empty string)",
  "freedom": "low | medium | high — and one sentence why",
  "invocation": {"mode": "auto | slash-only | background", "argument_hint": "[arg] or empty", "arguments": ["optional", "named", "args"]},
  "allowed_tools": ["minimal list, or empty"],
  "workflow": ["Step 1 …", "Step 2 …"],
  "files": [
    {"path": "SKILL.md", "purpose": "…"},
    {"path": "reference/…md", "purpose": "…", "when_to_read": "…"},
    {"path": "scripts/…", "purpose": "…", "usage": "python3 scripts/x.py <input>", "dependencies": ["stdlib only or package names"]},
    {"path": "evals/evals.json", "purpose": "3 eval scenarios"}
  ],
  "evals": [
    {"query": "A realistic user request", "expected_behavior": ["Observable behaviour 1", "…"]}
  ]
}

## User's idea
{{thought}}
"""

# ---------------------------------------------------------------------------
# Step 2 — write every file
# ---------------------------------------------------------------------------

BUNDLE_PROMPT = """You are an expert Agent Skills author. Write the complete skill bundle for **{{platform}}** following the blueprint exactly.

{{guide}}

{{frontmatter}}

## Blueprint
{{blueprint}}

## Original idea
{{thought}}

## Requirements
- `SKILL.md` starts with `---` on line 1 (YAML frontmatter), `name: {{name}}`, then the body: a title, a short overview, "Quick start", the numbered workflow with a copyable checklist, links to every other file saying when to read/run it, the output format, and key rules/gotchas.
- Every file listed in the blueprint is written in full. Every non-eval file is linked from SKILL.md. No references nested more than one level.
- Scripts are complete, runnable and production quality (argparse/--help, validation of inputs, clear errors, exit codes). They will be syntax-checked.
- `evals/evals.json` is a JSON array of 3 objects: {"skills": ["{{name}}"], "query": "…", "files": [], "expected_behavior": ["…", "…", "…"]}. Expected behaviours must be specific and observable in the response.
- No placeholders like "TODO", "…" or "[insert here]" anywhere.

## Output format — STRICT
Output every file in this exact delimited format and nothing else (no commentary, no outer code fence):

<<<FILE: SKILL.md>>>
(full file content)
<<<END FILE>>>
<<<FILE: reference/example.md>>>
(full file content)
<<<END FILE>>>
"""

SINGLE_FILE_PROMPT = """You are an expert prompt engineer. Turn the user's idea into a complete, high-quality instruction set for **{{platform}}** (it will be pasted as Custom GPT instructions, so it must be ONE self-contained file — no scripts or extra files).

## Blueprint
{{blueprint}}

## Requirements
- Start with `---` YAML frontmatter containing only `name: {{name}}` and `description:` (third person, what + when).
- Then: a title, the role and goal, a numbered workflow with checkpoints, decision rules / criteria, an exact output template, 1–2 short input → output examples, and constraints (what NOT to do). Put everything inline.
- Be concise and specific; no filler; no placeholders.

## Original idea
{{thought}}

## Output format — STRICT
<<<FILE: SKILL.md>>>
(full file content)
<<<END FILE>>>
"""

# ---------------------------------------------------------------------------
# Step 3 — repair after deterministic validation
# ---------------------------------------------------------------------------

REPAIR_PROMPT = """The skill bundle below failed automatic validation for **{{platform}}**. Fix EVERY error. Keep everything that already works; don't shorten or drop content unless an error requires it.

{{frontmatter}}

## Validation errors
{{errors}}

## Current bundle
{{bundle}}

## Output format — STRICT
Return the COMPLETE corrected bundle (all files, including unchanged ones) in the same format, and nothing else:
<<<FILE: path>>>
(full content)
<<<END FILE>>>
"""

# ---------------------------------------------------------------------------
# Usage guide
# ---------------------------------------------------------------------------

USAGE_NOTES_PROMPT = """Write a short, practical usage guide for this {{platform}} skill for someone new to skills.

Skill folder name: `{{name}}`
Files in the bundle: {{file_list}}

{{install_hint}}

Cover, in markdown with short sections and bullet points (under 300 words):
1. **What it does** — one or two sentences.
2. **Install** — where the folder goes.
3. **How to use it** — {{invoke_hint}} Give 2–3 example requests.
4. **Prerequisites** — anything the scripts need (python3, `pip install …`, node). Say "None" if nothing.
5. **Tips** — how to get the best results.

Output only the markdown.

## SKILL.md
{{skill_content}}
"""

INSTALL_HINTS = {
    "anthropic": "Install: this app syncs it to the project's `.claude/skills/{{name}}/`; the Install button copies it to `~/.claude/skills/{{name}}/` (all projects). The .zip can also be uploaded to claude.ai (Settings → Capabilities → Skills), though Claude Code-only frontmatter fields may need removing there.",
    "gemini": "Install: this app syncs it to the project's `.gemini/skills/{{name}}/`; it can also be copied to `~/.gemini/skills/{{name}}/`.",
    "chatgpt": "Install: copy the instructions into a Custom GPT's Instructions field (or Custom Instructions).",
}

# ---------------------------------------------------------------------------
# Evals — run each scenario with the skill loaded, then grade it
# ---------------------------------------------------------------------------

EVAL_RUN_SYSTEM = """You are an AI assistant running inside {{platform}}. The following skill has been triggered and loaded for this conversation. Follow its instructions exactly.

When the skill tells you to run a script, you cannot execute it in this test: read the script source below, state the exact command you would run, and reason about what it would output from the code. When it tells you to read a reference file, its content is included below.

=== LOADED SKILL: {{name}} ===
{{skill_content}}
=== END SKILL ===
"""

EVAL_GRADE_PROMPT = """You are a strict QA evaluator for AI skills. Grade the assistant's response against each expected behaviour. A behaviour passes only if the response clearly demonstrates it — be honest, not generous.

## User request
{{query}}

## Expected behaviours
{{behaviors}}

## Assistant response (skill loaded)
{{response}}

Return ONLY a JSON object (no code fence):
{"results": [{"behavior": "…", "pass": true, "reason": "one sentence"}], "overall_pass": true, "suggestions": ["concrete improvement to the SKILL files, if any"]}
"""
