from pydantic import BaseModel
from typing import List, Dict, Any, Optional

class TimelineEvent(BaseModel):
    timestamp: str
    event: str
    description: str
    actor: str  # "Buyer", "Supplier", "Human"

class WorkflowDocument(BaseModel):
    id: str
    type: str  # "MRQ", "Proposal", "CounterOffer", "FinalLetter", "PO", "Invoice", "DO"
    created_at: str
    created_by: str  # "Buyer", "Supplier", "Human"
    content: Dict[str, Any]  # The JSON details of the document (items, totals, etc.)
    letter_text: str

class WorkflowState(BaseModel):
    workflow_id: str
    status: str  # "ACTIVE", "COMPLETED", "REJECTED"
    current_step: int  # 1 to 5
    documents: List[WorkflowDocument] = []
    timeline: List[TimelineEvent] = []
    current_draft: Optional[WorkflowDocument] = None

class HistorySummary(BaseModel):
    workflow_id: str
    start_time: str
    end_time: str
    documents: List[Dict[str, Any]]
    summary: str
