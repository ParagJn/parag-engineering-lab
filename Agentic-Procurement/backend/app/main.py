import os
import logging
from fastapi import FastAPI, HTTPException, Body
from fastapi.middleware.cors import CORSMiddleware
from typing import List, Dict, Any, Optional
from pydantic import BaseModel

from app.models.settings import Settings
from app.models.product import Product
from app.models.workflow import WorkflowState, HistorySummary
from app.repositories.products_repo import ProductsRepository
from app.repositories.settings_repo import SettingsRepository
from app.repositories.history_repo import HistoryRepository
from app.repositories.workflow_repo import WorkflowRepository
from app.services.agent_service import AgentService
from app.services.workflow_engine import WorkflowEngine

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(title="Agentic Procurement Simulator API")

# Enable CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Resolve directories
# File is in backend/app/main.py -> parent of parent of parent is workspace root
BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
DATA_DIR = os.path.join(BASE_DIR, "data")

# Wire up dependencies
products_repo = ProductsRepository(DATA_DIR)
settings_repo = SettingsRepository(DATA_DIR)
history_repo = HistoryRepository(DATA_DIR)
workflow_repo = WorkflowRepository(DATA_DIR)
agent_service = AgentService()

workflow_engine = WorkflowEngine(
    workflow_repo=workflow_repo,
    products_repo=products_repo,
    history_repo=history_repo,
    settings_repo=settings_repo,
    agent_service=agent_service
)

# Pydantic schemas for request payloads
class UpdateDraftPayload(BaseModel):
    letter_text: str
    items: List[Dict[str, Any]]

# --- API Endpoints ---

@app.get("/products", response_model=List[Product])
def get_products():
    """Retrieve catalog products along with dynamic inventory counts."""
    try:
        return products_repo.get_all()
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/settings", response_model=Settings)
def get_settings():
    """Load settings configurations (API keys, models, temperature)."""
    try:
        return settings_repo.load_settings()
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/settings", response_model=Settings)
def save_settings(settings: Settings):
    """Save settings configurations."""
    try:
        settings_repo.save_settings(settings)
        return settings
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/history", response_model=List[HistorySummary])
def get_history():
    """Retrieve completed workflow history."""
    try:
        return history_repo.get_all()
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

# --- Workflow Endpoints ---

@app.get("/workflow/active", response_model=List[WorkflowState])
def list_active_workflows():
    """List all active (running or suspended) workflows."""
    try:
        return workflow_repo.list_active()
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/workflow/{workflow_id}", response_model=WorkflowState)
def get_workflow(workflow_id: str):
    """Retrieve state of a specific workflow."""
    state = workflow_repo.get(workflow_id)
    if not state:
        raise HTTPException(status_code=404, detail="Workflow not found")
    return state

@app.get("/workflow/{workflow_id}/report")
def get_workflow_report(workflow_id: str):
    """Retrieve or generate the high level report for a workflow."""
    try:
        # Check history first
        histories = history_repo.get_all()
        for h in histories:
            if h.workflow_id == workflow_id:
                return {"workflow_id": workflow_id, "report": h.summary}
        
        # If not in history, look in active
        state = workflow_repo.get(workflow_id)
        if not state:
            raise HTTPException(status_code=404, detail="Workflow not found")
            
        settings = settings_repo.load_settings()
        report = agent_service.generate_negotiation_summary(
            settings, state.timeline, state.documents
        )
        return {"workflow_id": workflow_id, "report": report}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/workflow/start", response_model=WorkflowState)
def start_workflow():
    """Initiates a new procurement simulation workflow and drafts the first Buyer MRQ."""
    try:
        return workflow_engine.start_workflow()
    except Exception as e:
        logger.error(f"Error starting workflow: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/workflow/{workflow_id}/edit", response_model=WorkflowState)
def edit_workflow_draft(workflow_id: str, payload: UpdateDraftPayload):
    """Allows human operator to edit the current draft letter or items before approval."""
    try:
        return workflow_engine.update_draft(
            workflow_id=workflow_id,
            letter_text=payload.letter_text,
            items_data=payload.items
        )
    except ValueError as ve:
        raise HTTPException(status_code=400, detail=str(ve))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/workflow/{workflow_id}/send", response_model=WorkflowState)
def approve_and_send_document(workflow_id: str):
    """Approves the draft document, sends it to the recipient, and triggers the next agent."""
    try:
        return workflow_engine.send_document(workflow_id)
    except ValueError as ve:
        raise HTTPException(status_code=400, detail=str(ve))
    except Exception as e:
        logger.error(f"Error advancing workflow: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/workflow/{workflow_id}/reject", response_model=WorkflowState)
def reject_workflow(workflow_id: str):
    """Cancels and rejects the current workflow."""
    try:
        return workflow_engine.reject_workflow(workflow_id)
    except ValueError as ve:
        raise HTTPException(status_code=400, detail=str(ve))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

# --- Admin Endpoints ---

@app.post("/admin/rebuild")
def rebuild_db():
    """Regenerates the database catalog from default seed values."""
    try:
        products_repo.rebuild_db()
        return {"status": "success", "message": "Product catalog database rebuilt successfully."}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/admin/reset")
def reset_db():
    """Clears history logs and resets product stock levels."""
    try:
        products_repo.reset_inventory()
        history_repo.clear()
        workflow_repo.clear_all()
        return {"status": "success", "message": "Inventory, history, and active sessions reset successfully."}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
