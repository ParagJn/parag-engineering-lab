# JSON Models

## Product

{
    "sku": "",
    "name": "",
    "category": "",
    "price": 0,
    "inventory": 0,
    "lead_time": 0,
    "moq": 0,
    "description": ""
}

---

## Quote

{
    "workflow_id": "",
    "quote_id": "",
    "created_at": "",
    "buyer": "",
    "supplier": "",
    "items": [],
    "status": ""
}

---

## Quote Item

{
    "sku": "",
    "requested_quantity": 0,
    "quoted_quantity": 0,
    "requested_price": 0,
    "quoted_price": 0,
    "discount": 0,
    "final_price": 0
}

---

## Workflow

{
    "workflow_id": "",
    "status": "",
    "documents": [],
    "timeline": []
}

---

## History

{
    "workflow_id": "",
    "start_time": "",
    "end_time": "",
    "documents": [],
    "summary": ""
}