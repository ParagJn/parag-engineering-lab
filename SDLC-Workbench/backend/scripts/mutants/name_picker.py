"""Deliberate breaks for the name drop-down (the 'What should we call you?' prompt offers the people on the Users list).

Frontend: python -u -m scripts.frontend_mutation_check scripts/mutants/name_picker.py
"""
A = "src/lib/actor.ts"
P = "src/components/NamePrompt.tsx"

MUTANTS: list = []

FRONTEND = [
    ("switched-off people are offered", A, "if (u.active && name && !seen.has(name.toLowerCase()))", "if (name && !seen.has(name.toLowerCase()))"),
    ("a name can be offered twice", A, "if (u.active && name && !seen.has(name.toLowerCase())) { seen.add(name.toLowerCase()); out.push(name) }", "if (u.active && name) { seen.add(name.toLowerCase()); out.push(name) }"),
    ("a blank name is offered", A, "if (u.active && name && !seen", "if (u.active && !seen"),
    ("names are not tidied", A, "const name = cleanName(u.name)\n    if (u.active", "const name = u.name\n    if (u.active"),
    ("the saved name is matched with case", A, "names.some((n) => n.toLowerCase() === name.toLowerCase()) ? names.find((n) => n.toLowerCase() === name.toLowerCase())! : OTHER", "names.includes(name) ? name : OTHER"),
    ("a saved name not on the list is lost", A, "name.toLowerCase())! : OTHER", "name.toLowerCase())! : ''"),
    ("no saved name starts on someone else", A, "if (!name) return ''", "if (!name) return OTHER"),
    ("the drop-down is never shown", P, "const listed = names.length > 0", "const listed = false"),
    ("the drop-down is shown with no list", P, "const listed = names.length > 0", "const listed = true"),
    ("the typing box always shows", P, "const typing = !listed || choice === OTHER", "const typing = true"),
    ("the typing box never shows with a list", P, "const typing = !listed || choice === OTHER", "const typing = !listed"),
    ("someone else is not offered", P, "<option value={OTHER}>Someone else (type a name)</option>", ""),
    ("the listed names are not offered", P, "{names.map((n) => <option key={n} value={n}>{n}</option>)}", ""),
    ("a chosen name is not used", A, "(choice === OTHER || choice === '' ? '' : choice)", "''"),
    ("someone else keeps the previous name", A, "(choice === OTHER || choice === '' ? '' : choice)", "(choice === '' ? '' : choice)"),
    # NOT TESTABLE without React: the one line that hands a drop-down choice to valueForChoice (an onChange handler). The rule itself is tested; breaking this wire survives.
    # ("the prompt does not use the rule", P, "setValue(valueForChoice(next))", "setValue('')")
    ("the saved listed name does not start chosen", P, "(names.length === 0 || startingChoice(initial, names) === OTHER ? initial : startingChoice(initial, names))", "''"),
]
