# pasted-image-20260925080323.png

**Type:** image/png (image)

_This image was converted to Markdown by an image-reading model; you are seeing its description, not the image itself._

---

# Medallion Architecture — Data Flow

This image is a left-to-right data architecture diagram illustrating the "Medallion Architecture" pattern. Four data sources on the left feed, via dashed converging lines, into three layered processing cards — Bronze (raw ingestion), Silver (cleansed & conformed), and Gold (business-ready) — which then fan out on the right to three consumption endpoints (Dashboards, KPI Reports, Analytics/ML). Each stage is labelled by a column heading (SOURCES, INGEST, REFINE, AGGREGATE, SERVE). The layout uses a light grey background, white rounded cards, and colour-coded headers (copper/brown for Bronze, grey for Silver, gold/yellow for Gold). The bottom edge shows partially cut-off coloured elements (likely a legend) that are not legible.

## Title & Subtitle
- **Medallion Architecture — Data Flow**
- Sources → Bronze (raw) → Silver (clean) → Gold (business) → Reports

## Column Headings (left to right)
SOURCES | INGEST | REFINE | AGGREGATE | SERVE

## Components

### SOURCES (left column, white cards with grey icons)
| Source | Subtitle | Icon |
|---|---|---|
| CRM | Database | Database cylinder |
| ERP | Transactions | Database cylinder |
| IoT | Streams | Wireless/signal icon |
| Files / Logs | CSV, JSON | Document icon |

### INGEST — Bronze card (copper/brown header)
- Badge: **3**
- Title: **BRONZE**
- Subtitle: Raw Ingestion
- Bullets:
  - Raw / as-is data
  - Append-only
  - Full history
- Illustration: light peach box with horizontal bars of varying length (representing raw records)
- Footer: **Delta / Parquet**

### REFINE — Silver card (grey header)
- Badge: **2**
- Title: **SILVER**
- Subtitle: Cleansed & Conformed
- Bullets:
  - Deduplicated
  - Validated & typed
  - Joined / enriched
- Illustration: a grid/table with a grey header row and one highlighted row
- Footer: a circular dotted "processing/loading" icon (no text)

### AGGREGATE — Gold card (gold/yellow header, gold border)
- Badge: **1**
- Title: **GOLD**
- Subtitle: Business-Ready
- Bullets:
  - Aggregated KPIs
  - Star schema / marts
  - Curated for BI & ML
- Illustration: star schema — central box labelled **FACT** connected to four surrounding pale-yellow dimension boxes
- Footer: **Semantic Model**

### SERVE (right column, white cards with blue icons)
| Output | Subtitle | Icon |
|---|---|---|
| Dashboards | Power BI / Tableau | Bar chart |
| KPI Reports | Finance, Sales | Rising line chart |
| Analytics / ML | Forecasts, Models | Node/network triangle |

## Connections
- CRM → Bronze (dashed grey line, small grey square data packets)
- ERP → Bronze (dashed line, dark blue-grey packet)
- IoT → Bronze (dashed line, dark grey packet)
- Files / Logs → Bronze (dashed line, grey packet)
  - All four source lines converge at a single point before entering the Bronze card, with several small coloured square packets clustered there.
- Bronze → Silver (dashed line with copper/brown circle markers)
- Silver → Gold (dashed line with grey circle markers)
- Gold → Dashboards (dashed line, gold diamond marker)
- Gold → KPI Reports (dashed line, gold diamond marker)
- Gold → Analytics / ML (dashed line, gold diamond marker)
  - The three Gold output lines fan out from a single point on the Gold card's right edge.

## Notes
- Numbered badges run in reverse order (Bronze = 3, Silver = 2, Gold = 1), suggesting Gold is the highest tier of quality.
- A row of small coloured shapes at the very bottom of the image is cut off and unreadable (likely a legend).