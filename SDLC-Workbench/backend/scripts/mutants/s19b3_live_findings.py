"""Deliberate breaks for the fixes that came from the first live run (2026-11-03): the live cost, the per-file download and folding, the acceptance size limit,
and the design inputs the use cases derive from.

Backend:  python -u -m scripts.mutation_check scripts/mutants/s19b3_live_findings.py --tests tests/test_compose.py tests/test_instructions.py tests/test_agent_skills.py
Frontend: python -u -m scripts.frontend_mutation_check scripts/mutants/s19b3_live_findings.py
"""
In = "app/build/instructions.py"
Sk = "app/phases/skills/build_instructions.md"

MUTANTS = [
    ("the acceptance file has the general limit", In, "    limit = MAX_ACCEPTANCE_CHARS if kind == ACCEPTANCE else MAX_FILE_CHARS", "    limit = MAX_FILE_CHARS"),
    ("every file has the acceptance limit", In, "    limit = MAX_ACCEPTANCE_CHARS if kind == ACCEPTANCE else MAX_FILE_CHARS", "    limit = MAX_ACCEPTANCE_CHARS"),
    ("the acceptance limit is 30,000", In, "MAX_ACCEPTANCE_CHARS = 40_000", "MAX_ACCEPTANCE_CHARS = 30_000"),
    ("the acceptance limit is 50,000", In, "MAX_ACCEPTANCE_CHARS = 40_000", "MAX_ACCEPTANCE_CHARS = 50_000"),
    ("the general limit is 25,000", In, "MAX_FILE_CHARS = 20_000", "MAX_FILE_CHARS = 25_000"),
    ("the set limit is too small", In, "SET_MAX_CHARS = 300_000", "SET_MAX_CHARS = 100_000"),
    ("the journey is not read", Sk, "- artefact: user_journey\n", ""),
    ("the personas are not read", Sk, "- artefact: personas\n", ""),
]

