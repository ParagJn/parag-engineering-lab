# Ranking Criteria for the Daily Digest

## Contents
- Scoring the candidates
- Source reliability tiers
- Diversity caps
- Merging duplicate events
- Developing and unconfirmed stories
- What to exclude
- Query recipes

## Scoring the candidates

Score each verified candidate on four factors, then sort by the combined judgement. Impact outweighs everything else. Use the other factors to order stories of similar impact.

1. **Impact**: how many people are affected and how severely.
   - Highest: deaths or mass displacement, war and ceasefire developments, national elections and changes of government, major disasters, market moves across whole economies, and public-health emergencies.
   - Middle: major policy or court decisions, large corporate events (mergers of household-name companies, mass layoffs), and significant scientific results.
   - Lowest: celebrity news, single-company product updates, and local incidents without wider effect.
2. **Novelty**: something new happened on the target date.
   - A new decision, a new figure, a new event or a confirmed outcome ranks high.
   - A background explainer, an anniversary piece or "what we know so far" with no new facts ranks low or is dropped.
3. **Breadth of coverage**: several independent major outlets report the event on the target date. If three or more tier-1 or tier-2 outlets lead with it, it is a top-5 contender. A story found in only one outlet ranks lower unless it is an exclusive from a tier-1 source.
4. **Source reliability**: see the tiers below. Break ties in favour of the higher tier.

For a topic scope, measure impact within that field. For example, for tech: effects on large user bases, regulation and the industry, not general-audience fame.

## Source reliability tiers

- **Tier 1**: wire services (Reuters, AP, AFP, Bloomberg, Kyodo, dpa, PA Media) and public broadcasters with strong newsrooms (BBC, NHK, Deutsche Welle, ABC Australia, CBC).
- **Tier 2**: major national newspapers and outlets (The Guardian, The New York Times, The Washington Post, Financial Times, The Wall Street Journal, Le Monde, The Japan Times, Nikkei Asia, Der Spiegel, Al Jazeera English), and established specialist outlets for topic scopes (The Verge, Ars Technica, TechCrunch and Wired for tech; CNBC for business; ESPN for sports; Nature news and Science for science).
- **Tier 3**: other reputable regional or trade outlets. Use them when they are the primary source for a regional story.
- **Avoid**:
  - content farms and SEO rewrite sites
  - aggregators (cite the original outlet instead)
  - press-release wires, unless the release itself is the news and no outlet has covered it
  - paywalled-only sources when a free tier-1 or tier-2 report of the same facts exists
  - opinion, editorial, analysis and sponsored pieces
  - social media posts as the sole source

## Diversity caps

- **Topic**: at most 3 items per topic. Topics include politics or government, conflict or security, business or markets, technology, science or health, climate or environment, disasters, sports, and culture. For a topic scope, apply the cap to sub-topics. For tech, the sub-topics are AI, devices, platforms or social media, security, regulation, and chips or hardware.
- **Outlet**: at most 2 items per outlet. The validator enforces this cap. When a third story from the same outlet qualifies, find the same story in another tier-1 or tier-2 outlet, or pick the next candidate.
- **Geography** (global scope): avoid more than 4 items about a single country unless events clearly justify it.

## Merging duplicate events

Treat items as the same event when they share the main actor, the action and the date, even if the headlines differ. For example, "Company X unveils model Y" and "Y launch: Company X takes on rivals" are the same event.

- Keep one item per event.
- Cite the most authoritative source: the tier-1 source first; within a tier, the outlet with the most complete facts.
- If a later report adds a key new fact, such as a confirmed death toll, include that fact in the summary only if you can verify it in a fetched article or snippet.
- A follow-on event with its own new development (for example, a market reaction to a policy decision) may be a separate item only if it is independently significant. Otherwise, fold it into the main item's summary.

## Developing and unconfirmed stories

- Give an item `"label": "developing"` when the facts are still changing (ongoing disasters, active incidents, counts in progress). Say what is known and attribute any figures ("officials said", "according to Reuters").
- Give an item `"label": "unconfirmed"` when a single outlet reports it based on anonymous sources, or when authorities have not confirmed it. Include it only if it is high-impact and comes from a tier-1 or tier-2 outlet.
- Give an item `"label": "updated"` when the main development is an update to a story that began before the target date.
- Never merge a rumour with confirmed facts in one summary without attribution.

## What to exclude

- Stories whose only timestamp is older than 24 hours before the target date, even if they still trend.
- Pages with no visible or retrievable publish or update time.
- Quizzes, galleries, horoscopes, "live TV" pages and newsletter landing pages.
- Duplicate wire copy republished by other sites.

## Query recipes

Replace `<date>` with the long-form date, for example "January 31, 2025". Run 4–6 of these queries per request.

### Global (no argument)
- `top news <date>`
- `world news today Reuters`
- `AP top headlines today`
- `BBC news world today`
- `business markets news <date>`
- `technology science news <date>`

### Country or region (for example Japan, UK, Germany, India)
- `<country> news <date>`
- `<country> top stories today`
- `Reuters <country> today` and `AP <country>`
- English-language national outlets:
  - Japan: `NHK World`, `Japan Times`, `Kyodo`, `Nikkei Asia`
  - UK: `BBC`, `Guardian`, `PA Media`
  - Germany: `Deutsche Welle`, `Spiegel International`
  - India: `The Hindu`, `Indian Express`, `PTI`
- `<country> politics today`, `<country> economy news <date>`

Keep only stories that are about the country or region or directly affect it. For example, a US tariff decision aimed at the country qualifies. A generic global story that merely mentions it does not.

### Topic (for example tech, AI, business, sports, science)
- `<topic> news <date>`
- `biggest <topic> news today`
- one query per sub-topic, for example `AI news today`, `cybersecurity breach today`, `tech regulation news <date>`, `chip semiconductor news today`
- specialist outlets: `The Verge <topic> today`, `TechCrunch today`, `Reuters technology`, `Bloomberg technology`
- sports: `<league or sport> results today`, `ESPN top stories`, `BBC Sport`

For topic scopes, check the sub-topic cap and the outlet cap before you validate.
