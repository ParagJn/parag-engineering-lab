"""Deliberate breaks for S19c-2 (the composer writes the UI guide and the screen files).

Backend:  python -u -m scripts.mutation_check scripts/mutants/s19c2_compose_ui.py --tests tests/test_compose.py tests/test_instructions.py tests/test_agent_skills.py
Frontend: python -u -m scripts.frontend_mutation_check scripts/mutants/s19c2_compose_ui.py
"""
Cp = "app/build/compose.py"
In = "app/build/instructions.py"
Sk = "app/phases/skills/build_instructions.md"

MUTANTS = [
    ("no UI files are ever written", Cp, "        has_ui = bool(screens)", "        has_ui = False"),
    ("UI files are always written", Cp, "        has_ui = bool(screens)", "        has_ui = True"),
    ("the guide is written after the use cases", Cp, "guide = await write(I.UI_GUIDE_NAME, I.UI_GUIDE, _request_ui_guide(screens), shown_foundation, 2, \"ui_guide\")", "guide = await write(I.UI_GUIDE_NAME, I.UI_GUIDE, _request_ui_guide(screens), shown_foundation, 2, \"ui_guide\") if False else None"),
    ("the guide is not shown the foundation", Cp, "_request_ui_guide(screens), shown_foundation, 2, \"ui_guide\")", "_request_ui_guide(screens), \"\", 2, \"ui_guide\")"),
    ("a screen is not shown the guide", Cp, "_request_screen(name, screen_id, title, text, design), shown_ui, index, \"screen\")", "_request_screen(name, screen_id, title, text, design), shown_foundation, index, \"screen\")"),
    ("a screen is not shown the foundation", Cp, "{I.FOUNDATION_NAME: foundation.body, I.UI_GUIDE_NAME: guide.body})", "{I.UI_GUIDE_NAME: guide.body})"),
    ("a use case is shown the guide", Cp, "_request_use_case(name, uc_id, title, text, screens), shown_foundation, index, \"use_case\")", "_request_use_case(name, uc_id, title, text, screens), shown_ui, index, \"use_case\")"),
    ("a use case is not told about the screens", Cp, "_request_use_case(name, uc_id, title, text, screens), shown_foundation", "_request_use_case(name, uc_id, title, text), shown_foundation"),
    ("a use case is always told about screens", Cp, "    if screens:\n        listed = \"; \".join", "    if True:\n        listed = \"; \".join"),
    ("screens are not run", Cp, "scenarios, ui_pieces = done_pieces[:len(uc_tasks)], done_pieces[len(uc_tasks):]", "scenarios, ui_pieces = done_pieces[:len(uc_tasks)], []"),
    ("use cases and screens are mixed up", Cp, "scenarios, ui_pieces = done_pieces[:len(uc_tasks)], done_pieces[len(uc_tasks):]", "ui_pieces, scenarios = done_pieces[:len(uc_tasks)], done_pieces[len(uc_tasks):]"),
    ("screens do not share the concurrency limit", Cp, "            name = I.screen_name(screen_id, title)\n            async with sem:", "            name = I.screen_name(screen_id, title)\n            if True:"),
    ("use cases do not share the concurrency limit", Cp, "            name = I.scenario_name(uc_id, title)\n            async with sem:", "            name = I.scenario_name(uc_id, title)\n            if True:"),
    ("a failed screen does not stop the others", Cp, "            for t in [*uc_tasks, *ui_tasks]:\n                t.cancel()", "            for t in [*uc_tasks]:\n                t.cancel()"),
    ("the screens are not in the saved order", Cp, "pieces = [foundation, *([guide] if guide else []), *scenarios, *ui_pieces, acceptance]", "pieces = [foundation, *([guide] if guide else []), *ui_pieces, *scenarios, acceptance]"),
    ("the guide is left out of the saved set", Cp, "pieces = [foundation, *([guide] if guide else []), *scenarios", "pieces = [foundation, *scenarios"),
    ("the total ignores the ui files", Cp, "+ ((1 + len(screens)) if has_ui else 0)", ""),
    ("the total counts the guide twice", Cp, "((1 + len(screens)) if has_ui else 0)", "((2 + len(screens)) if has_ui else 0)"),
    ("the first use case index ignores the guide", Cp, "        first = 3 if has_ui else 2", "        first = 2"),
    ("the screens' indexes overlap the use cases", Cp, "first + len(use_cases) + n, sid, title, text", "first + n, sid, title, text"),
    ("the guide's index is wrong", Cp, "shown_foundation, 2, \"ui_guide\")", "shown_foundation, 3, \"ui_guide\")"),
    ("the screen stage is mislabelled", Cp, "shown_ui, index, \"screen\")", "shown_ui, index, \"use_case\")"),
    ("the guide stage is mislabelled", Cp, "shown_foundation, 2, \"ui_guide\")", "shown_foundation, 2, \"foundation\")"),
    ("the set is not told the ui is required", Cp, "highest=int(item_ctx.highest.get(I.ITEM_PREFIX, 0)), require_ui=has_ui)", "highest=int(item_ctx.highest.get(I.ITEM_PREFIX, 0)))"),
    ("the gaps are not told the ui is required", Cp, "I.gaps_of(files, design, require_ui=has_ui)", "I.gaps_of(files, design)"),
    ("the screen title is not neutralised", Cp, "for the hi-fi screen {screen_id} ({neutralise(title)}).", "for the hi-fi screen {screen_id} ({title})."),
    ("the screen text is not neutralised", Cp, "The screen, as the design states it: {neutralise(text).strip()}", "The screen, as the design states it: {text.strip()}"),
    ("the screen list in the guide is not neutralised", Cp, "listed = \"\\n\".join(f\"- {sid} {neutralise(t)}\" for sid, t, _ in screens)", "listed = \"\\n\".join(f\"- {sid} {t}\" for sid, t, _ in screens)"),
    ("the screen request drops the id of the screen", Cp, "The Traceability section must name {screen_id}.", ""),
    ("the screen request drops 'in words'", Cp, "Describe the screen in WORDS, top to bottom: a coding tool cannot see the wireframe drawing. ", ""),
    ("the screen request drops the endpoints", Cp, "(the endpoints are: {_ids(design, 'API')})", ""),
    ("the guide request drops the screens", Cp, "The screens that will each get a file of their own after this one:\\n{listed}\\n", ""),
    ("the guide request drops its sections", Cp, "Its sections, in this order: {_sections(I.UI_GUIDE)}.", ""),
    ("the screen request drops its sections", Cp, "Its sections, in this order: {_sections(I.SCREEN)}.", ""),
    ("the screen limit is 14", In, "MAX_SCREENS = 15", "MAX_SCREENS = 14"),
    ("the screen limit is 16", In, "MAX_SCREENS = 15", "MAX_SCREENS = 16"),
    ("too many screens are accepted", Cp, "        if len(screens) > I.MAX_SCREENS:", "        if False:"),
    ("the screens are not in order", Cp, "        return sorted(screens)", "        return screens"),
    ("the screens are read from the wrong artefact", Cp, "wireframes = next((u for u in upstream if u.key == \"hifi_wireframes\"), None)", "wireframes = next((u for u in upstream if u.key == \"lowfi_wireframes\"), None)"),
    ("the skill drops the separation rule", Sk, "In a use case file never describe how a screen looks", "In a use case file describe anything"),
    ("the skill drops the screen sections", Sk, "4c. A screen file (UI-HFS-001-<short-name>.md)", "4c. A page file"),
    ("the skill drops the guide", Sk, "4b. When the design has hi-fi screens, the UI guide (01-ui-guidelines.md)", "4b. When the design has hi-fi screens, the guide"),
]

FRONTEND = [
    ("the decoder drops the ui_guide stage", "src/api/events.ts", "['foundation', 'ui_guide', 'use_case', 'screen', 'acceptance']", "['foundation', 'use_case', 'screen', 'acceptance']"),
    ("the decoder drops the screen stage", "src/api/events.ts", "['foundation', 'ui_guide', 'use_case', 'screen', 'acceptance']", "['foundation', 'ui_guide', 'use_case', 'acceptance']"),
    ("the decoder accepts any stage", "src/api/events.ts", "['foundation', 'ui_guide', 'use_case', 'screen', 'acceptance'] as const", "['foundation', 'ui_guide', 'use_case', 'screen', 'acceptance', 'guide'] as const"),
]
