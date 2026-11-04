"""Deliberate breaks for S20d (the Build Verify screen), frontend only.

Frontend: python -u -m scripts.frontend_mutation_check scripts/mutants/s20d_screen.py
Run alone: a sweep beside other heavy work gives INVALID ('no output') results.
"""
MUTANTS: list = []

L = "src/lib/verify.ts"
C = "src/components/VerifyPanel.tsx"
A = "src/api/verify.ts"
K = "src/api/client.ts"
P = "src/lib/verifyPaths.ts"
R = "src/lib/router.ts"
G = "src/pages/VerifyPage.tsx"

FRONTEND = [
    # ---- the look of a state
    ("found is not green", L, "tile: 'border-emerald-400 bg-emerald-50 text-emerald-900'", "tile: 'border-amber-400 bg-amber-50 text-amber-900 '"),
    ("not found is not red", L, "tile: 'border-rose-400 bg-rose-50 text-rose-900'", "tile: 'border-slate-400 bg-slate-100 text-slate-800 '"),
    ("possible is not dashed", L, "tile: 'border-sky-400 bg-sky-50 text-sky-900 border-dashed'", "tile: 'border-sky-400 bg-sky-50 text-sky-900'"),
    ("extra is not violet", L, "tile: 'border-violet-400 bg-violet-50 text-violet-900'", "tile: 'border-sky-400 bg-sky-50 text-sky-900 '"),
    ("two states share an icon", L, "icon: 'x', tile: 'border-rose-400", "icon: 'help', tile: 'border-rose-400"),
    ("found with differences uses the plain tick", L, "icon: 'check-alert'", "icon: 'check'"),
    ("a state loses its word", L, "word: 'Weak evidence'", "word: ''"),
    ("the order puts bad news first", L, "export const STATE_ORDER: VerifyState[] = ['found', 'differences', 'possible', 'weak', 'not_found', 'extra']", "export const STATE_ORDER: VerifyState[] = ['not_found', 'found', 'differences', 'possible', 'weak', 'extra']"),
    # ---- the ring and the maths
    ("possible counts as found", L, "  return c.designed === 0 ? 0 : (c.found + c.differences) / c.designed", "  return c.designed === 0 ? 0 : (c.found + c.differences + c.possible) / c.designed"),
    ("differences do not count as found", L, "  return c.designed === 0 ? 0 : (c.found + c.differences) / c.designed", "  return c.designed === 0 ? 0 : c.found / c.designed"),
    ("nothing designed divides by zero", L, "  return c.designed === 0 ? 0 :", "  return"),
    ("the percent is cut not rounded", L, "`${Math.round(share * 100)}%`", "`${Math.floor(share * 100)}%`"),
    ("the ring can overfill", L, "  const clamped = Math.min(1, Math.max(0, share))", "  const clamped = share"),
    ("the ring is the wrong size", L, "  const circumference = 2 * Math.PI * r", "  const circumference = Math.PI * r"),
    # ---- tiles and words
    ("tiles of every area are shown", L, "  const mine = matches.filter((m) => m.area === area)", "  const mine = [...matches]"),
    ("tiles are not ordered by id", L, "|| (a.designed ?? '').localeCompare(b.designed ?? '') || a.built.localeCompare(b.built))", ")"),
    ("a tile label hides the state", L, "return `${what}: ${look.word}${found}${diff}`", "return `${what}${found}${diff}`"),
    ("a tile label hides the differences", L, "  const diff = m.differences.length ?", "  const diff = false ?"),
    ("one difference is plural", L, "${m.differences.length === 1 ? 'difference' : 'differences'}", "differences"),
    ("an extra is labelled by its id", L, "  const what = m.designed ?? m.built", "  const what = m.designed ?? ''"),
    ("the line is dropped", L, "return m.file ? (m.line > 0 ? `${m.file}:${m.line}` : m.file) : ''", "return m.file"),
    ("the score shows for every step", L, "return m.step === 'words' ? `Matched by ${how}, score ${m.score.toFixed(2)}` : `Matched by ${how}`", "return `Matched by ${how}, score ${m.score.toFixed(2)}`"),
    ("a match with no step says how", L, "  if (!m.step) return ''", "  if (false) return ''"),
    # ---- the trend
    ("the trend goes newest first", L, "  return [...runs].reverse().map((r) => {", "  return [...runs].map((r) => {"),
    ("the line goes down for a rise", L, "const y = (share: number) => height - pad - Math.min(1, Math.max(0, share)) * (height - 2 * pad)", "const y = (share: number) => pad + Math.min(1, Math.max(0, share)) * (height - 2 * pad)"),
    ("the line can leave its box", L, "Math.min(1, Math.max(0, share)) * (height - 2 * pad)", "share * (height - 2 * pad)"),
    ("one run is not a dot", L, "points.length === 1 ? width / 2 :", "points.length === 1 ? 0 :"),
    ("change since is the wrong way", L, "return a.found + a.differences - (b.found + b.differences)", "return b.found + b.differences - (a.found + a.differences)"),
    ("the first run has a change", L, "  if (!older) return null", "  if (!older) return 0"),
    ("a design that grew is not a change", L, "  for (const k of keys) if ((run.design[k] ?? 0) !== (now[k] ?? 0) && (k in run.design || k in now)) return true", "  for (const k of keys) if (k in run.design && run.design[k] !== now[k]) return true"),
    ("a design that shrank is not a change", L, "  for (const k of keys) if ((run.design[k] ?? 0) !== (now[k] ?? 0) && (k in run.design || k in now)) return true", "  for (const k of keys) if (k in now && run.design[k] !== now[k]) return true"),
    # ---- the panel
    ("the ring says nothing for an empty area", C, "counts.designed === 0 ? `${AREA_WORDS[counts.area]}: nothing in the design`", "counts.designed === 0 ? `${AREA_WORDS[counts.area]}: 0% found`"),
    ("an empty area draws an arc", C, "      {counts.designed > 0 && (", "      {true && ("),
    ("the middle of the ring is empty", C, "{counts.designed === 0 ? '–' : percent(share)}", "{''}"),
    ("a tile opens by itself", C, "<details className={`group rounded-lg border-2 ${look.tile}`}>", "<details open className={`group rounded-lg border-2 ${look.tile}`}>"),
    ("a tile shows no state in words", C, "          <p className=\"font-semibold\">{look.word}</p>\n          <p>{look.hint}</p>", "          <p>{look.hint}</p>"),
    ("a tile hides its differences", C, "{match.differences.length > 0 && <ul", "{false && <ul"),
    ("a tile hides where it is", C, "{where && <p>In <span className=\"font-mono\">{where}</span></p>}", ""),
    ("a tile hides how it matched", C, "{howOf(match) && <p>{howOf(match)}</p>}", ""),
    ("a tile hides its note", C, "{match.note && <p>{match.note}</p>}", ""),
    ("an extra says found as", C, "{match.designed && match.built && <p>Found as", "{match.built && <p>Found as"),
    # EQUIVALENT, not tested: lucide-react already adds aria-hidden="true" to any icon given no accessible label (buildLucideIconNode), so dropping ours changes nothing. It stays in the code to state the intent without relying on a library default.
    # ("an icon can be heard", C, "return <Icon size={size} aria-hidden />", "return <Icon size={size} />"),
    ("the card hides what was built but not designed", C, "            {counts.extras > 0 && <> · {counts.extras} built but not designed</>}", ""),
    ("the card hides the change", C, "{change !== null && change !== 0 && <p", "{false && <p"),
    ("the card says more for fewer", C, "{change > 0 ? `${change} more` : `${-change} fewer`}", "{change > 0 ? `${change} fewer` : `${-change} more`}"),
    ("an empty area does not say so", C, "{counts.designed === 0 ? 'Nothing in the design.' :", "{counts.designed === 0 ? '' :"),
    ("the legend is missing a state", C, "{STATE_ORDER.map((s) => <li key={s}", "{STATE_ORDER.slice(1).map((s) => <li key={s}"),
    ("the trend shows with one run", C, "  if (runs.length < 2) return <p", "  if (runs.length < 0) return <p"),
    ("the trend hides with two runs", C, "  if (runs.length < 2) return <p", "  if (runs.length < 3) return <p"),
    ("the trend has no words", C, "aria-label={`${AREA_WORDS[area]}: ${points.map((p) => percent(p.share)).join(', then ')}`}", "aria-label=\"trend\""),
    ("the button works without a backend folder", C, "disabled={!p.canRun || !p.backend.trim() || p.busy}", "disabled={!p.canRun || p.busy}"),
    ("the button works without a name", C, "disabled={!p.canRun || !p.backend.trim() || p.busy}", "disabled={!p.backend.trim() || p.busy}"),
    ("the button works while busy", C, "disabled={!p.canRun || !p.backend.trim() || p.busy}", "disabled={!p.canRun || !p.backend.trim()}"),
    ("pressing enter checks without a folder", C, "if (p.canRun && p.backend.trim() && !p.busy) p.onRun()", "if (p.canRun && !p.busy) p.onRun()"),
    ("pressing enter checks twice", C, "if (p.canRun && p.backend.trim() && !p.busy) p.onRun()", "if (p.canRun && p.backend.trim()) p.onRun()"),
    ("the missing name is not explained", C, "{!p.canRun && <p className=\"text-xs text-slate-500\">Give your name first", "{false && <p className=\"text-xs text-slate-500\">Give your name first"),
    ("the languages are not named", C, "Python/FastAPI for the backend; React, Vue or plain JavaScript/TypeScript for the frontend, read by pattern. Other languages are not understood in this version.", "Folders are read."),
    ("the secret rule is not said", C, "Files that may hold a secret (.env, keys) are never read.", ""),
    ("the changed design is not warned", C, "{newer && p.designChanged && <Notice", "{false && <Notice"),
    ("the warning shows without a run", C, "{newer && p.designChanged && <Notice", "{p.designChanged && <Notice"),
    ("a failed check is not shown", C, "{p.error && <Notice tone=\"error\" title=\"The check could not be run\">{p.error}</Notice>}", ""),
    ("the notes are not folded", C, "<details className=\"rounded-lg border border-slate-200 bg-white px-3 py-2\">\n              <summary className=\"cursor-pointer text-sm font-semibold\">What could not be read", "<details open className=\"rounded-lg border border-slate-200 bg-white px-3 py-2\">\n              <summary className=\"cursor-pointer text-sm font-semibold\">What could not be read"),
    ("the notes show when there are none", C, "{newer.notes.length > 0 && (", "{true && ("),
    ("the markdown download is missing", C, "<a href={`/api/projects/${encodeURIComponent(p.projectId)}/verify/${newer.id}/download`}", "<a hidden href={`/api/projects/${encodeURIComponent(p.projectId)}/verify/${newer.id}/download`}"),
    ("the json download goes to markdown", C, "/download?format=json`}", "/download`}"),
    ("downloads go to another run", C, "verify/${newer.id}/download?format=json", "verify/${newer.id + 1}/download?format=json"),
    ("no run says so", C, "<Notice tone=\"info\" title=\"No check yet\">", "<Notice tone=\"info\" title=\"\">"),
    ("the earlier runs are not listed", C, "{p.runs.length > 0 && (", "{false && ("),
    ("the run on show is not marked", C, "aria-current={newer?.id === r.id ? 'true' : undefined}", ""),
    ("an earlier run is compared with a later one", C, "const older = newer ? p.runs.find((r) => r.id < newer.id) : undefined", "const older = newer ? p.runs.find((r) => r.id > newer.id) : undefined"),
    ("an earlier run cannot be opened", C, "onClick={() => p.onOpenRun(r.id)}", "onClick={() => undefined}"),
    ("the share of a run is not shown", C, "${c.designed ? percent(shareFound(c)) : '–'}", "–"),
    ("who ran it is not said", C, "Run {newer.id} by {newer.by.replace(/^human:/, '')}", "Run {newer.id}"),
    # ---- the decoders and the calls
    ("an unknown area is accepted", A, "area: oneOf(o.area, `${w}.area`, AREAS), designed: n('designed')", "area: str(o.area, `${w}.area`) as never, designed: n('designed')"),
    ("an unknown state is accepted", A, "state: oneOf(o.state, `${w}.state`, STATES)", "state: str(o.state, `${w}.state`) as never"),
    ("a count may be text", A, "const n = (key: string) => num(o[key], `${w}.${key}`)", "const n = (key: string) => o[key] as number"),
    ("a design version may be text", A, "[k, num(design[k], `${w}.design.${k}`)]", "[k, design[k] as number]"),
    ("a note may be a number", A, "counts: arr(o.counts, `${w}.counts`).map((c, i) => decodeCounts(c, `${w}.counts[${i}]`)), notes: strings(o.notes, `${w}.notes`)", "counts: arr(o.counts, `${w}.counts`).map((c, i) => decodeCounts(c, `${w}.counts[${i}]`)), notes: o.notes as string[]"),
    ("advice is required", A, "advice: typeof o.advice === 'string' ? o.advice : ''", "advice: str(o.advice, 'verify run.advice')"),
    ("the list advice is optional", A, "advice: str(o.advice, 'verify runs.advice')", "advice: typeof o.advice === 'string' ? o.advice : ''"),
    ("a built thing may have a designed id", A, "designed: nullable(o.designed, `${w}.designed`, str)", "designed: o.designed as never"),
    ("the check goes to the wrong address", K, "`/api/projects/${id(projectId)}/verify`, {\n        method: 'POST'", "`/api/projects/${id(projectId)}/verify/x`, {\n        method: 'POST'"),
    ("the check is a get", K, "        method: 'POST', headers: { 'Content-Type': 'application/json', ...who(actorName) }, body: JSON.stringify({ backend_path: backendPath, frontend_path: frontendPath }),", "        method: 'GET', headers: { 'Content-Type': 'application/json', ...who(actorName) }, body: undefined,"),
    ("the check does not name the person", K, "method: 'POST', headers: { 'Content-Type': 'application/json', ...who(actorName) }, body: JSON.stringify({ backend_path", "method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ backend_path"),
    ("the check drops the frontend", K, "backend_path: backendPath, frontend_path: frontendPath }", "backend_path: backendPath }"),
    ("a run is read by the wrong number", K, "verify/${id(String(runId))}`", "verify/${id(String(runId + 1))}`"),
    # ---- the saved folders
    ("a folder is saved for every project", P, "const key = (projectId: string) => `sdlc.verify.paths.${projectId}`", "const key = (projectId: string) => `sdlc.verify.paths`"),
    ("a damaged store breaks the page", P, "  } catch {\n    return { backend: '', frontend: '' }\n  }", "  } finally {\n  }"),
    ("a saved folder is not cut when read", P, "const text = (v: unknown) => (typeof v === 'string' ? v.slice(0, MAX) : '')", "const text = (v: unknown) => (typeof v === 'string' ? v : '')"),
    ("a saved folder is not cut when saved", P, "JSON.stringify({ backend: paths.backend.slice(0, MAX), frontend: paths.frontend.slice(0, MAX) })", "JSON.stringify(paths)"),
    ("a blocked store breaks saving", P, "  } catch {\n    /* a full or blocked store is not an error: the page works without it */\n  }", "  } finally {\n  }"),
    # ---- the address
    ("the verify address is not parsed", R, "    if (parts.length === 3 && parts[2] === 'verify') return { name: 'verify', id }\n", ""),
    ("the verify address takes more", R, "if (parts.length === 3 && parts[2] === 'verify')", "if (parts[2] === 'verify')"),
    ("the verify address is built wrongly", R, "case 'verify': return `#/projects/${encodeURIComponent(route.id)}/verify`", "case 'verify': return `#/projects/${route.id}/verify`"),
]
