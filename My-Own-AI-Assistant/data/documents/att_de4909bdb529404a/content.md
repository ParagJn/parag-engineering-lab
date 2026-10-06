# ChatGPT Image Sep 28, 2026, 10_55_22 AM.png

**Type:** image/png (image)

_This image was converted to Markdown by an image-reading model; you are seeing its description, not the image itself._

---

# Five-Layer Hybrid Data Platform Architecture Diagram

This is an enterprise data architecture diagram for a hybrid on-premises and cloud data platform. It has five numbered, colour-coded layers:

1. **Source Systems** (blue, top)
2. **On-Premises Data Platform** on Oracle Exadata (orange, left middle)
3. **Hybrid Bridge & Governed Sync** (purple, centre)
4. **Cloud Lakehouse Tier** on Azure Databricks & Unity Catalog (green, right middle)
5. **Consumption & Serving Layer** (pink, bottom)

Arrows show data flow between components. Solid and dashed arrows are used, and many arrows carry labels. *Inference:* the source system names (UIQ/SIQ, ADMS, DERMS, POAG, SCADA) suggest an electric utility context.

---

## 1 SOURCE SYSTEMS LAYER

### On-Premises & OT Sources (orange box)

| Icon | Label | Subtitle |
|---|---|---|
| Smart meter | **UIQ / SIQ** | (Smart Metering) |
| Monitor with chart | **ADMS** | (Distribution Mgmt) |
| Solar panel | **DERMS** | (DER Telemetry) |
| Transmission tower | **POAG** | (Outage Data) |
| Database | **Aveva PI** | (SCADA/Historian) |
| Document/list | **MSATS / EIP** | — |

### Cloud & SaaS Sources (blue box)

| Icon | Label | Subtitle |
|---|---|---|
| SAP logo | **SAP S/4HANA EAM** | (Assets) |
| Cloud with sun | **WeatherZone** | (Weather) |
| Green leaf | **Kinetiq / Enablon** | (EHS) |
| Cloud with gear | **Cloud APIs / SaaS Apps** | — |

---

## 2 ON-PREMISES DATA PLATFORM (ORACLE EXADATA / DB)

### Bronze Layer (Raw & Staging)
- **Raw OT & Telemetry Buffers** (Metering, SCADA, Outages, etc.)
- **Replicated Cloud/SAP Staging** (SaaS, SAP, External Data)

### Silver Layer (Enterprise Canonical 3NF Data Model)
- **Unified Domain Models (3NF)**
  - Assets
  - DER
  - Metering
  - Outages
  - Finance
- **Oracle Spatial & Graph Engine** (Network Topology & Asset GIS). It has a map pin / layers icon.
- **7-Year Conformed Historical Store**. It has a database with clock icon.

---

## 3 HYBRID BRIDGE & GOVERNED SYNC

- **Managed ADF / CDC Pipelines** (Automated Conformed Sync). It has an Azure "A" logo between two database icons.
  - Incremental data sync
  - Schema & data conformance
  - Monitoring & alerting
- **FinOps Threshold Gate** (Approval for Heavy Ad-Hoc Extracts). It has a shield with checkmark and coins icon.
  - Usage thresholds
  - Cost monitoring
  - Approval workflow

---

## 4 CLOUD LAKEHOUSE TIER (AZURE DATABRICKS & UNITY CATALOG)

### Gold Layer (Delta Lake)
- **Dimensional Models & Star Schemas** (Facts, Dimensions, Metrics)
- **Domain Data Marts** (Asset Performance, DER, SEB/FE Regulatory)

### Compute & Serving Engines
- **Databricks Serverless SQL Warehouse**
  - High-Concurrency BI & OLAP
  - Direct Lake / DirectQuery
  - Secure & Governed Access
- **Databricks ML & AI Workspace**
  - Forecasting & Predictive Analytics
  - ML Models & GenAI
  - Notebooks & Experiments

---

## 5 CONSUMPTION & SERVING LAYER

### Operational Serving (CI-Fortify Resilient)
- **SNET Core Operational Apps**
  - Network Operations
  - Field Operations
  - Asset Management
- **Real-time Control Room Dashboards**
  - Network Visibility
  - Outage Management
  - Real-time Operations
- **Power BI (via On-Prem Gateway)**
  - Operational Reports
  - Local Network Access
  - Near Real-time

### Enterprise BI & Analytics
- **Power BI (Direct Lake & Import)**
  - Enterprise Dashboards
  - Ad-hoc Analytics
  - Self Service BI
- **Regulatory Reporting (SEB, FE, AER)**
  - Compliance Reports
  - Statutory Submissions
  - Regulatory Analytics
- **ArcGIS Enterprise (Spatial BI)**. It has a globe icon.
  - Network & Asset GIS
  - Spatial Analytics
  - Geospatial Reporting

---

## Data Flows / Connections

| From | To | Label | Style |
|---|---|---|---|
| On-Premises & OT Sources | Bronze Layer (Layer 2) | GoldenGate / CDC / Kafka | Solid orange |
| Cloud & SaaS Sources | Cloud Lakehouse Tier (Layer 4) | ADF / SAP Datasphere / API | Solid blue |
| Raw OT & Telemetry Buffers | Silver Layer | Batch & Micro-Batch ETL (Cleansing & Conformance) | Solid orange |
| Replicated Cloud/SAP Staging | Silver Layer | Standardize & Enrich | Solid orange |
| Bronze Layer | Managed ADF / CDC Pipelines | — | Solid purple |
| Unified Domain Models (3NF) | Managed ADF / CDC Pipelines | — | Solid purple |
| Unified Domain Models (3NF) | Oracle Spatial & Graph Engine | — | Solid orange |
| Unified Domain Models (3NF) | 7-Year Conformed Historical Store | — | Solid orange |
| 7-Year Conformed Historical Store | FinOps Threshold Gate | On-Demand Extract Request | Dashed purple |
| FinOps Threshold Gate | Managed ADF / CDC Pipelines | — | Dashed purple, upward |
| Managed ADF / CDC Pipelines | Gold Layer (Delta Lake) | Incremental Delta Load | Solid green |
| Dimensional Models & Star Schemas and Domain Data Marts | Compute & Serving Engines | — | Green, merging arrows |
| Layer 2, under Oracle Spatial & Graph Engine | SNET Core Operational Apps / Real-time Control Room Dashboards | Low Latency / Local Network (Operational Feeds) | Two solid orange arrows |
| 7-Year Conformed Historical Store | Power BI (via On-Prem Gateway) | — | Solid orange |
| Layer 2, from the Oracle Spatial area | ArcGIS Enterprise (Spatial BI) | Spatial Feature Service | Dashed orange |
| Compute & Serving Engines | Enterprise BI & Analytics (Power BI / Regulatory Reporting area) | Direct Lake / DirectQuery | Two solid green arrows |
| Databricks ML & AI Workspace | ArcGIS Enterprise, right side of Enterprise BI | — | Solid green |