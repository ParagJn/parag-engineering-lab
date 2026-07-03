import uuid
import logging
from datetime import datetime
from typing import Dict, Any, List, Optional

from app.models.workflow import WorkflowState, WorkflowDocument, TimelineEvent, HistorySummary
from app.models.quote import QuoteDocument, QuoteItem
from app.repositories.workflow_repo import WorkflowRepository
from app.repositories.products_repo import ProductsRepository
from app.repositories.history_repo import HistoryRepository
from app.repositories.settings_repo import SettingsRepository
from app.services.agent_service import AgentService

logger = logging.getLogger(__name__)

class WorkflowEngine:
    def __init__(
        self,
        workflow_repo: WorkflowRepository,
        products_repo: ProductsRepository,
        history_repo: HistoryRepository,
        settings_repo: SettingsRepository,
        agent_service: AgentService
    ):
        self.workflow_repo = workflow_repo
        self.products_repo = products_repo
        self.history_repo = history_repo
        self.settings_repo = settings_repo
        self.agent_service = agent_service

    def _now_str(self) -> str:
        return datetime.now().isoformat()

    def start_workflow(self) -> WorkflowState:
        """Step 1: Start a new workflow and generate a draft MRQ from Buyer."""
        workflow_id = f"WF-{uuid.uuid4().hex[:6].upper()}"
        settings = self.settings_repo.load_settings()
        catalog = self.products_repo.get_all()
        
        # 1. Instantiate the state
        state = WorkflowState(
            workflow_id=workflow_id,
            status="ACTIVE",
            current_step=1,
            documents=[],
            timeline=[
                TimelineEvent(
                    timestamp=self._now_str(),
                    event="Workflow Initialized",
                    description="Procurement workflow started. Initializing Material Request Quote.",
                    actor="Human"
                )
            ]
        )
        
        # 2. Call Buyer agent for Step 1
        agent_output = self.agent_service.call_buyer(settings, catalog, step=1)
        
        # 3. Create Draft Document
        doc_id = f"DOC-{uuid.uuid4().hex[:6].upper()}"
        items = agent_output.get("items", [])
        
        # Create concrete QuoteDocument structure
        quote_doc = QuoteDocument(
            workflow_id=workflow_id,
            quote_id=doc_id,
            created_at=self._now_str(),
            buyer="MegaMart Online",
            supplier="FreshFizz Consumer Products",
            items=[QuoteItem(**it) for it in items],
            status="PENDING",
            letter_text=agent_output.get("letter_text", "")
        )
        
        draft = WorkflowDocument(
            id=doc_id,
            type="MRQ",
            created_at=self._now_str(),
            created_by="Buyer",
            content=quote_doc.model_dump(),
            letter_text=agent_output.get("letter_text", "")
        )
        
        state.current_draft = draft
        state.timeline.append(
            TimelineEvent(
                timestamp=self._now_str(),
                event="Buyer Drafted MRQ",
                description="Buyer (Gemini) generated Material Request Quote draft. Pending human approval.",
                actor="Buyer"
            )
        )
        
        self.workflow_repo.save(state)
        return state

    def start_workflow_with_skus(self, skus: List[str]) -> WorkflowState:
        """Step 1: Start a new replenishment workflow pre-populated with low-stock SKUs."""
        workflow_id = f"WF-{uuid.uuid4().hex[:6].upper()}"
        settings = self.settings_repo.load_settings()
        catalog = self.products_repo.get_all()
        
        # 1. Instantiate the state
        state = WorkflowState(
            workflow_id=workflow_id,
            status="ACTIVE",
            current_step=1,
            documents=[],
            timeline=[
                TimelineEvent(
                    timestamp=self._now_str(),
                    event="Workflow Initialized",
                    description="Procurement workflow started. Initializing Material Request Quote.",
                    actor="Human"
                )
            ]
        )
        
        # Generate the items directly from the provided SKUs
        items = []
        for sku in skus:
            prod = next((p for p in catalog if p.sku == sku), None)
            if not prod:
                continue
            # Replenish quantity: base MOQ + 100 units to restore inventory
            qty = max(prod.moq, 200)
            items.append({
                "sku": sku,
                "requested_quantity": qty,
                "quoted_quantity": 0,
                "requested_price": prod.price,
                "quoted_price": 0.0,
                "discount": 0.0,
                "final_price": 0.0
            })
            
        if not items:
            # Fallback to standard start if no valid SKUs
            return self.start_workflow()
            
        # Build the dynamic letter text for these items
        items_list_str = "\n".join([f"- {it['sku']}: {it['requested_quantity']} units" for it in items])
        letter_text = (
            "Dear FreshFizz Commercial Sales Team,\n\n"
            "This is an automated auto-replenishment request. MegaMart Online's automated stock tracking system "
            "has flagged the following catalog lines as falling below our standard safety threshold levels. "
            "We would like to request an immediate Material Request Quote (MRQ) for:\n"
            f"{items_list_str}\n\n"
            "Please verify your current stock levels and issue a formal quote proposal. Let us know estimated dispatch lead times "
            "so we can prioritize receipt logistics.\n\n"
            "Sincerely,\n\n"
            "Automated Replenishment System\nMegaMart Online"
        )
        
        # 3. Create Draft Document
        doc_id = f"DOC-{uuid.uuid4().hex[:6].upper()}"
        
        # Create concrete QuoteDocument structure
        quote_doc = QuoteDocument(
            workflow_id=workflow_id,
            quote_id=doc_id,
            created_at=self._now_str(),
            buyer="MegaMart Online",
            supplier="FreshFizz Consumer Products",
            items=[QuoteItem(**it) for it in items],
            status="PENDING",
            letter_text=letter_text
        )
        
        draft = WorkflowDocument(
            id=doc_id,
            type="MRQ",
            created_at=self._now_str(),
            created_by="Buyer",
            content=quote_doc.model_dump(),
            letter_text=letter_text
        )
        
        state.current_draft = draft
        state.timeline.append(
            TimelineEvent(
                timestamp=self._now_str(),
                event="Buyer Drafted MRQ",
                description="Buyer (Automated Replenishment System) generated replenishment Material Request Quote draft. Pending human approval.",
                actor="Buyer"
            )
        )
        
        self.workflow_repo.save(state)
        return state

    def _sync_letter_text(self, letter_text: str, items: List[Dict[str, Any]]) -> str:
        """Helper to dynamically sync quantities and prices mentioned in the letter text with items list."""
        import re
        for it in items:
            sku = it.get("sku", "")
            qty = it.get("quoted_quantity") or it.get("requested_quantity") or 0
            price = it.get("final_price") or it.get("quoted_price") or it.get("requested_price") or 0.0
            
            # 1. Update quantity: look for SKU, then find the next number
            # We match SKU followed by any characters except newlines/numbers, then the number
            pattern_qty = rf"({sku}[^0-9\n]*)\b\d+\b"
            letter_text = re.sub(pattern_qty, lambda m: f"{m.group(1)}{qty}", letter_text, flags=re.IGNORECASE)
            
            # 2. Update price: look for SKU, then find the next '$' and its number
            pattern_price = rf"({sku}[^$\n]*\$\s*)\d+(\.\d+)?"
            letter_text = re.sub(pattern_price, lambda m: f"{m.group(1)}{price:.2f}", letter_text, flags=re.IGNORECASE)
            
        return letter_text

    def update_draft(self, workflow_id: str, letter_text: str, items_data: List[Dict[str, Any]]) -> WorkflowState:
        """Allows human to edit the current draft's letter text or item details before sending."""
        state = self.workflow_repo.get(workflow_id)
        if not state or not state.current_draft:
            raise ValueError("No active workflow or draft found")
            
        draft = state.current_draft
        
        # Sync the letter text with any edited items quantities/prices first
        synced_letter_text = self._sync_letter_text(letter_text, items_data)
        
        draft.letter_text = synced_letter_text
        draft.content["letter_text"] = synced_letter_text
        
        # Update items in content
        updated_items = []
        for it in items_data:
            updated_items.append(QuoteItem(**it).model_dump())
        draft.content["items"] = updated_items
        
        state.current_draft = draft
        state.timeline.append(
            TimelineEvent(
                timestamp=self._now_str(),
                event="Draft Modified",
                description="Human operator updated the draft contents.",
                actor="Human"
            )
        )
        self.workflow_repo.save(state)
        return state

    def send_document(self, workflow_id: str) -> WorkflowState:
        """Approves the current draft, adds it to the documents timeline, and invokes the next agent."""
        state = self.workflow_repo.get(workflow_id)
        if not state or not state.current_draft:
            raise ValueError("No active workflow or draft found")
            
        draft = state.current_draft
        state.current_draft = None
        
        # Update status of quote document inside content to SENT
        draft.content["status"] = "SENT"
        state.documents.append(draft)
        
        state.timeline.append(
            TimelineEvent(
                timestamp=self._now_str(),
                event=f"{draft.type} Approved & Sent",
                description=f"Human approved and sent {draft.type} to the recipient.",
                actor="Human"
            )
        )
        
        settings = self.settings_repo.load_settings()
        catalog = self.products_repo.get_all()
        
        # Transition to next step
        if state.current_step == 1:
            # Transition to Step 2: Supplier generates Fulfillment Proposal
            state.current_step = 2
            
            # Call Supplier agent
            agent_output = self.agent_service.call_supplier(
                settings, catalog, step=2, previous_data=draft.content
            )
            
            doc_id = f"DOC-{uuid.uuid4().hex[:6].upper()}"
            items = agent_output.get("items", [])
            
            quote_doc = QuoteDocument(
                workflow_id=workflow_id,
                quote_id=doc_id,
                created_at=self._now_str(),
                buyer="MegaMart Online",
                supplier="FreshFizz Consumer Products",
                items=[QuoteItem(**it) for it in items],
                status="PENDING",
                letter_text=agent_output.get("letter_text", "")
            )
            
            state.current_draft = WorkflowDocument(
                id=doc_id,
                type="Proposal",
                created_at=self._now_str(),
                created_by="Supplier",
                content=quote_doc.model_dump(),
                letter_text=agent_output.get("letter_text", "")
            )
            
            state.timeline.append(
                TimelineEvent(
                    timestamp=self._now_str(),
                    event="Supplier Proposed Fulfillment",
                    description="Supplier (Claude) generated Fulfillment Proposal draft. Pending human approval.",
                    actor="Supplier"
                )
            )
            
        elif state.current_step == 2:
            # Transition to Step 3: Buyer submits Counter Offer (negotiation)
            state.current_step = 3
            
            # Call Buyer agent
            agent_output = self.agent_service.call_buyer(
                settings, catalog, step=3, previous_data=draft.content
            )
            
            doc_id = f"DOC-{uuid.uuid4().hex[:6].upper()}"
            items = agent_output.get("items", [])
            
            quote_doc = QuoteDocument(
                workflow_id=workflow_id,
                quote_id=doc_id,
                created_at=self._now_str(),
                buyer="MegaMart Online",
                supplier="FreshFizz Consumer Products",
                items=[QuoteItem(**it) for it in items],
                status="PENDING",
                letter_text=agent_output.get("letter_text", "")
            )
            
            state.current_draft = WorkflowDocument(
                id=doc_id,
                type="CounterOffer",
                created_at=self._now_str(),
                created_by="Buyer",
                content=quote_doc.model_dump(),
                letter_text=agent_output.get("letter_text", "")
            )
            
            state.timeline.append(
                TimelineEvent(
                    timestamp=self._now_str(),
                    event="Buyer Proposed Counter-Offer",
                    description="Buyer (Gemini) generated Counter-Offer draft (discounts & qty modifications). Pending human approval.",
                    actor="Buyer"
                )
            )
            
        elif state.current_step == 3:
            # Transition to Step 4: Supplier accepts Counter Offer (Final letter)
            state.current_step = 4
            
            # Call Supplier agent
            agent_output = self.agent_service.call_supplier(
                settings, catalog, step=4, previous_data=draft.content
            )
            
            doc_id = f"DOC-{uuid.uuid4().hex[:6].upper()}"
            items = agent_output.get("items", [])
            
            quote_doc = QuoteDocument(
                workflow_id=workflow_id,
                quote_id=doc_id,
                created_at=self._now_str(),
                buyer="MegaMart Online",
                supplier="FreshFizz Consumer Products",
                items=[QuoteItem(**it) for it in items],
                status="PENDING",
                letter_text=agent_output.get("letter_text", "")
            )
            
            state.current_draft = WorkflowDocument(
                id=doc_id,
                type="FinalLetter",
                created_at=self._now_str(),
                created_by="Supplier",
                content=quote_doc.model_dump(),
                letter_text=agent_output.get("letter_text", "")
            )
            
            state.timeline.append(
                TimelineEvent(
                    timestamp=self._now_str(),
                    event="Supplier Drafted Final Letter",
                    description="Supplier (Claude) generated Final Acceptance Letter draft. Pending human approval.",
                    actor="Supplier"
                )
            )
            
        elif state.current_step == 4:
            # Transition to Step 5: Buyer drafts Final Acceptance Quote
            state.current_step = 5
            
            # Call Buyer Agent to draft acceptance letter
            agent_output = self.agent_service.call_buyer(
                settings, catalog, step=5, previous_data=draft.content
            )
            
            doc_id = f"DOC-{uuid.uuid4().hex[:6].upper()}"
            items = agent_output.get("items", [])
            
            quote_doc = QuoteDocument(
                workflow_id=workflow_id,
                quote_id=doc_id,
                created_at=self._now_str(),
                buyer="MegaMart Online",
                supplier="FreshFizz Consumer Products",
                items=[QuoteItem(**it) for it in items],
                status="PENDING",
                letter_text=agent_output.get("letter_text", "")
            )
            
            state.current_draft = WorkflowDocument(
                id=doc_id,
                type="FinalQuote",
                created_at=self._now_str(),
                created_by="Buyer",
                content=quote_doc.model_dump(),
                letter_text=agent_output.get("letter_text", "")
            )
            
            state.timeline.append(
                TimelineEvent(
                    timestamp=self._now_str(),
                    event="Buyer Drafted Final Acceptance",
                    description="Buyer (Gemini) drafted the final acceptance terms. Pending human review and approval.",
                    actor="Buyer"
                )
            )
            
        elif state.current_step == 5:
            # Transition to Step 6: Finalize. Auto-generate Purchase Order, Invoice, and Delivery Order
            state.current_step = 6
            state.status = "COMPLETED"
            
            # Filter items to only include accepted SKU items for final contract docs
            all_draft_items = draft.content.get("items", [])
            final_items = [it for it in all_draft_items if it.get("accepted", True)]
            
            # 1. Generate Purchase Order (PO)
            po_id = f"PO-{uuid.uuid4().hex[:6].upper()}"
            po_text = (
                f"PURCHASE ORDER\n\n"
                f"Order Reference: {po_id}\n"
                f"Workflow Reference: {workflow_id}\n"
                f"Date: {datetime.now().strftime('%Y-%m-%d')}\n"
                f"Buyer: MegaMart Online\n"
                f"Supplier: FreshFizz Consumer Products\n\n"
                f"Items:\n"
            )
            total_value = 0.0
            for idx, item in enumerate(final_items, 1):
                sku = item["sku"]
                qty = item["quoted_quantity"]
                price = item["final_price"]
                item_total = round(qty * price, 2)
                total_value += item_total
                po_text += f"{idx}. SKU: {sku} - Qty: {qty} @ ${price:.2f}/unit (Subtotal: ${item_total:.2f})\n"
                
            po_text += f"\nTotal PO Value: ${total_value:.2f}\n\n"
            po_text += "Payment Terms: Net 30 days.\nShipping Terms: FOB Origin."
            
            po_doc = WorkflowDocument(
                id=po_id,
                type="PO",
                created_at=self._now_str(),
                created_by="Buyer",
                content={"po_id": po_id, "items": final_items, "total_value": total_value},
                letter_text=po_text
            )
            state.documents.append(po_doc)
            
            # 2. Generate Commercial Invoice
            inv_id = f"INV-{uuid.uuid4().hex[:6].upper()}"
            inv_text = (
                f"COMMERCIAL INVOICE\n\n"
                f"Invoice Reference: {inv_id}\n"
                f"Purchase Order Reference: {po_id}\n"
                f"Date: {datetime.now().strftime('%Y-%m-%d')}\n"
                f"Remit To: FreshFizz Consumer Products\n"
                f"Bill To: MegaMart Online\n\n"
                f"Items Invoiced:\n"
            )
            for idx, item in enumerate(final_items, 1):
                sku = item["sku"]
                qty = item["quoted_quantity"]
                price = item["final_price"]
                item_total = round(qty * price, 2)
                inv_text += f"{idx}. SKU: {sku} - Qty: {qty} @ ${price:.2f}/unit (Subtotal: ${item_total:.2f})\n"
                
            inv_text += f"\nTotal Amount Due: ${total_value:.2f}\n\n"
            inv_text += "Please remit payment via ACH transfer within 30 days."
            
            inv_doc = WorkflowDocument(
                id=inv_id,
                type="Invoice",
                created_at=self._now_str(),
                created_by="Supplier",
                content={"invoice_id": inv_id, "total_value": total_value},
                letter_text=inv_text
            )
            state.documents.append(inv_doc)
            
            # 3. Generate Delivery Order (DO)
            do_id = f"DO-{uuid.uuid4().hex[:6].upper()}"
            do_text = (
                f"DELIVERY ORDER / PACKING SLIP\n\n"
                f"Delivery Reference: {do_id}\n"
                f"Associated PO: {po_id}\n"
                f"Carrier: Standard CPG Carrier\n"
                f"Ship To: MegaMart Fulfillment Center\n"
                f"Ship From: FreshFizz Distribution Hub\n\n"
                f"Items Scheduled for Dispatch:\n"
            )
            for idx, item in enumerate(final_items, 1):
                sku = item["sku"]
                qty = item["quoted_quantity"]
                # Look up lead time from catalog
                prod = self.products_repo.get_by_sku(sku)
                lt = prod.lead_time if prod else 3
                do_text += f"{idx}. SKU: {sku} - Dispatch Qty: {qty} units (Estimated Lead Time: {lt} days)\n"
                
            do_text += "\nGoods received in good condition signature required."
            
            do_doc = WorkflowDocument(
                id=do_id,
                type="DO",
                created_at=self._now_str(),
                created_by="Supplier",
                content={"delivery_id": do_id},
                letter_text=do_text
            )
            state.documents.append(do_doc)
            
            # Update Inventory (only for accepted quantities)
            for item in final_items:
                sku = item["sku"]
                qty_purchased = item["quoted_quantity"]
                prod = self.products_repo.get_by_sku(sku)
                if prod:
                    self.products_repo.update_inventory(sku, prod.inventory - qty_purchased)
            
            # Generate Friendly Narrative Report using Gemini
            settings = self.settings_repo.load_settings()
            friendly_report = self.agent_service.generate_negotiation_summary(
                settings, state.timeline, state.documents
            )
            
            history_summary = HistorySummary(
                workflow_id=workflow_id,
                start_time=state.timeline[0].timestamp,
                end_time=self._now_str(),
                documents=[d.model_dump() for d in state.documents],
                summary=friendly_report
            )
            self.history_repo.add(history_summary)
            
            state.timeline.append(
                TimelineEvent(
                    timestamp=self._now_str(),
                    event="Workflow Completed",
                    description="Final PO, Commercial Invoice, and Delivery Orders generated. Inventory levels decremented.",
                    actor="Human"
                )
            )

        self.workflow_repo.save(state)
        return state

    def reject_workflow(self, workflow_id: str) -> WorkflowState:
        """Cancels/Rejects the active negotiation process."""
        state = self.workflow_repo.get(workflow_id)
        if not state:
            raise ValueError("No active workflow found")
            
        state.status = "REJECTED"
        state.current_draft = None
        state.timeline.append(
            TimelineEvent(
                timestamp=self._now_str(),
                event="Workflow Terminated",
                description="Human operator rejected the draft and terminated the workflow.",
                actor="Human"
            )
        )
        self.workflow_repo.save(state)
        return state