FRONTEND = [
    ("a file is shown open", "src/components/InstructionFiles.tsx", "<details className=\"rounded-lg border border-slate-200 bg-white\">", "<details open className=\"rounded-lg border border-slate-200 bg-white\">"),
    ("the files are not shown", "src/components/ArtefactReader.tsx", "{isInstructionSet(a.type) ? <InstructionFiles body={a.body} />", "{false ? <InstructionFiles body={a.body} />"),
    ("every artefact is shown as a set", "src/components/ArtefactReader.tsx", "{isInstructionSet(a.type) ? <InstructionFiles body={a.body} />", "{true ? <InstructionFiles body={a.body} />"),
    ("the download saves the whole set", "src/lib/instructionSet.ts", "return { name: instructionDownloadName(file.name), text: file.text }", "return { name: instructionDownloadName(file.name), text: file.name }"),
    ("the download uses the raw name", "src/lib/instructionSet.ts", "return { name: instructionDownloadName(file.name), text: file.text }", "return { name: file.name, text: file.text }"),
    ("the button does not use the download function", "src/components/InstructionFiles.tsx", "onClick={() => { const d = downloadOf(f); saveText(d.name, d.text) }}", "onClick={() => saveText(f.name, body)}"),
    ("the label does not use the saved name", "src/components/InstructionFiles.tsx", "const saveAs = downloadOf(f).name", "const saveAs = f.name"),
    ("the overview is not shown", "src/components/InstructionFiles.tsx", "{head.trim() && <SafeMarkdown>{head}</SafeMarkdown>}", ""),
    ("an empty set says nothing", "src/components/InstructionFiles.tsx", "{files.length === 0 && <p", "{false && <p"),
    ("a file's text is not rendered", "src/components/InstructionFiles.tsx", "<SafeMarkdown collapseCode>{f.text}</SafeMarkdown>", ""),
    ("the line count is missing", "src/components/InstructionFiles.tsx", "<span className=\"text-xs text-slate-500\">{count(lines, 'line')}</span>", ""),
    ("the mark must not be a whole line", "src/lib/instructionSet.ts", "const MARK = /^=== FILE: (\\S+) ===[ \\t]*$/", "const MARK = /=== FILE: (\\S+) ===/"),
    ("a mark may hold spaces", "src/lib/instructionSet.ts", "const MARK = /^=== FILE: (\\S+) ===[ \\t]*$/", "const MARK = /^=== FILE: (.+) ===[ \\t]*$/"),
    ("windows line ends are not read", "src/lib/instructionSet.ts", "(body ?? '').replace(/\\r\\n/g, '\\n')", "(body ?? '')"),
    ("a repeated file replaces the first", "src/lib/instructionSet.ts", "const keep = !seen.has(mark[1])", "const keep = true"),
    ("a file keeps its blank lines", "src/lib/instructionSet.ts", ".replace(/^\\n+|\\n+$/g, '') + '\\n'", " + '\\n'"),
    ("a file loses its final newline", "src/lib/instructionSet.ts", ".replace(/^\\n+|\\n+$/g, '') + '\\n'", ".replace(/^\\n+|\\n+$/g, '')"),
    ("the head keeps trailing blank lines", "src/lib/instructionSet.ts", "head: head.join('\\n').replace(/\\n+$/, '')", "head: head.join('\\n')"),
    ("the last file is dropped", "src/lib/instructionSet.ts", "  close()\n  return { head", "  return { head"),
    ("a safe name is rewritten", "src/lib/instructionSet.ts", "if (SAFE_NAME.test(name)) return name", "if (false) return name"),
    ("an unsafe name is kept", "src/lib/instructionSet.ts", "  const stem = name.replace(/\\.md$/i, '')", "  return name\n  const stem = name.replace(/\\.md$/i, '')"),
    ("the saved name may be empty", "src/lib/instructionSet.ts", "return `${stem || 'instructions'}.md`", "return `${stem}.md`"),
    ("a leading dot is kept", "src/lib/instructionSet.ts", ".replace(/^[._-]+/, '')", ""),
    ("the name is not cut", "src/lib/instructionSet.ts", ".slice(0, 70)", ""),
    ("the line count of an empty file is one", "src/lib/instructionSet.ts", "  if (!text) return 0\n", ""),
    ("a final newline counts as a line", "src/lib/instructionSet.ts", "return text.endsWith('\\n') ? text.split('\\n').length - 1 : text.split('\\n').length", "return text.split('\\n').length"),
    ("a file's cost is not counted while it works", "src/state/runProgress.ts", "  if (r.state === 'done') return r.costUsd\n  let sum = 0", "  if (r.state === 'done') return r.costUsd\n  return 0\n  let sum = 0"),
    ("a failed file's cost is counted", "src/state/runProgress.ts", "    if (x.state !== 'done') continue", "    if (x.state === 'writing') continue"),
    ("an unknown price counts as nothing", "src/state/runProgress.ts", "    if (x.costUsd === null) return null", "    if (x.costUsd === null) continue"),
    ("the artefact and its files are both counted", "src/state/runProgress.ts", "  if (r.state === 'done') return r.costUsd\n  let sum = 0", "  let sum = r.state === 'done' ? r.costUsd ?? 0 : 0"),
    ("the total ignores unknown rows", "src/state/runProgress.ts", "const known = costs.every((c) => c !== null)", "const known = true"),
    ("a finished file does not update the total", "src/state/runProgress.ts", "      return recomputeCost(withRow(next, e.key, (r) => ({ ...r, pieces: upsertPiece(r.pieces, { file: e.file, state: 'done',", "      return (withRow(next, e.key, (r) => ({ ...r, pieces: upsertPiece(r.pieces, { file: e.file, state: 'done',"),
]

FRONTEND += [
    ("an opened file shows its code blocks unfolded", "src/components/InstructionFiles.tsx", "<SafeMarkdown collapseCode>{f.text}</SafeMarkdown>", "<SafeMarkdown>{f.text}</SafeMarkdown>"),
]
