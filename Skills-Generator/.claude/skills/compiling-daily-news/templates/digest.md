# Digest Template

ALWAYS use this exact structure. Replace the angle-bracket fields. Keep the em dashes (—) and the middle dot (·) as shown.

```markdown
# Top 10 News — <scope> — <YYYY-MM-DD>

1. **<Headline>**

   <1–2 sentence neutral summary drawn only from the article or snippet text.>

   — <Source>, <HH:MM TZ> · [link](<canonical URL>)

2. **<Headline>**

   <Summary.>

   — <Source>, <HH:MM TZ> · [link](<canonical URL>)

(continue through item 10)

**Sources & method:** <One line: where the stories were searched, how many outlets, the verification window, and the ranking basis.>
```

## Field rules

- **Title**
  - `<scope>` is `Global` when there is no argument. Otherwise it is the region or topic as the user gave it, in title case (`Japan`, `UK`, `Tech & AI`).
  - The date is the target date from Step 1, in `YYYY-MM-DD` format.
  - If fewer than 10 stories were verified, use the real count in the title (`Top 7 News`). Add this line directly before "Sources & method": `_Only <N> verifiable stories published within the window were found for this scope; the list was not padded._`
- **Headline**
  - Keep it in bold.
  - Write a factual rewrite or the outlet's headline without clickbait.
  - For labelled items, prefix the label in brackets inside the bold: `**[Developing] <Headline>**`.
- **Summary**
  - Write 1–2 sentences and at most 60 words.
  - Keep it neutral, with no adjectives of judgement.
  - Attribute uncertain figures ("officials said").
- **Source line**
  - `<Source>` is the outlet name.
  - The time is the publish or update time in 24-hour `HH:MM`, converted to the user's timezone from Step 1, followed by that timezone's abbreviation (or `UTC`).
  - The link text is always `link`.
- **Sources & method**
  - Write one line only.
  - Example: `**Sources & method:** Searched the web on 2025-01-31 for Global news; 10 stories from 8 outlets (AP, BBC, Bloomberg, Reuters, The Guardian); publish times verified within 36 hours of the end of 2025-01-31 (UTC); ranked by impact, novelty and breadth of coverage.`

## Example entry

```markdown
4. **[Developing] Magnitude 6.8 earthquake strikes off northern coast**

   The quake struck offshore early on Friday and triggered a brief tsunami advisory, according to the national weather agency. No deaths had been reported at the time of publication.

   — NHK World, 06:12 JST · [link](https://www3.nhk.or.jp/nhkworld/en/news/example-quake/)
```
