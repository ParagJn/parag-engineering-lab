"""Deliberate breaks for the paste-ready review fixes (S13 follow-up, 2026-10-31): the fix as its own longer field, lines that wrap after "Fix:",
a finding about several items, and the words the reviewer is told.

Run:  cd backend && python -u -m scripts.mutation_check scripts/mutants/s13_paste_ready.py --tests tests/test_review_reply.py tests/test_review_prompt.py tests/test_link_replacement.py

The rubric wording (app/phases/review/rubric.md) is Markdown, which this harness cannot break (it compiles every mutant as Python), so it is
broken by hand: remove each of "replacement text itself", "ready to paste in place of the faulty one", "traceable to a source", "bracketed gap"
and "change only the faulty part" in turn and `tests/test_review_prompt.py::test_the_rubric_asks_for_a_fix_that_can_be_pasted_and_traced_to_a_source` must fail.
"""
R = "app/review/reply.py"
P = "app/review/prompt.py"
M = "app/phases/review/rubric.md"
C = "app/config.py"

MUTANTS = [
    ("the fix limit is the problem limit", R, "MAX_FIX_CHARS = 3000 ", "MAX_FIX_CHARS = 1500 "),
    ("the fix limit is one too generous", R, "MAX_FIX_CHARS = 3000 ", "MAX_FIX_CHARS = 3001 "),
    ("the problem limit is the fix limit", R, "MAX_TEXT_CHARS = 1500 ", "MAX_TEXT_CHARS = 3000 "),
    ("the fix is cut at the problem limit", R, "text[match.end():].strip()[:MAX_FIX_CHARS]", "text[match.end():].strip()[:MAX_TEXT_CHARS]"),
    ("a wrapped fix is not cut", R, "(last.fix + \"\\n\" + raw.strip())[:MAX_FIX_CHARS].strip()", "(last.fix + \"\\n\" + raw.strip()).strip()"),
    ("a wrapped fix line is joined with a space", R, "(last.fix + \"\\n\" + raw.strip())", "(last.fix + \" \" + raw.strip())"),
    ("a wrapped fix line goes to the problem", R, "                    if in_fix[at]:", "                    if False:"),
    ("a wrapped problem line goes to the fix", R, "                    if in_fix[at]:", "                    if True:"),
    ("the fix is never recognised as started", R, "            in_fix.append(bool(_FIX.search(rest)))", "            in_fix.append(False)"),
    ("a wrapped line is only given to the last of several findings", R, "for at in range(len(findings) - group, len(findings)):", "for at in range(len(findings) - 1, len(findings)):"),
    ("a wrapped line is given to every finding so far", R, "for at in range(len(findings) - group, len(findings)):", "for at in range(0, len(findings)):"),
    ("the group size is not kept", R, "        group = len(targets)", "        group = 1"),
    ("a fix starting on a wrapped line is not noticed", R, "                        in_fix[at] = bool(_FIX.search(raw))", "                        pass"),
    ("the prompt does not say the fix is the replacement text", P, "The Fix is the REPLACEMENT TEXT ITSELF", "The Fix is a suggestion"),
    ("the prompt does not say how to wrap a long fix", P, "start every further line with two spaces", "continue on the next line"),
    ("the prompt allows an invented fact in the gap", P, "Never fill the gap with an invented fact.", "Fill the gap with your best guess."),
    ("the prompt does not forbid markup for a drawing", P, "do not write markup", "write the markup"),
    ("the prompt example loses the Fix marker", P, "Fix: the replacement text.'", "Suggestion: the replacement text.'"),
    ("the prompt has no ordering for a long list", P, " If there are many problems, put the most serious first and stop after the twenty that matter most.", ""),
    ("the review output limit is back to 3000", C, "review_max_output_tokens: int = Field(default=8000,", "review_max_output_tokens: int = Field(default=3000,"),
]
