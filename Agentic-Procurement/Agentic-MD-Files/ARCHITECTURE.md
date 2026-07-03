# Architecture

## Frontend

React

Pages

Dashboard

Workflow

History

Admin

Settings

---

## Backend

FastAPI

Layers

API

↓

Workflow Engine

↓

Agent Services

↓

JSON Repository

↓

Filesystem

---

## Agent Layer

BuyerAgent

Gemini

SupplierAgent

Claude

Each agent returns structured JSON.

---

## Repository Layer

ProductsRepository

InventoryRepository

HistoryRepository

WorkflowRepository

SettingsRepository

---

## Storage

data/

products.json

inventory.json

history.json

quotes/

fulfillments/

purchase_orders/

delivery_orders/

invoices/

settings.json

---

## APIs

GET /products

POST /workflow/start

POST /workflow/send

POST /workflow/counter

POST /workflow/finalize

GET /history

GET /settings

POST /settings

POST /admin/rebuild

POST /admin/reset

---

## Startup

start.sh

Activate

/Users/paragjain/dev-works/myenv

Run

FastAPI

React

Open browser