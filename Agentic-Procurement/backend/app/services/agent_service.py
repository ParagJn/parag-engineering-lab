import re
import json
import logging
from typing import Dict, Any, List
import google.generativeai as genai
from anthropic import Anthropic

from app.models.settings import Settings
from app.models.product import Product
from app.core.prompts import BUYER_SYSTEM_PROMPT, SUPPLIER_SYSTEM_PROMPT
from typing import Optional

logger = logging.getLogger(__name__)

class AgentService:
    def __init__(self):
        pass

    def _extract_json(self, text: str) -> Dict[str, Any]:
        """Extracts and parses the first JSON object found in a text block."""
        # Find first '{' and last '}'
        match = re.search(r'(\{.*\})', text, re.DOTALL)
        if not match:
            # Fallback: try parsing directly
            try:
                return json.loads(text.strip())
            except Exception:
                raise ValueError("Could not extract valid JSON from LLM response")
        
        json_str = match.group(1)
        try:
            return json.loads(json_str)
        except json.JSONDecodeError as e:
            # Try cleaning up common issues: trailing commas, newlines in strings
            # Let's try parsing one more time with a simple fix or raise
            raise ValueError(f"JSON parsing error: {str(e)} in extracted block: {json_str}")

    def call_buyer(self, settings: Settings, catalog: List[Product], step: int, previous_data: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """Calls Gemini for Buyer Agent (MegaMart Online). Falls back to mock if key is missing."""
        if not settings.gemini_key:
            logger.info("Gemini API Key missing. Using Mock Buyer.")
            return self._mock_buyer(catalog, step, previous_data)
        
        try:
            genai.configure(api_key=settings.gemini_key)
            model_name = settings.buyer_model or "gemini-1.5-flash"
            model = genai.GenerativeModel(
                model_name=model_name,
                system_instruction=BUYER_SYSTEM_PROMPT
            )
            
            # Formulate the user prompt
            catalog_str = json.dumps([p.model_dump() for p in catalog], indent=2)
            prompt = f"Step: {step}\n"
            prompt += f"Catalog:\n{catalog_str}\n\n"
            
            if previous_data:
                prompt += f"Previous Document Data:\n{json.dumps(previous_data, indent=2)}\n\n"
            
            prompt += "Generate your response now. Remember to output ONLY the JSON object conforming to the schema specified in the system instructions."
            
            response = model.generate_content(
                prompt,
                generation_config=genai.types.GenerationConfig(
                    response_mime_type="application/json"
                )
            )
            return self._extract_json(response.text)
        except Exception as e:
            logger.error(f"Error calling Gemini: {str(e)}. Falling back to Mock.")
            return self._mock_buyer(catalog, step, previous_data)

    def call_supplier(self, settings: Settings, catalog: List[Product], step: int, previous_data: Dict[str, Any]) -> Dict[str, Any]:
        """Calls Claude for Supplier Agent (FreshFizz). Falls back to mock if key is missing."""
        from app.core.prompts import SUPPLIER_SYSTEM_PROMPT
        if not settings.claude_key:
            logger.info("Claude API Key missing. Using Mock Supplier.")
            return self._mock_supplier(catalog, step, previous_data)
            
        try:
            client = Anthropic(api_key=settings.claude_key)
            model_name = settings.supplier_model or "claude-3-5-sonnet-20240620"
            
            catalog_str = json.dumps([p.model_dump() for p in catalog], indent=2)
            prompt = f"Step: {step}\n"
            prompt += f"Catalog:\n{catalog_str}\n\n"
            prompt += f"Previous Document Data:\n{json.dumps(previous_data, indent=2)}\n\n"
            prompt += "Generate your response now. Return ONLY a valid JSON block."

            message = client.messages.create(
                model=model_name,
                max_tokens=2048,
                system=SUPPLIER_SYSTEM_PROMPT,
                messages=[{"role": "user", "content": prompt}]
            )
            response_text = message.content[0].text
            return self._extract_json(response_text)
        except Exception as e:
            logger.error(f"Error calling Claude: {str(e)}. Falling back to Mock.")
            return self._mock_supplier(catalog, step, previous_data)

    def _mock_buyer(self, catalog: List[Product], step: int, previous_data: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """Simulates Buyer agent behavior programmatically."""
        if step == 1:
            # Select first 4 items in catalog
            items = []
            selected_skus = ["SODA-001", "CHIP-001", "COOK-001", "JUIC-001"]
            for sku in selected_skus:
                prod = next((p for p in catalog if p.sku == sku), catalog[0])
                qty = max(prod.moq, 150)
                items.append({
                    "sku": sku,
                    "requested_quantity": qty,
                    "quoted_quantity": 0,
                    "requested_price": prod.price,
                    "quoted_price": 0.0,
                    "discount": 0.0,
                    "final_price": 0.0
                })
            
            letter_text = (
                "Dear FreshFizz Commercial Sales Team,\n\n"
                "I hope this letter finds you well. MegaMart Online is looking to restock our CPG product selection "
                "for the upcoming summer season. Based on our market analytics and current inventory levels, we would "
                "like to request a fulfillment proposal and price quote for the following products:\n"
                "- FizzCola Classic (SODA-001): 200 units\n"
                "- CrunchySalt Potato Chips (CHIP-001): 150 units\n"
                "- ChocoDelight Cookies (COOK-001): 100 units\n"
                "- PureOrange Juice (JUIC-001): 80 units\n\n"
                "Please review your stock levels and let us know your standard lead times, minimum order requirements, "
                "and any bulk purchase terms that might apply to this order. We look forward to establishing a mutually "
                "beneficial supply relationship.\n\n"
                "Best regards,\n\n"
                "Procurement Director\nMegaMart Online"
            )
            return {"letter_text": letter_text, "items": items}
            
        elif step == 3:
            # Negotiate: Apply 3-5% discount, reduce COOK-001 quantity
            items = []
            orig_items = previous_data.get("items", []) if previous_data else []
            negotiated_skus = ["SODA-001", "CHIP-001"]
            
            for item in orig_items:
                item_copy = item.copy()
                sku = item_copy["sku"]
                
                # Apply 4% discount to SODA-001 and CHIP-001
                if sku in negotiated_skus:
                    item_copy["discount"] = 0.04
                    item_copy["final_price"] = round(item_copy["quoted_price"] * 0.96, 2)
                else:
                    item_copy["discount"] = 0.0
                    item_copy["final_price"] = item_copy["quoted_price"]
                
                # Reduce quantity for COOK-001 to 80
                if sku == "COOK-001":
                    item_copy["requested_quantity"] = 80
                    item_copy["quoted_quantity"] = 80
                
                items.append(item_copy)
                
            letter_text = (
                "Dear FreshFizz Commercial Sales Team,\n\n"
                "Thank you for providing the initial fulfillment proposal and confirming inventory availability. "
                "We are pleased to see that you can fulfill our requested quantities for most items.\n\n"
                "Upon reviewing the quoted prices, our finance team has requested that we seek a discount on our "
                "highest-volume lines to align with our seasonal budget caps. Specifically, we are proposing a 4% discount "
                "on FizzCola Classic (SODA-001) and CrunchySalt Potato Chips (CHIP-001). Additionally, we have adjusted the "
                "requested quantity for ChocoDelight Cookies (COOK-001) down to 80 units to better balance our stock levels.\n\n"
                "We believe this counter-offer is fair and aligns with standard volume discount agreements in the industry. "
                "If these terms are acceptable, we are prepared to issue a formal Purchase Order immediately.\n\n"
                "Sincerely,\n\n"
                "Procurement Director\nMegaMart Online"
            )
            return {"letter_text": letter_text, "items": items}
            
        elif step == 5:
            # Final quote acceptance: clone items
            items = []
            orig_items = previous_data.get("items", []) if previous_data else []
            for item in orig_items:
                items.append(item.copy())
                
            letter_text = (
                "Dear FreshFizz Commercial Sales Team,\n\n"
                "We have received your final pricing counter-proposal (Ref: FinalLetter). "
                "We accept FizzCola Classic (SODA-001) at the negotiated 4% discounted unit price of $1.44. "
                "We also accept your pricing of $2.20 for CrunchySalt Potato Chips (CHIP-001) without the discount.\n\n"
                "Based on these terms, we are sending this final quote approval. "
                "Please proceed with generating the official Purchase Order, Commercial Invoice, and Delivery Orders for our logistics teams."
                "\n\n"
                "Sincerely,\n\n"
                "Procurement Director\nMegaMart Online"
            )
            return {"letter_text": letter_text, "items": items}
            
        return {}

    def _mock_supplier(self, catalog: List[Product], step: int, previous_data: Dict[str, Any]) -> Dict[str, Any]:
        """Simulates Supplier agent behavior programmatically."""
        if step == 2:
            # Check inventory and fulfill
            items = []
            orig_items = previous_data.get("items", [])
            for item in orig_items:
                sku = item["sku"]
                prod = next((p for p in catalog if p.sku == sku), None)
                qty = item["requested_quantity"]
                
                inv_available = prod.inventory if prod else 500
                quoted_qty = min(qty, inv_available)
                price = prod.price if prod else 2.0
                
                items.append({
                    "sku": sku,
                    "requested_quantity": qty,
                    "quoted_quantity": quoted_qty,
                    "requested_price": item.get("requested_price", price),
                    "quoted_price": price,
                    "discount": 0.0,
                    "final_price": price
                })
                
            letter_text = (
                "Dear MegaMart Online Procurement Team,\n\n"
                "Thank you for your Material Request Quote. We appreciate the opportunity to partner with "
                "MegaMart Online for your seasonal retail inventory replenishment.\n\n"
                "We have verified our stock levels at our FreshFizz main distribution center. I am pleased to confirm "
                "that we have full inventory availability for all requested items and can fulfill 100% of your requested quantities:\n"
                "- FizzCola Classic (SODA-001): 200 units @ $1.50/unit\n"
                "- CrunchySalt Potato Chips (CHIP-001): 150 units @ $2.20/unit\n"
                "- ChocoDelight Cookies (COOK-001): 100 units @ $3.50/unit\n"
                "- PureOrange Juice (JUIC-001): 80 units @ $4.20/unit\n\n"
                "Our estimated lead time for packing and shipping is 3 business days from receiving your official "
                "Purchase Order. Please let us know if this proposal meets your timeline, so we can lock in the shipment slots.\n\n"
                "Sincerely yours,\n\n"
                "Commercial Sales Director\nFreshFizz Consumer Products"
            )
            return {"letter_text": letter_text, "items": items}
            
        elif step == 4:
            # Decline discount for CHIP-001, accept for others
            items = []
            orig_items = previous_data.get("items", [])
            for item in orig_items:
                item_copy = item.copy()
                if item_copy["sku"] == "CHIP-001":
                    # Reject discount: set back to quoted price
                    item_copy["discount"] = 0.0
                    item_copy["final_price"] = item_copy["quoted_price"]
                items.append(item_copy)
                
            letter_text = (
                "Dear MegaMart Online Procurement Team,\n\n"
                "Thank you for your feedback and counter-proposal. We appreciate your transparency regarding your seasonal "
                "budget constraints. \n\n"
                "After reviewing the proposal with our commercial pricing committee, we have approved the proposed 4% discount "
                "on FizzCola Classic (SODA-001), lowering its unit price to $1.44. However, due to tight margins and rising supply "
                "costs for raw potatoes, we are UNABLE to approve the discount on CrunchySalt Potato Chips (CHIP-001). Its unit "
                "price must remain at the original quoted rate of $2.20.\n\n"
                "We accept the quantity adjustment for ChocoDelight Cookies (COOK-001) down to 80 units. "
                "Please review these final pricing terms. If you accept this final proposal, you may proceed with submitting your PO."
                "\n\n"
                "With best regards,\n\n"
                "Commercial Sales Director\nFreshFizz Consumer Products"
            )
            return {"letter_text": letter_text, "items": items}
            
        return {}

    def generate_negotiation_summary(self, settings: Settings, timeline: List[Any], documents: List[Any]) -> str:
        """Calls Gemini to generate a friendly high-level report/summary of the negotiation in markdown."""
        if not settings.gemini_key:
            logger.info("Gemini API Key missing. Using Mock Summary generator.")
            return self._mock_summary_report(timeline, documents)
            
        try:
            genai.configure(api_key=settings.gemini_key)
            model_name = settings.buyer_model or "gemini-1.5-flash"
            model = genai.GenerativeModel(model_name=model_name)
            
            # Prepare context
            timeline_str = json.dumps([e if isinstance(e, dict) else e.model_dump() for e in timeline], indent=2)
            docs_summary = []
            for doc in documents:
                d_dict = doc if isinstance(doc, dict) else doc.model_dump()
                docs_summary.append({
                    "id": d_dict["id"],
                    "type": d_dict["type"],
                    "created_by": d_dict["created_by"],
                    "items": d_dict.get("content", {}).get("items", [])
                })
            docs_str = json.dumps(docs_summary, indent=2)
            
            prompt = (
                "You are an expert AI Procurement Consultant.\n"
                "Please review the following timeline of events and documents exchanged during a business negotiation:\n\n"
                f"Timeline:\n{timeline_str}\n\n"
                f"Documents summary:\n{docs_str}\n\n"
                "Generate a friendly, highly readable, and professional 'High Level Negotiation Report' in Markdown format.\n"
                "The report should contain:\n"
                "1. A clean, styled header with the Workflow Reference.\n"
                "2. An executive summary section detailing who negotiated with whom and what the final outcome was.\n"
                "3. A breakdown of the SKU-level pricing decisions (showing initial quotes, discounts requested, supplier counter-decisions, and whether the buyer accepted or declined specific SKUs).\n"
                "4. A clear highlight of the total final cost and the total discount savings achieved.\n"
                "5. Next steps or shipping details (estimated dispatch timeline).\n\n"
                "Use bullet points, bold highlights, and markdown tables to make it look visually stunning. Keep the tone friendly yet professional."
            )
            
            response = model.generate_content(prompt)
            return response.text
        except Exception as e:
            logger.error(f"Error calling Gemini for summary: {str(e)}")
            return self._mock_summary_report(timeline, documents)

    def _mock_summary_report(self, timeline: List[Any], documents: List[Any]) -> str:
        """Generates a beautiful mock report in markdown format as fallback."""
        # Find PO document to get final items
        po_doc = None
        for d in documents:
            d_dict = d if isinstance(d, dict) else d.model_dump()
            if d_dict["type"] == "PO":
                po_doc = d_dict
                break
                
        items_list = []
        total_value = 0.0
        savings = 0.0
        
        if po_doc:
            items_list = po_doc.get("content", {}).get("items", [])
            total_value = po_doc.get("content", {}).get("total_value", 0.0)
            
            for it in items_list:
                qty = it.get("quoted_quantity", 0)
                q_price = it.get("quoted_price", 0.0)
                f_price = it.get("final_price", 0.0)
                savings += qty * (q_price - f_price)
        else:
            # Fallback values
            total_value = 540.20
            savings = 12.00
            
        report = (
            f"# 📊 High-Level Negotiation Report\n\n"
            f"**Ref**: MegaMart-FreshFizz Procurement Sync\n\n"
            f"## 1. Executive Summary\n"
            f"This negotiation session represents a replenishment cycle between **MegaMart Online** (Buyer) and **FreshFizz Consumer Products** (Supplier). "
            f"Through cooperative agent-driven negotiation, the parties reached agreement on restocking key CPG lines. The human operator "
            f"guided approvals at each outbound communication step, ensuring complete policy compliance.\n\n"
            f"## 2. SKU-Level Negotiation Breakdown\n"
            f"During Step 3, MegaMart requested a **4% discount** on volume products. FreshFizz accepted the terms on **SODA-001** "
            f"but declined the discount on **CHIP-001** due to local ingredient costs. \n\n"
            f"Here is how each SKU was resolved:\n\n"
            f"| SKU | Status | Final Quantity | Unit Price | Notes |\n"
            f"| :--- | :--- | :--- | :--- | :--- |\n"
        )
        
        for it in items_list:
            sku = it.get("sku", "")
            qty = it.get("quoted_quantity", 0)
            f_price = it.get("final_price", 0.0)
            discount = it.get("discount", 0.0)
            accepted = it.get("accepted", True)
            
            status_text = "✅ ACCEPTED" if accepted else "❌ DECLINED"
            disc_text = f"{(discount*100):.0f}% off" if discount > 0 else "Full Price"
            if not accepted:
                disc_text = "Deactivated SKU"
            
            report += f"| **{sku}** | {status_text} | {qty} units | ${f_price:.2f} | {disc_text} |\n"
            
        report += (
            f"\n"
            f"## 3. Financial Summary\n"
            f"* **Total Contract Value**: `${total_value:,.2f}`\n"
            f"* **Negotiated Savings**: `${savings:,.2f}`\n"
            f"* **Net Payment Terms**: Net 30 days\n\n"
            f"## 4. Shipping & Lead Times\n"
            f"Estimated dispatch is **3 business days** from Purchase Order validation. Cargo will ship via Freight Carrier from the "
            f"FreshFizz main distribution hub to the MegaMart fulfillment center."
        )
        return report
