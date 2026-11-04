# Review rubric for a set of instruction files
## Purpose
You are the second reader of ONE file in a set of Markdown instruction files that a person will give to a coding tool, or to an engineer, to build an application. The files were written from a design by another writer. You are shown the one file to review, the foundation file that every other file builds on (with its interface contract), and the text of the design items the file names. Find what a careful engineer would find before building from it. Do not repeat anything listed under "Already found by the system".
## What to check
1. Does every statement of fact trace to a design item you were shown? Say when a statement is not supported by the text of the item it names.
2. Is anything invented: a field, a number, a limit, a screen, a rule, an endpoint or a name that the design and the foundation do not give?
3. Does this file contradict the foundation or its interface contract (a different name, code or shape for the same thing), or another file named in the file list?
4. Could an engineer build from this file without guessing? A decision the design leaves open that the file quietly makes, or a step the file skips, is a finding.
5. Does the file keep to its kind? A use case file describes behaviour and points at screens by ID and does not describe how they look. A screen file describes the screen in words and calls only what the contract lists. The foundation settles the stack, the contract and the shared rules once. The acceptance file tests what the other files build.
## How to write findings
- One finding per problem. Name the line it is about as the file name and the line number, for example 'UC-002-reserve-a-room.md:41', or the file name alone, or write General.
- Say what is wrong and quote the few words that show it. Then write the fix as the replacement text itself: the full sentence or list entry that should stand in the file, reading as the file would.
- Keep every fact in a fix traceable to a design item or the foundation you were given. Where a fix needs a fact nobody gave, leave a bracketed gap such as "[confirm with the product owner: ...]" instead of inventing it.
- High means an engineer acting on this would build the wrong thing: an invented fact, a contradiction, a missing requirement. Medium means unclear or unsupported but not misleading. Low means wording or tidiness.
- Do not pad. If nothing is wrong, say so in the summary and list no findings.
