---
name: compiling-daily-news
description: "Searches the web for today's most important news stories and compiles a verified, deduplicated top-10 digest with a headline, a 1–2 sentence summary, the source, the publish time and a link for each item. Use when the user asks for today's news, top headlines, the top 10 news stories, what's happening in the world today, a daily news briefing or digest, or the latest news for a specific country, region or topic such as tech, business or sports."
when_to_use: >-
  Example requests: "search the internet for top 10 news from today",
  "what are today's headlines?", "give me a news briefing",
  "top stories in Germany today", "today's biggest tech news",
  "/compiling-daily-news UK".
argument-hint: "[region or topic, optional]"
allowed-tools: WebSearch WebFetch Bash(date *) Bash(python3 ${CLAUDE_SKILL_DIR}/scripts/*)
---

# Compiling Daily News

Build a top-10 digest of today's most important news for a scope (global by default, or the region or topic in `$ARGUMENTS`). Selecting stories is editorial judgement. Date verification, deduplication and output format are strict and are checked by a script.

## Quick start

1. Run `date '+%F %H:%M %Z %z'`.
2. Search, verify, rank and pick 10 stories.
3. Validate them with `python3 ${CLAUDE_SKILL_DIR}/scripts/validate_digest.py --date YYYY-MM-DD --window-hours 36`.
4. Render the digest with `--render` and present it.

## Files

- [reference/ranking-criteria.md](reference/ranking-criteria.md): editorial rules and query recipes.
  - Read the "Query recipes" section at Step 2 when `$ARGUMENTS` names a region or topic.
  - Read the whole file at Step 4 before ranking.
- [templates/digest.md](templates/digest.md): the exact output structure. Read it at Step 6 only if you write the digest by hand instead of using `--render`.
- [scripts/validate_digest.py](scripts/validate_digest.py): the checker and renderer. Run it at Steps 5 and 6. Do not read it unless it fails in a way you cannot interpret.

## Workflow

Copy this checklist and tick items off as you go:

```
Progress:
- [ ] Step 1: Date and scope established
- [ ] Step 2: 15–25 candidates gathered from 4–6 searches
- [ ] Step 3: Each candidate verified (timestamp, canonical URL, outlet, facts)
- [ ] Step 4: 10 stories ranked and selected per ranking criteria
- [ ] Step 5: validate_digest.py reports ok: true
- [ ] Step 6: Digest rendered and presented with date, scope and method note
```

### Step 1: Establish the target date and scope

Run `date '+%F %H:%M %Z %z'`. The output gives today's date, the time, the timezone name and the UTC offset.

Treat `$ARGUMENTS` as an optional region or topic, for example `Japan`, `UK` or `tech`. If it is empty, use global general news with the scope `Global`. If the user named a scope in plain language ("biggest AI and tech news"), use that scope.

Tell the user the date and scope before searching, for example: "Compiling top news for 2025-01-31 (JST), scope: Japan."

### Step 2: Gather candidates

Run 4–6 WebSearch queries that combine the date and the scope:

- `<scope> news <Month D, YYYY>`
- `top headlines today <scope>`
- `breaking news <scope>`
- one query per major section (politics, business, tech, science), or per sub-topic when the scope is a topic
- wire services and major outlets: `Reuters <scope> today`, `AP news <scope>`, `BBC <scope>`

For a region or topic scope, use the query recipes in [reference/ranking-criteria.md](reference/ranking-criteria.md).

Collect 15–25 candidates. For each one, note the headline, the outlet, the URL and any date shown in the search result.

### Step 3: Verify each candidate

Confirm that each candidate was published or updated within the last 24 hours of the target date. Use WebFetch on the article, or the date metadata in the search snippet.

For each candidate you keep, record:

- the canonical URL (no tracking parameters)
- the outlet name
- the ISO-8601 timestamp with its offset, for example `2025-01-31T08:15:00+00:00`
- the key facts, taken from the article or snippet text

Drop any candidate you cannot date. If WebFetch fails or hits a paywall, use the snippet date only when the snippet shows one explicitly.

### Step 4: Rank and select 10

Apply [reference/ranking-criteria.md](reference/ranking-criteria.md):

- Rank by impact, novelty, breadth of coverage and source reliability.
- Merge stories that cover the same event and keep the most authoritative source.
- Include at most 3 items per topic and at most 2 per outlet.
- Label developing or unconfirmed stories as such.

### Step 5: Validate (loop until ok)

Pass the items as JSON to the script using a heredoc. The JSON is a list of objects with these fields:

- `rank`: 1–10, in order
- `headline`
- `summary`
- `source`: the outlet name
- `url`
- `published`: ISO-8601 with offset
- `label` (optional): `developing`, `unconfirmed` or `updated`

```bash
python3 ${CLAUDE_SKILL_DIR}/scripts/validate_digest.py --date 2025-01-31 --window-hours 36 --tz-offset +09:00 <<'JSON'
[{"rank": 1, "headline": "Headline text", "summary": "One or two sentences.", "source": "Reuters", "url": "https://www.reuters.com/world/example-story/", "published": "2025-01-31T06:40:00+00:00"}]
JSON
```

Set `--tz-offset` to the `%z` value from Step 1.

The script prints `{"ok": bool, "count": N, "errors": [{"rank", "field", "message"}], "warnings": [...]}` and exits 1 when there are errors.

- If `ok` is false, fix each error. For a stale, undated or duplicate item, or an outlet cap violation, replace it with the next-best verified candidate. Shorten any summary over 60 words. Then re-run the script.
- Repeat until `ok` is true.
- Review each warning, such as a naive timestamp, a summary with more than 2 sentences, or a plain-http link. Change the item if the warning points to a real problem.
- If fewer than 10 verifiable stories exist, pass `--expect N` with the real count. Do not pad the list.

The 36-hour window allows for timezone differences between outlets. Still prefer stories from the last 24 hours.

### Step 6: Render and present

Re-run the same command with `--render --scope "<scope>"`. The script then prints the markdown digest instead of the JSON report. Add `--tz-name <%Z value from Step 1>` (for example `--tz-name JST`) so the source-line times show the timezone abbreviation; without it the script prints `UTC` or `UTC+HH:MM`.

Alternatively, write the digest by hand following [templates/digest.md](templates/digest.md) exactly.

Present the digest with:

- the date
- the scope
- a one-line note on how you selected the sources
- the shortfall, if you found fewer than 10 verifiable stories

## Output format

ALWAYS use the structure in [templates/digest.md](templates/digest.md):

- the title `Top 10 News — <scope> — <YYYY-MM-DD>`
- a numbered list of entries
- a closing "Sources & method" line

Example entry (illustrative format only):

```markdown
3. **Central bank holds rates steady, signals cuts later this year**

   The bank kept its benchmark rate unchanged at its policy meeting and said inflation is cooling faster than expected.

   — Reuters, 14:05 UTC · [link](https://www.reuters.com/markets/example-rate-decision/)
```

## Hard rules

- Never invent stories, facts, dates, times or URLs. Every URL must come from a search result or a fetched page.
- Write summaries only from fetched article text or search snippet text. Keep them neutral: no opinion, no speculation beyond the source.
- Never guess a publish time. An undated item is dropped.
- Report fewer than 10 items rather than including unverified or stale ones.
- Label unconfirmed or developing reports with `label`. Never present them as established fact.
- Do not present the digest until the validator returns `ok: true`.

## Gotchas

- Live blogs and "latest updates" pages show today's update time even when the story began earlier. Include them only if there is a new development today, and describe that development.
- Search snippets often show relative ages ("3 hours ago"). Convert them to an ISO timestamp using the time from Step 1, and mark the item for WebFetch verification if the age is vague ("1 day ago").
- Syndicated wire copy appears on many sites. Cite the original wire service, not the republisher.
- Many outlets use the same URL for different editions with different query strings. The validator treats URLs that differ only in the query string or fragment as duplicates.
