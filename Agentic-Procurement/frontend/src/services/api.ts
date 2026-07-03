const API_BASE = "http://localhost:8000";

export interface Product {
  sku: string;
  name: string;
  category: string;
  price: number;
  inventory: number;
  lead_time: number;
  moq: number;
  description: string;
}

export interface Settings {
  gemini_key: string;
  claude_key: string;
  buyer_model: string;
  supplier_model: string;
}

export interface TimelineEvent {
  timestamp: string;
  event: string;
  description: string;
  actor: "Buyer" | "Supplier" | "Human";
}

export interface QuoteItem {
  sku: string;
  requested_quantity: number;
  quoted_quantity: number;
  requested_price: number;
  quoted_price: number;
  discount: number;
  final_price: number;
  accepted: boolean;
}

export interface WorkflowDocument {
  id: string;
  type: "MRQ" | "Proposal" | "CounterOffer" | "FinalLetter" | "FinalQuote" | "PO" | "Invoice" | "DO";
  created_at: string;
  created_by: "Buyer" | "Supplier" | "Human";
  content: any;
  letter_text: string;
}

export interface WorkflowState {
  workflow_id: string;
  status: "ACTIVE" | "COMPLETED" | "REJECTED";
  current_step: number;
  documents: WorkflowDocument[];
  timeline: TimelineEvent[];
  current_draft?: WorkflowDocument;
}

export interface HistorySummary {
  workflow_id: string;
  start_time: string;
  end_time: string;
  documents: any[];
  summary: string;
}

export const api = {
  async getProducts(): Promise<Product[]> {
    const res = await fetch(`${API_BASE}/products`);
    if (!res.ok) throw new Error("Failed to fetch products");
    return res.json();
  },

  async getSettings(): Promise<Settings> {
    const res = await fetch(`${API_BASE}/settings`);
    if (!res.ok) throw new Error("Failed to fetch settings");
    return res.json();
  },

  async saveSettings(settings: Settings): Promise<Settings> {
    const res = await fetch(`${API_BASE}/settings`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(settings),
    });
    if (!res.ok) throw new Error("Failed to save settings");
    return res.json();
  },

  async getHistory(): Promise<HistorySummary[]> {
    const res = await fetch(`${API_BASE}/history`);
    if (!res.ok) throw new Error("Failed to fetch history");
    return res.json();
  },

  async getActiveWorkflows(): Promise<WorkflowState[]> {
    const res = await fetch(`${API_BASE}/workflow/active`);
    if (!res.ok) throw new Error("Failed to fetch active workflows");
    return res.json();
  },

  async getWorkflow(workflowId: string): Promise<WorkflowState> {
    const res = await fetch(`${API_BASE}/workflow/${workflowId}`);
    if (!res.ok) throw new Error("Failed to fetch workflow state");
    return res.json();
  },

  async startWorkflow(): Promise<WorkflowState> {
    const res = await fetch(`${API_BASE}/workflow/start`, { method: "POST" });
    if (!res.ok) throw new Error("Failed to start workflow");
    return res.json();
  },

  async editDraft(workflowId: string, letterText: string, items: any[]): Promise<WorkflowState> {
    const res = await fetch(`${API_BASE}/workflow/${workflowId}/edit`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ letter_text: letterText, items }),
    });
    if (!res.ok) throw new Error("Failed to update draft");
    return res.json();
  },

  async sendDocument(workflowId: string): Promise<WorkflowState> {
    const res = await fetch(`${API_BASE}/workflow/${workflowId}/send`, { method: "POST" });
    if (!res.ok) throw new Error("Failed to approve and send document");
    return res.json();
  },

  async rejectWorkflow(workflowId: string): Promise<WorkflowState> {
    const res = await fetch(`${API_BASE}/workflow/${workflowId}/reject`, { method: "POST" });
    if (!res.ok) throw new Error("Failed to reject workflow");
    return res.json();
  },

  async rebuildCatalog(): Promise<void> {
    const res = await fetch(`${API_BASE}/admin/rebuild`, { method: "POST" });
    if (!res.ok) throw new Error("Failed to rebuild catalog");
  },

  async resetDatabase(): Promise<void> {
    const res = await fetch(`${API_BASE}/admin/reset`, { method: "POST" });
    if (!res.ok) throw new Error("Failed to reset database");
  },

  async getWorkflowReport(workflowId: string): Promise<{ workflow_id: string; report: string }> {
    const res = await fetch(`${API_BASE}/workflow/${workflowId}/report`);
    if (!res.ok) throw new Error("Failed to fetch workflow report");
    return res.json();
  },

  async chatAboutWorkflow(workflowId: string, userMessage: string, chatHistory: any[]): Promise<{ reply: string }> {
    const res = await fetch(`${API_BASE}/workflow/${workflowId}/chat`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ user_message: userMessage, chat_history: chatHistory }),
    });
    if (!res.ok) throw new Error("Failed to chat about workflow");
    return res.json();
  },

  async startReplenishmentWorkflow(skus: string[]): Promise<WorkflowState> {
    const res = await fetch(`${API_BASE}/workflow/start-replenishment`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ skus }),
    });
    if (!res.ok) throw new Error("Failed to start replenishment workflow");
    return res.json();
  }
};
