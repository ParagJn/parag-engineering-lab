Now comes the fun part. 

I want to use the ingelligence that we built into the backend to generate a Statement of Work (SoW) for a project.
Use the background provided, assumptions, and out-of-scope information to generate a professional SoW document.
I will give a sample along with section headers. Just provide the content for each section based on the information provided in the project model.

Sample Starts 

**Background and Context**

The current Gas Systems Refresh (GSR) reporting capability is delivered through a collection of Cognos reports that support operational performance monitoring, regulatory obligations, and business reporting requirements. 

These reports are relied upon by business stakeholders for compliance reporting, service level monitoring, outage performance analysis, customer service performance tracking, and safety reporting.

As part of the GSR Program, AusNet is enhancing its reporting capability to support the application landscape comprising SAP IS-U & PoAG. The reporting solution will incorporate new business reporting requirements, consolidate existing reports where practical, and decommission reports that are no longer required.

The GSR DnA Phase 1 engagement will establish the reporting design and data foundations. This will enable approved gas reporting datasets to be made available for reporting and analytics.

The scope for Phase 1 is: 
•	Load the data to approximately 140 existing tables that has both Gas & Electricity Data, in addition,  one new table is to be built and loaded that will contain Gas Data Only. 
•	Out of the 140 Tables, 13 tables will be used to load the gas data using a filter attribute. The additional 127 tables will be derived for the GSR reporting dataset and loaded as per requirements. 
•	Filter and replicate existing electricity reporting structures for gas reporting where possible
•	Replicate PoAG/GSR source data into Databricks and build the required master tables and filtered datasets on top of CDC-fed data
•	Produce an approved design and implementation plan for report development


**1.3	Scope

1.3.1	Gas Reporting Enablement using existing electricity 

Scope Overview
Establish the foundation for gas reporting by extending the existing electricity reporting framework. The approach is to reuse the current reporting structures wherever possible and introduce filtering logic to derive gas reporting datasets without creating a separate ingestion framework.

Scope of Work
•	Analyse the existing electricity reporting datasets and identify the changes required to support gas reporting. 140 tables will be extracted for both Gas & Electricity Data. Of the 140 Tables, 13 tables will be filtered using 1 attribute to extract Gas data and loaded. The remaining 127 tables will be derived from the 13 tables. 
•	Create and load 1 new table with Gas data only, this table will not have any electricity data. 
•	Implement filtering logic to derive the required gas reporting datasets from the replicated source data.
•	Create the required gas reporting objects while reusing the existing electricity reporting structures where applicable.
•	Validate the filtering logic to separate out gas data  from source systems through to the reporting datasets.  No change to electricity data will be performed. .
•	Perform unit testing to verify that the filtered datasets are correctly generated and available for downstream processing.

Key Outcomes
•	Gas data load capability established using the existing electricity data ingestion framework.
•	Filtering logic implemented for the identified reporting datasets.
•	Required gas reporting objects created.
•	End-to-end data flow validated from source systems to reporting datasets.
•	Unit-tested filtering solution ready for CDC-based ingestion.


1.3.2	CDC Data Ingestion & Data Replication

Scope Overview
Build the data ingestion framework required to replicate source data into the Databricks platform using Change Data Capture (CDC) . 

Scope of Work
•	Analyse the source systems and define the source-to-target mappings for the required reporting datasets.
•	Configure the CDC environment by defining the source and target connections, security, logging, and platform settings. 
•	Build a common ingestion framework for both electricity and gas datasets.
•	Implement CDC flows to replicate the required source tables into the target platform.
•	Validate replicated datasets to ensure completeness and consistency prior to downstream processing.
•	Perform unit testing of the CDC configuration and replication processes.

Key Outcomes
•	CDC environment configured and operational.
•	Source data successfully replicated into the Databricks platform.
•	Data replication validated through unit testing.


1.3.3	Data Platform Development

Scope Overview
Develop the Databricks data platform required to process, organize, and prepare reporting datasets. 
Build a scalable and maintainable processing framework using reusable data pipelines and notebook components.

Scope of Work
•	Configure the required ADLS folder structure to support data ingestion and processing.
•	Develop the Databricks data model for the reporting solution.
•	Create the required data pipelines and notebook framework to process reporting datasets.
•	Configure scheduling and monitoring for automated execution.
•	Validate approximately 140 reporting tables through unit testing to confirm successful processing.

Key Outcomes
•	Databricks Data pipelines and notebook framework developed.
•	ADLS storage structure configured.
•	Scheduling and monitoring framework established.
•	Processed reporting datasets validated and available for report development.


1.3.4	Detailed Design

Scope Overview
Develop the As Built Document (DEL01) by defining the required interface specifications, data ingestion changes, and technical design required to support the new reporting solution in Phase 2. 

Prepare the report design and wireframe layouts to establish the foundation for report development in Phase 2. 

Scope of Work
•	Review the existing GSR Program solution definition document and contribute to any deviations required for DnA.
•	Prepare the As Built Document for the proposed solution.
•	Define the data ingestion approach, including the required interface specifications and data flow.
•	Prepare report design and wireframe layouts for the required report changes.
•	Collaborate with business and technical stakeholders to validate the proposed design and incorporate feedback.
•	Participate in Critical Design Review (CDR) endorsement activities.

Key Outcomes:
•	As Bulit Document (DEL01)
•	Interface specifications (DEL03) and data ingestion design.
•	Report layouts and wireframes.
•	Input to CDR


**1.3.5	Out of scope

Scope Area	Details
Development	•	Development of any data load jobs beyond the 13 of 140 identified gas tables received from SAP. 
•	Business transformation of any datasets. The only requirement is the addition of a filter to one attribute to distinguish gas data from electricity data.  
•	Changes to the existing data load framework or any jobs processing electricity data.  
•	Development of the 34 reports is excluded from the Phase 1 scope.
Testing	•	System Testing is out of scope for this engagement, as agreed with the GSR Program. A standalone System Testing phase would require resource-intensive mock test data creation. Solution testing will be performed through SIT and UAT in Phase 2, with IBM supporting data loadsand defect remediation..
•	Regression testing is limited to validating the GSR DnA solution changes delivered under this SOW. Investigation, analysis and remediation of defects not directly attributable to those changes are excluded from scope.
Performance	•	Performance testing and optimisation are excluded from scope, including the investigation and resolution of performance issues arising from increased data volumes, infrastructure constraints, or existing platform limitations.  
Business Logic	•	The scope includes direct source-to-target data mappings only.  Activities requiring data transformation, multi-table joins, derived calculations, data enrichment, or new business rules are not in scope for this phase. 

sample Ends. 

Let have the intelligence that will first anlayze the content provided by the user in background especially and then little bit on assumptions and out-of-scope. If this content is not good enough, it will ask the user to provide more information. Once the content is good enough, it will generate a draft SoW document based on the sample provided above.

On the UI side, Add a button "SoW Draft". Clicking on that button will generate a draft SoW document using the backend AI capabilities. The generated document should be displayed in a modal or a new page, allowing the user to review and edit it before finalizing. 
and finally give an option to save it as word docucument. 