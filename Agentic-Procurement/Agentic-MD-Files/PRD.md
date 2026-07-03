# Product Requirements

## Goal

Build an enterprise procurement simulator.

The simulator should resemble an SAP/Oracle procurement workflow rather than a chatbot.

Every interaction occurs between two AI agents.

A human operator approves every outbound communication.

---

## Companies

Company A

MegaMart Online

Buyer

Uses Gemini.

Company B

FreshFizz Consumer Products

Supplier

Uses Claude.

---

## Product Catalog

Generate 20 fictional CPG products.

Categories

- Soda
- Chips
- Snacks
- Energy Drinks
- Cookies
- Crackers
- Juice

Each product contains

SKU

Name

Category

Inventory

Price

Lead Time

MOQ

Description

---

## Procurement Workflow

Step 1

Buyer creates Material Request Quote.

Human reviews.

Human clicks Send.

---

Step 2

Supplier reviews inventory.

Supplier generates Fulfillment Proposal.

Human reviews.

Human clicks Send.

---

Step 3

Buyer negotiates.

Discount selected SKUs by 3–5%.

Reduce some requested quantities.

Generate Counter Offer.

Human approves.

---

Step 4

Supplier accepts.

Generate Final Fulfillment Letter.

Human approves.

---

Step 5

Buyer generates Purchase Order.

Supplier generates

Invoice

Delivery Order

Workflow completed.

---

## Human in the Loop

Every outbound document pauses.

User must click

Approve

Reject

Edit

Send

No automatic sending.

---

## Persistence

Everything stored as JSON.

Products

Inventory

History

Quotes

Invoices

Purchase Orders

Delivery Orders

Settings

---

## Admin

Rebuild Product Database

Reset Inventory

Reset History

Export JSON

Import JSON

---

## Settings

Gemini Key

Claude Key

Temperature

Model

Persist to JSON.