# Data Story Studio

Upload one or more CSV or Excel files and get an AI-built, animated dashboard that tells the story in the data. You can explore it, question it, rework it and share it.

> Analyse the data. Discover the story. Design the visualization. Animate the insight.

## Run

```bash
cp .env.example .env     # add IBM_ICA_ENDPOINT / IBM_ICA_API_KEY
./start.sh               # backend :8020, frontend :5190
```

Open http://localhost:5190 and click **Try the example** for a guided tour. Datasets you've already built appear under **Recent**; **View dashboard** opens the saved dashboard without regenerating it.

### Guided example (`data/Example/`)

Brightleaf Coffee Co. is a fictional six-store coffee chain with two years of data across four related files:

| File | What it is | Links to |
|---|---|---|
| `orders.csv` | about 19K orders: hourly timestamp, store, product, channel, quantity, discount, revenue; includes 36 duplicate rows | — |
| `products.csv` | menu: name, category, price | `orders.product_id` |
| `stores.xlsx` | stores: name, Australian state, area, format (Excel) | `orders.store_id` |
| `feedback.csv` | survey answers for about 30% of orders: rating, wait time, would recommend | `orders.order_id` (partial match) |

Planted stories for the analysis to find: delivery grows from about 8% to 28% of orders; a new store opens in March 2025; Riverside closes for three weeks in August 2025; hot drink prices rise 8% in January 2026; cold drinks peak in summer; a weekday 7–9am rush; longer waits (peak hours, delivery) go with lower ratings. The six stores sit in six Australian states, so revenue by state is drawn as a **map** (the example's map panel).

Loading the example shows a step-by-step guide on the readiness screen and on the dashboard. To regenerate the data: `python scripts/make_example.py`.

### More samples

The `samples/` folder has more fictional datasets:

| Sample | Shows |
|---|---|
| `service_tickets.csv` | Hourly timestamps, a derived *hours to resolve* measure, an outage spike, channel mix shift |
| `retail_orders.csv` + `retail_products.csv` + `retail_stores.xlsx` | Multi-file join detection (many-to-one, with match rates), DD/MM/YYYY dates |
| `small_web_traffic.csv` | The readiness gate: 18 rows, which triggers "more data recommended" |
| `service_tickets.csv` + `small_web_traffic.csv` | Unrelated files: you're asked how they link, or to analyse them separately |

Without IBM ICA configured, everything still works except Q&A and free-form redraws. The dashboard then uses computed titles instead of AI narrative, and the Executive Summary is assembled from those computed findings.

## Flow

1. **Upload**: CSV/TSV/Excel (each sheet becomes a table). Header rows are detected, null tokens normalised, currency and % symbols stripped, and types inferred. Numeric codes (`*_code`, FIPS, ZIP, postcodes) are treated as identifiers or categories, never summed.
   - **Preview data** on each file opens a paged, sortable, searchable view of the rows exactly as they'll be analysed, with each column's role and emptiness in the header.
2. **Readiness gate**: decisions come from computed numbers. The LLM only phrases the file descriptions and suggests goals.
   - Fewer than `MIN_ROWS` (default 1,000) records blocks the build with "more data recommended". You can upload more, or *analyse anyway* to get a dashboard marked low-confidence.
   - With several files, it detects **joins** (shared keys, value overlap, match rate, cardinality) and **unions** (same columns). Files it can't link block the build until you name the link columns or choose to analyse each file separately.
   - Quality checks: mostly-empty columns, duplicate rows (one-click dedupe), ambiguous day/month dates (one-click switch), mixed date formats, unparsed values, codes with leading zeros, numeric IDs.
   - **Long-format tables**: when a column names the measure each row holds (e.g. `measure_name` with values on very different scales), adding rows together would mix units. Each measure gets its own dashboard tab instead (up to 20), and within a tab the value column leads and is averaged.
   - Optional goal and audience.
3. **Insight discovery** (deterministic): about 25 candidate views are scored by business significance. Candidates cover KPI movement, trend fit, robust anomalies, period-over-period change with driver attribution (waterfall), concentration (top-N share, 80% rule), segment growth, time-of-week heatmaps, correlations and distributions. Partial first and last periods are detected and excluded from trends.
   - **Maps** appear only when a dimension's values are places: at least 85% of its records name a country (names or ISO codes) or a state/province of the US, Canada, Australia, India, Brazil, China, Russia, Indonesia or South Africa (names or postal codes). The check reads values, not column names, so "Region = North / South", departments or cities stay as bar charts. A code-only column needs at least 6 matched regions so abbreviations like `HR` / `IT` aren't mistaken for countries. Boundaries are Natural Earth (public domain), bundled in `backend/geo/`. World shapes are 1:110m, so very small countries are hard to see. There are no city or county maps.
4. **Story** (IBM ICA): the model picks and orders panels into headline, evidence, drivers and detail, and writes headings and insights (what happened, how big, evidence, why it may matter, next step). A **number guard** drops any sentence that cites a figure not present in the computed facts.
5. **Explore**:
   - Click a bar, series, period, heatmap cell or map region to filter every panel. Titles are recomputed under the filter.
   - Every panel has *Data* (sortable, downloadable as CSV) and *Query* (the exact SQL, editable and re-runnable read-only).
   - Click a KPI to see its definition, record count, its trend by period and the query behind it.
   - **Ask** in natural language. The model writes one SELECT, which is validated, sandboxed and retried once on error. The answer is phrased from the result only, and you can pin it to the dashboard.
   - **Redraw** a panel: switch chart type or time grain directly, or describe the change ("split by region", "average instead"). Undo is supported.
   - *Show more findings*: candidates the story left out can be added back.
6. **Executive Summary**: board-ready commentary written from the dashboard's computed facts: bottom line, key metrics table (taken straight from the KPI cards), what happened, risks, opportunities, recommended actions, and notes on the data. The number guard applies. It's saved with the dashboard and can be copied, or downloaded as **Markdown** or **PDF**, to paste into reports. *Rewrite* regenerates it.
7. **Export**:
   - **HTML**: one self-contained file with the viewer bundle and data embedded, plus the map boundaries the dashboard uses. It works offline with animation, tooltips, data tables and SQL.
   - **PDF**: the same report printed through headless Chromium with motion off, one section per page.
7. **Executive deck (PPTX)**: the toolbar's *PPTX* button builds a 5-7 slide briefing in the dashboard's theme: title with the one-sentence central takeaway, the numbers at a glance, 2-3 evidence slides (headline that states the point, a native editable chart, supporting points, *so what*), the decisions to take, and a closing slide of missing evidence and next steps. The plan is number-guarded like the summary and cached on the dashboard; without ICA it is assembled from the computed story. Clicking *PPTX* opens a picker with two independent choices: a **design** (slide layout and fonts: Classic, Editorial, Split, Focus) and a **colour palette** (Studio, Boardroom, Midnight, Evergreen), 16 combinations in all; the design previews recolour live as you pick a palette, and the last choice is remembered. Designs and palettes live in `DESIGNS` / `PALETTES` in `backend/deck.py`; a design is one function per slide kind in `SLIDES`. Active filters apply to the charts. Speaker notes are included.

## Architecture

```
backend/
  ingest.py      file -> typed frame -> DuckDB table (type inference, header detection, date formats)
  profile.py     column profiling + semantic roles (measure / dimension / time / id / flag / text)
  readiness.py   the readiness gate: volume, relationships, quality issues
  model.py       analysis scopes: DuckDB views with unions, lookup joins, derived durations
  panels.py      panel recipes -> SQL -> data + chart encoding + computed, evidence-backed titles
  maps.py        place detection (values -> countries / states) and boundary GeoJSON for map panels
  geo/           Natural Earth boundaries: countries (1:110m), states/provinces of 9 countries (1:50m)
  insights.py    candidate generation and significance scoring; deterministic default story
  story.py       IBM ICA layer: compose story, Q&A, redraw; number guard
  brief.py       executive summary (Markdown + PDF), number-guarded
  workspace.py   dataset storage (data/<id>/), sandboxed read-only queries with timeout
  export.py      self-contained HTML + Playwright PDF
  deck.py        executive PowerPoint (5-7 slides, native charts, number-guarded plan)
  main.py        FastAPI routes
frontend/src/
  charts/        ECharts option builders (validated palette, thin marks, purposeful motion)
  dashboard/     story view, KPI cards, panel cards, Q&A drawer
  setup/         upload + readiness screens, data previewer
  viewer.tsx     entry for the offline viewer bundled into HTML exports
```

**Trust rules**
- The AI never draws charts or types numbers. It edits *recipes* (structured specs), or writes a SELECT that is parsed, checked to be a single read-only statement, and run on a DuckDB connection with filesystem access disabled.
- Missing values stay missing; they are never treated as zero.
- Rates and averages are weighted correctly when grouped into "Other".
- Titles say what was observed. Interpretations are labelled *Hypothesis*.

**Motion**: KPI values count up, sparklines and trend lines draw themselves, bars grow in sequence, and waterfall steps appear one by one. Sections reveal on scroll, and filter changes morph the charts. Motion respects `prefers-reduced-motion`, and there is a *Motion on/off* toggle and a *Replay* button.

## Config (`.env`)

| Key | Default | |
|---|---|---|
| `IBM_ICA_ENDPOINT`, `IBM_ICA_API_KEY` | — | required for the AI narrative and Q&A |
| `IBM_ICA_MODEL_ID` | `claude-sonnet-5-5` | `claude-opus-5-5` is rejected by the IBM gateway for this key (E003) as of 2026-10-17 |
| `IBM_ICA_FALLBACK_MODEL_ID` | `claude-sonnet-5` | retried once when a reply is blocked by the content filter |
| `MIN_ROWS` | `1000` | readiness volume threshold |
| `MAX_UPLOAD_MB` | `200` | |
