from pydantic import BaseModel
from typing import List, Optional

class QuoteItem(BaseModel):
    sku: str
    requested_quantity: int
    quoted_quantity: int
    requested_price: float
    quoted_price: float
    discount: float  # e.g., 0.03 for 3%
    final_price: float
    accepted: bool = True

class QuoteDocument(BaseModel):
    workflow_id: str
    quote_id: str
    created_at: str
    buyer: str
    supplier: str
    items: List[QuoteItem]
    status: str  # PENDING, APPROVED, SENT
    letter_text: Optional[str] = None
