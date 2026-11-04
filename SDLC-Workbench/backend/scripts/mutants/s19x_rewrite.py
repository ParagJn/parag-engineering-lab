"""Deliberate breaks for 'Rewrite everything' (2026-11-04): the server offers a rewrite once a running phase has content; the button asks for rewrite_all.

Backend:  python -u -m scripts.mutation_check scripts/mutants/s19x_rewrite.py --tests tests/test_routes_projects.py tests/test_run_api.py
Frontend: python -u -m scripts.frontend_mutation_check scripts/mutants/s19x_rewrite.py
"""
En = "app/workflow/engine.py"

MUTANTS = [
    ("a running phase never offers rewrite", En, '    "running": ("run", "rewrite", "finish"),', '    "running": ("run", "finish"),'),
    ("rewrite comes after finish", En, '    "running": ("run", "rewrite", "finish"),', '    "running": ("run", "finish", "rewrite"),'),
    ("a phase under review offers rewrite", En, '    "awaiting_review": ("approve", "request_changes"),', '    "awaiting_review": ("approve", "request_changes", "rewrite"),'),
    ("a rejected phase offers rewrite", En, '    "rejected": ("run",),', '    "rejected": ("run", "rewrite"),'),
    ("an approved phase offers rewrite", En, '    "approved": ("reopen",),', '    "approved": ("reopen", "rewrite"),'),
    ("a phase with nothing written offers rewrite", En, '    return actions if has_content else tuple(a for a in actions if a != "rewrite")', "    return actions"),
    ("a phase with content loses rewrite", En, '    return actions if has_content else tuple(a for a in actions if a != "rewrite")', '    return tuple(a for a in actions if a != "rewrite")'),
    ("the content flag is inverted", En, '    return actions if has_content else tuple(a for a in actions if a != "rewrite")', '    return tuple(a for a in actions if a != "rewrite") if has_content else actions'),
    ("content is assumed absent by default", En, "blocked_by: str | None, has_content: bool = True)", "blocked_by: str | None, has_content: bool = False)"),
    ("the engine says there is always content", En, "any(a.has_content for a in artefacts)),", "True),"),
    ("the engine says there is never content", En, "any(a.has_content for a in artefacts)),", "False),"),
    ("the engine looks at all artefacts being written", En, "any(a.has_content for a in artefacts)),", "all(a.has_content for a in artefacts)),"),
    ("a phase with nothing in the plan offers actions", En, "    if not has_artefacts:\n        return ()", "    if False:\n        return ()"),
]

FRONTEND = [
    ("the action is not known to the screen", "src/api/types.ts", "['run', 'rewrite', 'finish', 'approve', 'request_changes', 'reopen']", "['run', 'finish', 'approve', 'request_changes', 'reopen']"),
    ("the action is in another place", "src/api/types.ts", "['run', 'rewrite', 'finish', 'approve', 'request_changes', 'reopen']", "['run', 'finish', 'rewrite', 'approve', 'request_changes', 'reopen']"),
    ("the button has another label", "src/lib/phaseActions.ts", "label: 'Rewrite everything',", "label: 'Run it again',"),
    ("the button is not wired", "src/lib/phaseActions.ts", "this costs money.',\n      live: true,\n    },\n    finish", "this costs money.',\n      live: false,\n    },\n    finish"),
    ("the hint hides the cost", "src/lib/phaseActions.ts", "the old versions are kept. Calls real models: this costs money.',", "the old versions are kept.',"),
    ("the hint says the old versions are lost", "src/lib/phaseActions.ts", "the old versions are kept. Answers come from recordings", "the old versions are replaced. Answers come from recordings"),
    ("the replay hint claims a cost", "src/lib/phaseActions.ts", "Answers come from recordings: free and offline.'\n        : 'Writes every artefact", "Calls real models: this costs money.'\n        : 'Writes every artefact"),
    ("the live hint claims it is free", "src/lib/phaseActions.ts", "this costs money.',\n      live: true,\n    },\n    finish", "free and offline.',\n      live: true,\n    },\n    finish"),
    ("a rewrite sends no option", "src/state/useProjectScreen.ts", "return action === 'rewrite' ? { rewrite_all: true } : undefined", "return undefined"),
    ("every run sends the option", "src/state/useProjectScreen.ts", "return action === 'rewrite' ? { rewrite_all: true } : undefined", "return { rewrite_all: true }"),
    ("the option has the wrong name", "src/state/useProjectScreen.ts", "{ rewrite_all: true } : undefined", "{ rewriteAll: true } : undefined"),
    ("the screen does not start a rewrite", "src/state/useProjectScreen.ts", "return action === 'run' || action === 'rewrite'", "return action === 'run'"),
    ("the screen starts a run for any action", "src/state/useProjectScreen.ts", "return action === 'run' || action === 'rewrite'", "return true"),
    ("the dispatch never uses the decision", "src/state/useProjectScreen.ts", "  if (startsARun(action)) await startFor(", "  if (action === 'run') await startFor("),
    # UNKILLABLE BY CONSTRUCTION, dropped: `act` is a React hook callback and the project has no DOM test library, so a test cannot press the real button. Everything the
    # callback decides is in `performAction`, `startsARun` and `rewriteOptions`, which ARE pressed in tests. That the hook calls `performAction` is a browser check.
    ("finish approves", "src/state/useProjectScreen.ts", "  else if (action === 'finish') await client.finishPhase(", "  else if (action === 'finish') await client.approvePhase("),
    ("the start ignores the option", "src/state/useProjectScreen.ts", "return client.startRun(projectId, phaseKey, actorName, rewriteOptions(action))", "return client.startRun(projectId, phaseKey, actorName)"),
    ("a rewrite opens a form", "src/lib/phaseActions.ts", "  if (action === 'reopen') return 'open_reopen'\n", "  if (action === 'reopen') return 'open_reopen'\n  if (action === 'rewrite') return 'open_send_back'\n"),
]

