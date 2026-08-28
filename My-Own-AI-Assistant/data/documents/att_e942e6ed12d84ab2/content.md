# 2026-06-30 DD-69676 Reporting Requirements.docx

**Type:** application/vnd.openxmlformats-officedocument.wordprocessingml.document

---

Content From Jira Task – DD-69676

Type: H++ (Complex) 

Description: Currently, performance and compliance reports for AER/DEECA are manually compiled. Automation is required for reporting on curtailment (due to export limits, voltage, backstop), total generation, and server performance. Must include customers prior to DERMS implementation.

This requirement introduces automated reporting capability for Flexible Exports (FE), compliance, and operational performance to replace the current manual reporting process used for AER, DEECA, and internal operational monitoring.

The solution must automate the capture, calculation, and production of key FE and inverter-related reports, including operational dashboards, and support both:

customers onboarded to DERMS; and

customers that existed prior to DERMS implementation, where applicable.

Reports:
Inverter Compliance: Tracks inverter compliance over time - AS4777.2 non-conformance, breach of export limit, unauthorised export, export exceeding registered capacity, incl Operational Dashboard
AIO 3.9.6 – AS4777.2(2020) Compliant Inverters

FE Performance: Operational compliance report, incl comparison to service commitment and non-compliance to FE across customers (weekly), incl Operational Dashboard
AIO 3.9.8.1 – Export limit compliance
MO – Service Performance Portal
MO – Test for FE limit enablement

Export Services: FE Export Services Report
AIO 3.9.7.1 – Avg duration full export
AIO 3.9.7.2 – Avg duration no export
AIO 3.9.7.3 – Avg upper limit
AIO 3.9.7.4 – Avg time upper limit unavail

Inverter Curtailment: Tracks customer curtailment - static and flex customers, by voltage, network/backstop event, HC, other etc - also includes total potential generation with no curtailment
AIO 3.9.5.8 – Export customers with measured overvoltage
AIO 3.9.5.9 – Export customers with estimated overvoltage

Dependency: interfaces in R1, req for SEB then extend and dev reports for R2

Data Ingestion Requirements (Interfaces)

The solution shall provide interfaces and data pipelines to ingest, validate and store inverter, DERMS, network and operational data required for flexible exports and solar emergency backstop reporting.

Data Sources

Ingestion Functions

The data sources above represent a significant volume of data, therefore the ingestion pipeline should ensure that the data is accurately acquired from the source systems, perform a validation and quality check, store sufficient records for reporting, maintain an auditability of the data and preserve data for both DERMS and pre-DERMS customers where applicable.

Further details TBC

Intermediary Data Tables

The data presented is complex, and translations will be required in order to actually use the data to determine the metrics described in Section 2. There are a few key intermediary data tables that will be required:

Export Limit Data Table

Currently, customers can have a static export limit, or SEB/DERMS export limit (static but with backstop capability), or in future shall have a flexible export limit. The actual export limit that should have been applied at any given time is dependent on several factors:

The customers’ actual export limit (for static customers)

The customers’ devices’ connectivity status, and the time since the last connection was made (ramp down behaviour), as well as the inverter’s control response

Activity of an emergency backstop event (ramp down behaviour)

The customers’ flexible export limit (for flexible export customers)

The customer’s default static fallback export limit

The start date of the customer’s flexible or backstop enabled installation

An interim table is required to translate the requirements above into a usable data structure that shows for any given time interval, a calculated export limit based on the above quantities.

Note: The MRID of each control should be measured against the control response, whether the OEM acknowledges the start and end of the control. If there is no acknowledgement, then we should decide if the device has fallen back to a default limit or is ramping down. This can then be compared to PQ data for dispatch verification.

Other Tables

TBC based on data sources

Derived Metrics and Calculation Requirements

The solution shall calculate intermediary metrics and aggregations that form the basis of regulatory, operational and compliance reporting. This also includes the overlay of business rules on top of the raw datasets and some aggregations to determine compliance status or issues.

Metric Aggregations

All metrics are expected to be calculated at a customer level, typically also at an interval (timeseries) level and aggregated on a regular basis into higher level statistics presented within reports and to the end user via the operational dashboard.

Metrics

The following metrics shall be considered.

Note: All business rules are formally yet to be determined.

For some of the metrics above, the tolerance should be configurable and adjustable as required (but audited), and therefore algorithm parameters should reside in a database table with associated history table.

Compliance Mechanisms 

Separately to the calculation of metrics to identify non-compliance, where a non-compliance is repeatedly detected, a compliance mechanism is required to record and identify repeat offenders and assets.

The existing compliance implementation is described in Confluence at the link below. This should be used as a basis to build out further compliance mechanisms.

https://ausnetservices-adaptivedelivery.atlassian.net/wiki/spaces/FBPKS/pages/2669674911/Compliance+Implementation

Installer Points System

The backend logic for an installer points system will be required. This should consider the following metrics in determining the compliance for an installation:

Compliance to AS4777.2 (2020)

Export Limit Compliance / Unauthorised Export

Export Exceeding Registered Capacity

Commissioning Status

Where an installer has multiple consecutive installations over a given time period that fail to meet the compliance requirements above, the installer shall be flagged in the system with a point increase. This should be a dynamic count that is decremented after some time or successful installations, however with history recorded.

The points system should be used to flag regular non-conformers, however no customer/installer should be notified of this as part of DEFE’s current scope of works.

Update Frequency

Definition of Non-Conformance/Compliance

TBC

Reporting Requirements

There are two types of reporting requirements outlined in this program; formal reports and the operational dashboard.

Formal Reports

Annual Information Order

The AIO is a requirement of the DNSP delivered on a yearly basis, to provide the regulator with information about the DNSP’s network. A specific report for the AIO should be available within the dashboard (extract) or via other extraction means. This should aggregate metrics calculated throughout the year into yearly figures.

The “FE related” aspects of the AIO encompass:

Other

Other formal reports TBC. May be covered by simply selecting appropriate date range on dashboard with an “export” report button.

Dashboards

Dashboard may contain:

A total compliance metric for the fleet

A compliance rate over time plot (bar plot, per day or per week, for the selected timeframe)

An issue type and prevalence plot (horizontal bar plot of compliance area and total count, for the selected timeframe)

A pie-chart of curtailed devices by the curtailment type (for the selected timeframe – connected, comms failure, network constraint curtailment, voltage curtailment etc)

Devices in service count

Plot of telemetry health over time

Timeseries plot of total allowed export vs total export level

Timeseries plot of average export vs service commitment

List of new DERs with an issue over the last X days

Geographic map of hotspots for non-compliance, or tabulated view with segmentation by network or geographic area

Statistics divided by “solar inverter”, “battery inverter”, or customer “has solar”, “has battery”

System availability metric