# ---- the budget setting and the folded citations (2026-11-04) -----------------------------------------------------------------------------------------
# Backend:  python -u -m scripts.mutation_check scripts/mutants/s19x_rewrite.py --only budget --tests tests/test_config.py
Cf = "app/config.py"
MUTANTS += [
    ("the budget never sets the cap", Cf, '        if "run_budget_usd" in given and "run_max_cost_usd" not in given:', "        if False:"),
    ("the budget always overrides the cap", Cf, '        if "run_budget_usd" in given and "run_max_cost_usd" not in given:', '        if "run_budget_usd" in given:'),
    # EQUIVALENT, dropped: copying the budget over a cap nobody set changes nothing, because the budget's default and the cap's default are both 5.0.
    ("the budget is copied the wrong way", Cf, "            self.run_max_cost_usd = self.run_budget_usd", "            self.run_budget_usd = self.run_max_cost_usd"),
    ("the budget is halved", Cf, "            self.run_max_cost_usd = self.run_budget_usd", "            self.run_max_cost_usd = self.run_budget_usd / 2"),
    ("the budget has no upper limit", Cf, "run_budget_usd: float = Field(default=5.0, ge=0, le=1000)", "run_budget_usd: float = 5.0"),
    ("the budget default is eight", Cf, "run_budget_usd: float = Field(default=5.0, ge=0, le=1000)", "run_budget_usd: float = Field(default=8.0, ge=0, le=1000)"),
]

FRONTEND += [
    ("the citations are shown open", "src/components/ArtefactReader.tsx", '<details aria-label="Sources" className="mt-5 rounded-lg border border-slate-200 px-3 py-2">', '<details open aria-label="Sources" className="mt-5 rounded-lg border border-slate-200 px-3 py-2">'),
    ("the citations are not folded", "src/components/ArtefactReader.tsx", '<details aria-label="Sources" className="mt-5 rounded-lg border border-slate-200 px-3 py-2">\n        <summary className="cursor-pointer text-sm font-bold">', '<section aria-label="Sources" className="mt-5 rounded-lg border border-slate-200 px-3 py-2">\n        <summary className="cursor-pointer text-sm font-bold">'),
    ("the citation count is missing", "src/components/ArtefactReader.tsx", "What it cites ({a.sources.length})</summary>", "What it cites</summary>"),
    ("each citation is no longer folded", "src/components/ArtefactReader.tsx", '<details key={s.source_id} className="rounded-lg border border-slate-200 px-3 py-2 text-sm">', '<div key={s.source_id} className="rounded-lg border border-slate-200 px-3 py-2 text-sm">'),
]

# ---- the folded connections (2026-11-05) -----------------------------------------------------------------------------------------------------------
FRONTEND += [
    ("the connections are shown open", "src/components/ArtefactReader.tsx", '    <details className="rounded-lg border border-slate-200 px-3 py-2">\n      <summary className="cursor-pointer text-sm font-bold">{title} ({links.length})', '    <details open className="rounded-lg border border-slate-200 px-3 py-2">\n      <summary className="cursor-pointer text-sm font-bold">{title} ({links.length})'),
    ("the connections are not folded", "src/components/ArtefactReader.tsx", '    <details className="rounded-lg border border-slate-200 px-3 py-2">\n      <summary className="cursor-pointer text-sm font-bold">{title} ({links.length})</summary>', '    <div className="rounded-lg border border-slate-200 px-3 py-2">\n      <p className="cursor-pointer text-sm font-bold">{title} ({links.length})</p>'),
    ("the connection count is missing", "src/components/ArtefactReader.tsx", "{title} ({links.length})</summary>", "{title}</summary>"),
    ("the connection count is wrong", "src/components/ArtefactReader.tsx", "{title} ({links.length})</summary>", "{title} ({links.length + 1})</summary>"),
    ("the empty sentence is dropped", "src/components/ArtefactReader.tsx", "{links.length === 0 ? <p className=\"mt-2 text-xs text-slate-500\">{empty}</p> : (", "{links.length === 0 ? null : ("),
    ("the links are not listed", "src/components/ArtefactReader.tsx", "          {links.map((l, i) => (\n            <li key={i} className=\"font-mono\"><span>{l.from}</span>", "          {[].map((l: LinkRef, i) => (\n            <li key={i} className=\"font-mono\"><span>{l.from}</span>"),
    ("a link is shown backwards", "src/components/ArtefactReader.tsx", "<span>{l.from}</span> <ChevronRight size={10} className=\"inline\" aria-hidden /> <span>{l.to}</span>", "<span>{l.to}</span> <ChevronRight size={10} className=\"inline\" aria-hidden /> <span>{l.from}</span>"),
    ("only one list is folded", "src/components/ArtefactReader.tsx", '<Links title="Built on this" links={a.links.used_by} empty="Nothing is built on it yet." />', '<div><h4 className="text-sm font-bold">Built on this</h4><p>{a.links.used_by.length}</p></div>'),
]
