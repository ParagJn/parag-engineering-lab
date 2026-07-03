import React, { useEffect, useState, useRef } from "react";
import { api, type WorkflowState, type WorkflowDocument, type QuoteItem } from "../services/api";
import { 
  Play, Send, Edit3, XCircle, CheckCircle, AlertCircle, 
  Terminal, Building2, UserCheck, Loader2, FileText, ShoppingCart, Receipt, Truck 
} from "lucide-react";

interface WorkflowSimulatorProps {
  initialWorkflow?: WorkflowState | null;
  clearInitialWorkflow?: () => void;
}

export const WorkflowSimulator: React.FC<WorkflowSimulatorProps> = ({ initialWorkflow, clearInitialWorkflow }) => {
  const [activeWorkflow, setActiveWorkflow] = useState<WorkflowState | null>(null);
  const [loading, setLoading] = useState(false);
  const [agentGenerating, setAgentGenerating] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [isEditing, setIsEditing] = useState(false);

  // Edit fields
  const [editLetter, setEditLetter] = useState("");
  const [editItems, setEditItems] = useState<any[]>([]);

  const logEndRef = useRef<HTMLDivElement>(null);

  // Load any existing active workflow on mount
  useEffect(() => {
    if (initialWorkflow) {
      setActiveWorkflow(initialWorkflow);
      if (clearInitialWorkflow) clearInitialWorkflow();
      return;
    }
    const fetchActive = async () => {
      try {
        const activeList = await api.getActiveWorkflows();
        if (activeList.length > 0) {
          // Get details of the first active workflow
          const details = await api.getWorkflow(activeList[0].workflow_id);
          setActiveWorkflow(details);
        }
      } catch (err: any) {
        console.error("Failed to load active workflows:", err);
      }
    };
    fetchActive();
  }, [initialWorkflow]);

  // Scroll activity log to bottom
  useEffect(() => {
    if (logEndRef.current) {
      logEndRef.current.scrollIntoView({ behavior: "smooth" });
    }
  }, [activeWorkflow?.timeline, agentGenerating]);

  const handleStart = async () => {
    setLoading(true);
    setAgentGenerating(true);
    setError(null);
    try {
      const state = await api.startWorkflow();
      setActiveWorkflow(state);
    } catch (err: any) {
      setError(err.message || "Failed to start simulation run.");
    } finally {
      setLoading(false);
      setAgentGenerating(false);
    }
  };

  const handleEditToggle = () => {
    if (!activeWorkflow?.current_draft) return;
    setEditLetter(activeWorkflow.current_draft.letter_text || "");
    // Deep copy items
    setEditItems(JSON.parse(JSON.stringify(activeWorkflow.current_draft.content.items || [])));
    setIsEditing(true);
  };

  const handleEditSave = async () => {
    if (!activeWorkflow) return;
    setLoading(true);
    setError(null);
    try {
      const updatedState = await api.editDraft(
        activeWorkflow.workflow_id,
        editLetter,
        editItems
      );
      setActiveWorkflow(updatedState);
      setIsEditing(false);
    } catch (err: any) {
      setError(err.message || "Failed to save edits.");
    } finally {
      setLoading(false);
    }
  };

  const handleSend = async () => {
    if (!activeWorkflow) return;
    setLoading(true);
    setAgentGenerating(true);
    setError(null);
    setIsEditing(false);
    try {
      const nextState = await api.sendDocument(activeWorkflow.workflow_id);
      setActiveWorkflow(nextState);
    } catch (err: any) {
      setError(err.message || "Failed to approve and send document.");
    } finally {
      setLoading(false);
      setAgentGenerating(false);
    }
  };

  const handleReject = async () => {
    if (!activeWorkflow) return;
    if (!window.confirm("Are you sure you want to reject this draft and terminate the workflow?")) return;
    setLoading(true);
    setError(null);
    setIsEditing(false);
    try {
      const canceledState = await api.rejectWorkflow(activeWorkflow.workflow_id);
      setActiveWorkflow(canceledState);
    } catch (err: any) {
      setError(err.message || "Failed to reject workflow.");
    } finally {
      setLoading(false);
    }
  };

  const handleReset = () => {
    setActiveWorkflow(null);
    setIsEditing(false);
  };

  const toggleItemAccept = async (sku: string) => {
    if (!activeWorkflow || !activeWorkflow.current_draft) return;
    const draft = activeWorkflow.current_draft;
    const updatedItems = (draft.content.items || []).map((it: any) => {
      if (it.sku === sku) {
        return {
          ...it,
          accepted: it.accepted === false ? true : false
        };
      }
      return it;
    });
    
    setLoading(true);
    try {
      const nextState = await api.editDraft(
        activeWorkflow.workflow_id,
        draft.letter_text,
        updatedItems
      );
      setActiveWorkflow(nextState);
    } catch (err: any) {
      setError(err.message || "Failed to toggle SKU approval.");
    } finally {
      setLoading(false);
    }
  };

  const updateItemQty = (index: number, qty: number) => {
    const copy = [...editItems];
    copy[index].requested_quantity = qty;
    copy[index].quoted_quantity = qty; // sync in draft for edit
    setEditItems(copy);
  };

  const updateItemPrice = (index: number, price: number) => {
    const copy = [...editItems];
    copy[index].requested_price = price;
    copy[index].quoted_price = price;
    copy[index].final_price = price;
    setEditItems(copy);
  };

  const getStepStatus = (stepNum: number) => {
    if (!activeWorkflow) return "inactive";
    if (activeWorkflow.status === "COMPLETED") return "completed";
    if (activeWorkflow.status === "REJECTED") return "failed";
    if (activeWorkflow.current_step > stepNum) return "completed";
    if (activeWorkflow.current_step === stepNum) return "active";
    return "inactive";
  };

  const renderTimeline = () => {
    const steps = [
      { num: 1, name: "Material Request Quote", desc: "Buyer drafts product requisition" },
      { num: 2, name: "Fulfillment Proposal", desc: "Supplier reviews stock & quotes pricing" },
      { num: 3, name: "Buyer Negotiation", desc: "Buyer counter-offers discounts (3-5%)" },
      { num: 4, name: "Supplier Counter-Proposal", desc: "Supplier accepts/rejects discounts at SKU level" },
      { num: 5, name: "Buyer Final Acceptance", desc: "Buyer reviews counter and confirms active SKUs" },
      { num: 6, name: "PO & Invoicing", desc: "Finalize contracts, PO, invoice, & delivery" }
    ];

    return (
      <div className="flex flex-col space-y-6">
        <h3 className="text-sm font-bold text-slate-400 uppercase tracking-wider mb-2">Workflow Timeline</h3>
        <div className="relative pl-6 border-l-2 border-slate-200 space-y-8">
          {steps.map((s) => {
            const status = getStepStatus(s.num);
            let badgeBg = "bg-slate-100 text-slate-400 border-slate-200";
            let dotBg = "bg-slate-300";
            
            if (status === "completed") {
              badgeBg = "bg-green-50 text-green-700 border-green-200";
              dotBg = "bg-green-600";
            } else if (status === "active") {
              badgeBg = "bg-blue-50 text-blue-700 border-blue-200 ring-2 ring-blue-100 pulse-indicator";
              dotBg = "bg-blue-600";
            } else if (status === "failed") {
              badgeBg = "bg-red-50 text-red-700 border-red-200";
              dotBg = "bg-red-600";
            }

            return (
              <div key={s.num} className="relative">
                {/* Timeline Dot */}
                <span className={`absolute -left-[31px] top-1.5 rounded-full h-4 w-4 border-2 border-white ${dotBg} transition-colors duration-300`} />
                <div className={`p-3.5 border rounded-xl bg-white shadow-sm transition-all duration-300 ${status === "active" ? "ring-2 ring-blue-500 ring-offset-2 scale-102 border-blue-200" : "border-slate-200"}`}>
                  <div className="flex items-center justify-between">
                    <span className="text-xs font-bold text-slate-400">Step {s.num}</span>
                    <span className={`text-xxs font-bold px-2 py-0.5 rounded-full border ${badgeBg}`}>
                      {status.toUpperCase()}
                    </span>
                  </div>
                  <h4 className="font-bold text-slate-900 text-sm mt-1">{s.name}</h4>
                  <p className="text-xs text-slate-500 mt-0.5">{s.desc}</p>
                </div>
              </div>
            );
          })}
        </div>
      </div>
    );
  };

  const renderDocument = (doc: WorkflowDocument | undefined, isDraft: boolean = false) => {
    if (!doc) return null;

    const items: QuoteItem[] = isEditing ? editItems : (doc.content?.items || []);
    
    // Calculate total values (only sum up items where accepted !== false)
    const activeItems = items.filter(it => it.accepted !== false);
    const totalQty = activeItems.reduce((sum, it) => {
      const q = doc.type === "MRQ" ? it.requested_quantity : (it.quoted_quantity !== undefined ? it.quoted_quantity : it.requested_quantity);
      return sum + (q || 0);
    }, 0);
    const totalCost = activeItems.reduce((sum, it) => {
      const q = doc.type === "MRQ" ? it.requested_quantity : (it.quoted_quantity !== undefined ? it.quoted_quantity : it.requested_quantity);
      const p = it.final_price || it.quoted_price || it.requested_price || 0;
      return sum + ((q || 0) * p);
    }, 0);

    return (
      <div className="bg-white border border-slate-200 rounded-xl shadow-md overflow-hidden flex flex-col h-full animate-fade-in">
        {/* Card Header */}
        <div className="px-5 py-4 border-b border-slate-100 bg-slate-50 flex items-center justify-between">
          <div className="flex items-center space-x-2">
            <FileText className="h-5 w-5 text-slate-500" />
            <span className="font-bold text-slate-900 text-sm">
              {doc.type} {isDraft ? "(DRAFT DRAFT)" : ""} - {doc.id}
            </span>
          </div>
          <span className="text-xs text-slate-400">{new Date(doc.created_at).toLocaleTimeString()}</span>
        </div>

        {/* Card Body */}
        <div className="p-5 flex-1 overflow-y-auto space-y-6 max-h-[480px]">
          {/* Business Letter Text */}
          <div className="border border-slate-100 bg-amber-50/40 p-4 rounded-xl font-serif text-sm leading-relaxed text-slate-800 whitespace-pre-line shadow-inner min-h-[120px]">
            {isEditing ? (
              <textarea
                value={editLetter}
                onChange={(e) => setEditLetter(e.target.value)}
                className="w-full h-44 p-3 font-serif border border-slate-300 rounded-lg text-sm bg-white focus:outline-none focus:ring-1 focus:ring-blue-500 focus:border-blue-500"
              />
            ) : (
              doc.letter_text
            )}
          </div>

          {/* Table of items */}
          <div>
            <h4 className="text-xs font-bold text-slate-400 uppercase tracking-wider mb-2">Requisition Items</h4>
            <div className="border border-slate-100 rounded-lg overflow-x-auto">
              <table className="min-w-full divide-y divide-slate-150 text-xs">
                <thead className="bg-slate-50">
                  <tr>
                    <th className="px-3 py-2 text-left font-bold text-slate-500">SKU</th>
                    <th className="px-3 py-2 text-right font-bold text-slate-500">Qty</th>
                    <th className="px-3 py-2 text-right font-bold text-slate-500">Price</th>
                    {doc.type === "CounterOffer" || doc.type === "FinalLetter" || doc.type === "FinalQuote" ? (
                      <>
                        <th className="px-3 py-2 text-right font-bold text-slate-500">Disc</th>
                        <th className="px-3 py-2 text-right font-bold text-slate-500">Final</th>
                      </>
                    ) : null}
                    {(doc.type === "FinalLetter" || doc.type === "FinalQuote") && (
                      <th className="px-3 py-2 text-center font-bold text-slate-500">Approval</th>
                    )}
                    <th className="px-3 py-2 text-right font-bold text-slate-500">Total</th>
                  </tr>
                </thead>
                <tbody className="bg-white divide-y divide-slate-100">
                  {items.map((it, idx) => {
                    const isItemAccepted = it.accepted !== false;
                    const qVal = doc.type === "MRQ" ? it.requested_quantity : (it.quoted_quantity !== undefined ? it.quoted_quantity : it.requested_quantity);
                    const qty = isItemAccepted ? (qVal || 0) : 0;
                    const price = it.quoted_price || it.requested_price || 0;
                    const finalPrice = it.final_price || price;
                    const subtotal = qty * finalPrice;
                    
                    return (
                      <tr key={it.sku} className={isItemAccepted ? "transition-opacity" : "opacity-40 line-through bg-slate-50/50 transition-opacity"}>
                        <td className="px-3 py-2 font-bold text-slate-900">{it.sku}</td>
                        <td className="px-3 py-2 text-right whitespace-nowrap">
                          {isEditing ? (
                            <input
                              type="number"
                              min="0"
                              value={it.requested_quantity}
                              onChange={(e) => updateItemQty(idx, parseInt(e.target.value) || 0)}
                              className="w-16 px-1.5 py-0.5 border border-slate-300 rounded text-right focus:outline-none focus:ring-1 focus:ring-blue-500"
                            />
                          ) : (
                            doc.type === "MRQ" ? it.requested_quantity : (it.quoted_quantity !== undefined ? it.quoted_quantity : it.requested_quantity)
                          )}
                        </td>
                        <td className="px-3 py-2 text-right">
                          {isEditing ? (
                            <input
                              type="number"
                              step="0.05"
                              value={it.requested_price}
                              onChange={(e) => updateItemPrice(idx, parseFloat(e.target.value) || 0.0)}
                              className="w-20 px-1.5 py-0.5 border border-slate-300 rounded text-right focus:outline-none focus:ring-1 focus:ring-blue-500"
                            />
                          ) : (
                            `$${price.toFixed(2)}`
                          )}
                        </td>
                        {doc.type === "CounterOffer" || doc.type === "FinalLetter" || doc.type === "FinalQuote" ? (
                          <>
                            <td className="px-3 py-2 text-right text-purple-600 font-medium">
                              {(it.discount * 100).toFixed(0)}%
                            </td>
                            <td className="px-3 py-2 text-right font-semibold text-slate-900">
                              ${finalPrice.toFixed(2)}
                            </td>
                          </>
                        ) : null}
                        {(doc.type === "FinalLetter" || doc.type === "FinalQuote") && (
                          <td className="px-3 py-2 text-center whitespace-nowrap">
                            {isDraft ? (
                              <button
                                onClick={() => toggleItemAccept(it.sku)}
                                className={`px-2 py-0.5 rounded text-xxs font-extrabold transition-colors cursor-pointer ${
                                  isItemAccepted
                                    ? "bg-green-100 text-green-700 hover:bg-green-200"
                                    : "bg-red-100 text-red-700 hover:bg-red-200"
                                }`}
                              >
                                {isItemAccepted ? "✓ Active" : "✗ Decline"}
                              </button>
                            ) : (
                              <span className={`px-2 py-0.5 rounded text-xxs font-bold ${
                                isItemAccepted
                                  ? "bg-green-50 text-green-600 border border-green-200"
                                  : "bg-red-50 text-red-600 border border-red-200"
                              }`}>
                                {isItemAccepted ? "Accepted" : "Declined"}
                              </span>
                            )}
                          </td>
                        )}
                        <td className="px-3 py-2 text-right font-bold text-slate-900">
                          ${subtotal.toFixed(2)}
                        </td>
                      </tr>
                    );
                  })}
                  <tr className="bg-slate-50 font-bold">
                    <td className="px-3 py-2 text-slate-900">Total</td>
                    <td className="px-3 py-2 text-right">{totalQty}</td>
                    <td className="px-3 py-2" colSpan={doc.type === "CounterOffer" || doc.type === "FinalLetter" || doc.type === "FinalQuote" ? (doc.type === "FinalLetter" || doc.type === "FinalQuote" ? 4 : 3) : 1} />
                    <td className="px-3 py-2 text-right text-slate-900">${totalCost.toFixed(2)}</td>
                  </tr>
                </tbody>
              </table>
            </div>
          </div>
        </div>
      </div>
    );
  };

  return (
    <div className="max-w-none w-full px-8 py-6 flex flex-col h-[calc(100vh-64px)] justify-between">
      {/* Upper header */}
      <div className="mb-4 flex justify-between items-center">
        <div>
          <h2 className="text-xl font-bold text-slate-900">Negotiation Simulator Board</h2>
          {activeWorkflow && (
            <p className="text-xs text-slate-500 mt-0.5">
              Active Session: <span className="font-bold text-blue-600">{activeWorkflow.workflow_id}</span> • Status: <span className="font-bold text-slate-700">{activeWorkflow.status}</span>
            </p>
          )}
        </div>
        {activeWorkflow && activeWorkflow.status !== "ACTIVE" && (
          <button
            onClick={handleReset}
            className="px-4 py-1.5 border border-slate-300 rounded-lg text-xs font-bold text-slate-700 hover:bg-slate-50 transition-colors"
          >
            Clear Board
          </button>
        )}
      </div>

      {error && (
        <div className="bg-red-50 border-l-4 border-red-500 p-4 mb-4 rounded-r-lg flex items-center justify-between">
          <div className="flex items-center space-x-2 text-sm text-red-700">
            <AlertCircle className="h-5 w-5" />
            <span>{error}</span>
          </div>
          <button onClick={() => setError(null)} className="text-red-400 hover:text-red-600 text-xs font-bold">Dismiss</button>
        </div>
      )}

      {/* Main split-screen panel */}
      <div className="grid grid-cols-1 lg:grid-cols-12 gap-6 flex-1 overflow-hidden min-h-[500px]">
        <div className="lg:col-span-5 bg-white border-2 border-blue-100 rounded-2xl shadow-md p-5 pt-6 flex flex-col justify-between overflow-hidden relative">
          <div className="h-1.5 bg-gradient-to-r from-[#4285F4] via-[#EA4335] via-[#FBBC05] to-[#34A853] w-full absolute top-0 left-0" />
          <div className="flex flex-col h-full justify-between">
            {/* Buyer header */}
            <div className="flex justify-between items-start pb-4 border-b border-slate-100 mb-4">
              <div className="flex items-center space-x-3">
                <div className="h-10 w-10 bg-blue-100 rounded-xl flex items-center justify-center text-blue-700">
                  <Building2 className="h-5 w-5" />
                </div>
                <div>
                  <span className="text-xxs font-bold text-blue-600 uppercase tracking-wider block">Buyer (Company A)</span>
                  <h4 className="font-bold text-slate-900 text-sm">MegaMart Online</h4>
                </div>
              </div>
              <span className="text-xxs font-semibold bg-blue-50 text-blue-700 border border-blue-200 px-2 py-0.5 rounded-full">
                Gemini Agent
              </span>
            </div>

            {/* Document display */}
            <div className="flex-1 overflow-hidden">
              {activeWorkflow ? (
                // Show document if created by Buyer and is current step, or show history
                (() => {
                  const buyerDocTypes = ["MRQ", "CounterOffer", "FinalQuote", "PO"];
                  const draft = activeWorkflow.current_draft;
                  const isBuyerDraft = draft && draft.created_by === "Buyer";
                  
                  if (isBuyerDraft) {
                    return renderDocument(draft, true);
                  }
                  
                  // Else look for last buyer document in history
                  const buyerDocs = activeWorkflow.documents.filter(d => buyerDocTypes.includes(d.type));
                  if (buyerDocs.length > 0) {
                    return renderDocument(buyerDocs[buyerDocs.length - 1], false);
                  }
                  
                  return (
                    <div className="h-full flex flex-col justify-center items-center text-slate-400 text-xs">
                      <span>No documents drafted yet.</span>
                    </div>
                  );
                })()
              ) : (
                <div className="h-full flex flex-col justify-center items-center text-slate-400 text-xs text-center p-6 border-2 border-dashed border-slate-200 rounded-xl">
                  <span>Start a new simulation to activate MegaMart Online's Buyer agent.</span>
                </div>
              )}
            </div>
          </div>
        </div>

        {/* Timeline Panel */}
        <div className="lg:col-span-2 bg-slate-50 border-2 border-slate-100 rounded-2xl shadow-md p-4 pt-5 flex flex-col justify-between overflow-y-auto relative">
          <div className="h-1.5 bg-gradient-to-r from-[#4285F4] via-[#EA4335] via-[#FBBC05] to-[#34A853] w-full absolute top-0 left-0" />
          {renderTimeline()}
          
          {/* Action console for Human Operator */}
          <div className="mt-6 pt-4 border-t border-slate-200 space-y-4">
            <h4 className="text-xxs font-bold text-slate-400 uppercase tracking-wider flex items-center space-x-1.5">
              <UserCheck className="h-3.5 w-3.5" />
              <span>Human-In-The-Loop Action Console</span>
            </h4>
            
            {!activeWorkflow ? (
              <button
                disabled={loading}
                onClick={handleStart}
                className="w-full flex justify-center items-center space-x-2 py-3 px-4 border border-transparent rounded-xl shadow bg-blue-600 hover:bg-blue-700 text-white font-bold text-sm disabled:opacity-50 transition-colors cursor-pointer"
              >
                {loading ? (
                  <>
                    <Loader2 className="h-4 w-4 animate-spin" />
                    <span>Booting Agents...</span>
                  </>
                ) : (
                  <>
                    <Play className="h-4 w-4 fill-current" />
                    <span>Start Simulation Run</span>
                  </>
                )}
              </button>
            ) : activeWorkflow.status === "ACTIVE" ? (
              // Display actions for the current draft
              activeWorkflow.current_draft ? (
                isEditing ? (
                  <div className="grid grid-cols-2 gap-3">
                    <button
                      onClick={handleEditSave}
                      disabled={loading}
                      className="flex justify-center items-center space-x-1.5 py-2.5 px-3 border border-transparent rounded-lg shadow-sm bg-green-600 hover:bg-green-700 text-white font-bold text-xs transition-colors cursor-pointer"
                    >
                      Save Draft
                    </button>
                    <button
                      onClick={() => setIsEditing(false)}
                      className="flex justify-center items-center space-x-1.5 py-2.5 px-3 border border-slate-300 rounded-lg text-slate-700 bg-white hover:bg-slate-50 font-bold text-xs transition-colors cursor-pointer"
                    >
                      Cancel
                    </button>
                  </div>
                ) : (
                  <div className="space-y-2">
                    <button
                      disabled={loading}
                      onClick={handleSend}
                      className="w-full flex justify-center items-center space-x-2 py-3 px-4 border border-transparent rounded-xl shadow bg-green-600 hover:bg-green-700 text-white font-bold text-sm disabled:opacity-50 transition-colors cursor-pointer"
                    >
                      <Send className="h-4 w-4" />
                      <span>Approve & Send Draft</span>
                    </button>
                    
                    <div className="grid grid-cols-2 gap-3">
                      <button
                        onClick={handleEditToggle}
                        disabled={loading}
                        className="flex justify-center items-center space-x-1.5 py-2 px-3 border border-slate-300 rounded-lg text-slate-700 bg-white hover:bg-slate-50 font-bold text-xs transition-colors cursor-pointer"
                      >
                        <Edit3 className="h-3.5 w-3.5" />
                        <span>Edit Draft</span>
                      </button>
                      <button
                        onClick={handleReject}
                        disabled={loading}
                        className="flex justify-center items-center space-x-1.5 py-2 px-3 border border-red-200 rounded-lg text-red-700 bg-red-50 hover:bg-red-100 font-bold text-xs transition-colors cursor-pointer"
                      >
                        <XCircle className="h-3.5 w-3.5" />
                        <span>Reject Draft</span>
                      </button>
                    </div>
                  </div>
                )
              ) : (
                <div className="flex justify-center items-center py-4 text-xs text-slate-500 font-medium">
                  <Loader2 className="h-4 w-4 animate-spin mr-2 text-blue-600" />
                  <span>Agent is drafting next letter...</span>
                </div>
              )
            ) : activeWorkflow.status === "COMPLETED" ? (
              <div className="bg-green-50 border border-green-200 rounded-xl p-3 flex flex-col items-center text-center">
                <CheckCircle className="h-8 w-8 text-green-600 mb-2" />
                <span className="text-sm font-bold text-green-800">Negotiation Fully Completed!</span>
                <span className="text-xxs text-green-600 mt-1">Contracts signed. Inventory levels updated.</span>
                <button
                  onClick={handleReset}
                  className="mt-3 inline-flex items-center px-4 py-1.5 border border-green-300 rounded-lg text-xs font-bold text-green-700 hover:bg-green-100 transition-colors"
                >
                  Start Another Session
                </button>
              </div>
            ) : (
              <div className="bg-red-50 border border-red-200 rounded-xl p-3 flex flex-col items-center text-center">
                <XCircle className="h-8 w-8 text-red-600 mb-2" />
                <span className="text-sm font-bold text-red-800">Workflow Terminated</span>
                <button
                  onClick={handleReset}
                  className="mt-3 inline-flex items-center px-4 py-1.5 border border-red-300 rounded-lg text-xs font-bold text-red-700 hover:bg-red-100 transition-colors"
                >
                  Reset Board
                </button>
              </div>
            )}
          </div>
        </div>

        {/* Supplier Panel */}
        <div className="lg:col-span-5 bg-white border-2 border-orange-100 rounded-2xl shadow-md p-5 pt-6 flex flex-col justify-between overflow-hidden relative">
          <div className="h-1.5 bg-gradient-to-r from-[#4285F4] via-[#EA4335] via-[#FBBC05] to-[#34A853] w-full absolute top-0 left-0" />
          <div className="flex flex-col h-full justify-between">
            {/* Supplier header */}
            <div className="flex justify-between items-start pb-4 border-b border-slate-100 mb-4">
              <div className="flex items-center space-x-3">
                <div className="h-10 w-10 bg-orange-100 rounded-xl flex items-center justify-center text-orange-700">
                  <Building2 className="h-5 w-5" />
                </div>
                <div>
                  <span className="text-xxs font-bold text-orange-600 uppercase tracking-wider block">Supplier (Company B)</span>
                  <h4 className="font-bold text-slate-900 text-sm">FreshFizz Consumer Products</h4>
                </div>
              </div>
              <span className="text-xxs font-semibold bg-orange-50 text-orange-700 border border-orange-200 px-2 py-0.5 rounded-full">
                Claude Agent
              </span>
            </div>

            {/* Document display */}
            <div className="flex-1 overflow-hidden">
              {activeWorkflow ? (
                // Show document if created by Supplier and is current step, or show history
                (() => {
                  const supplierDocTypes = ["Proposal", "FinalLetter", "Invoice", "DO"];
                  const draft = activeWorkflow.current_draft;
                  const isSupplierDraft = draft && draft.created_by === "Supplier";
                  
                  if (isSupplierDraft) {
                    return renderDocument(draft, true);
                  }
                  
                  // Else look for last supplier document in history
                  const supplierDocs = activeWorkflow.documents.filter(d => supplierDocTypes.includes(d.type));
                  if (supplierDocs.length > 0) {
                    return renderDocument(supplierDocs[supplierDocs.length - 1], false);
                  }
                  
                  return (
                    <div className="h-full flex flex-col justify-center items-center text-slate-400 text-xs">
                      <span>No documents drafted yet.</span>
                    </div>
                  );
                })()
              ) : (
                <div className="h-full flex flex-col justify-center items-center text-slate-400 text-xs text-center p-6 border-2 border-dashed border-slate-200 rounded-xl">
                  <span>Start a new simulation to activate FreshFizz's Supplier agent.</span>
                </div>
              )}
            </div>
          </div>
        </div>
      </div>

      {/* Completion outputs (only if completed) */}
      {activeWorkflow && activeWorkflow.status === "COMPLETED" && (() => {
        const mrqDoc = activeWorkflow.documents.find(d => d.type === "MRQ");
        const poDoc = activeWorkflow.documents.find(d => d.type === "PO");
        const initialItems = mrqDoc?.content?.items || [];
        const finalItems = poDoc?.content?.items || [];
        
        const initialValue = initialItems.reduce((sum: number, it: any) => sum + (it.requested_quantity * it.requested_price), 0);
        const finalValue = poDoc?.content?.total_value || 0;
        const totalSavings = Math.max(0, initialValue - finalValue);
        const savingsPct = initialValue > 0 ? (totalSavings / initialValue * 100) : 0;
        
        const initialQtySum = initialItems.reduce((sum: number, it: any) => sum + it.requested_quantity, 0);
        const finalQtySum = finalItems.reduce((sum: number, it: any) => sum + (it.quoted_quantity || 0), 0);
        const fulfillmentSuccessRate = initialQtySum > 0 ? (finalQtySum / initialQtySum * 100) : 0;

        return (
          <div className="mt-6 border-t border-slate-200 pt-6 space-y-6 animate-slide-up">
            {/* Scorecard KPIs */}
            <div className="bg-white border-2 border-green-200 rounded-2xl shadow-sm overflow-hidden relative">
              <div className="h-1 bg-gradient-to-r from-green-400 via-[#34A853] to-emerald-600 w-full absolute top-0 left-0" />
              <div className="p-5">
                <h3 className="font-bold text-slate-900 text-sm md:text-base flex items-center space-x-2 mb-4">
                  <span className="text-xl">📈</span>
                  <span>Negotiation Performance Scorecard & Cost Audit</span>
                </h3>
                
                <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
                  <div className="bg-slate-50 border border-slate-150 p-4 rounded-xl">
                    <span className="text-xxs font-bold text-slate-400 uppercase tracking-wider block">Fulfillment Rate</span>
                    <span className="text-xl md:text-2xl font-black text-slate-800 mt-1 block">{fulfillmentSuccessRate.toFixed(0)}%</span>
                    <span className="text-xxs text-slate-500 mt-1 block">{finalQtySum} of {initialQtySum} units secured</span>
                  </div>
                  
                  <div className="bg-slate-50 border border-slate-150 p-4 rounded-xl">
                    <span className="text-xxs font-bold text-slate-400 uppercase tracking-wider block">Contract Value Change</span>
                    <span className="text-xl md:text-2xl font-black text-slate-800 mt-1 block">${finalValue.toFixed(2)}</span>
                    <span className="text-xxs text-slate-500 mt-1 block">Initial request: ${initialValue.toFixed(2)}</span>
                  </div>
                  
                  <div className="bg-slate-50 border border-slate-150 p-4 rounded-xl">
                    <span className="text-xxs font-bold text-slate-400 uppercase tracking-wider block">Cost Savings Secured</span>
                    <span className="text-xl md:text-2xl font-black text-green-600 mt-1 block">${totalSavings.toFixed(2)}</span>
                    <span className="text-xxs bg-green-50 text-green-700 px-2 py-0.5 rounded font-bold mt-1 inline-block">{savingsPct.toFixed(1)}% total savings</span>
                  </div>
                  
                  <div className="bg-slate-50 border border-slate-150 p-4 rounded-xl">
                    <span className="text-xxs font-bold text-slate-400 uppercase tracking-wider block">Supplier Dispatch lead</span>
                    <span className="text-xl md:text-2xl font-black text-slate-800 mt-1 block">3 business days</span>
                    <span className="text-xxs text-slate-500 mt-1 block">FOB Origin Shipping terms</span>
                  </div>
                </div>

                {/* Scorecard Table */}
                <div className="mt-6">
                  <h4 className="text-xxs font-bold text-slate-400 uppercase tracking-wider mb-2">Item-by-Item Saving Breakdown</h4>
                  <div className="border border-slate-100 rounded-xl overflow-hidden">
                    <table className="min-w-full divide-y divide-slate-150 text-xs text-left">
                      <thead className="bg-slate-50 text-slate-500">
                        <tr>
                          <th className="px-4 py-2 font-bold">SKU</th>
                          <th className="px-4 py-2 text-right font-bold">Initial Request</th>
                          <th className="px-4 py-2 text-right font-bold">Negotiated Qty</th>
                          <th className="px-4 py-2 text-right font-bold">Initial Price</th>
                          <th className="px-4 py-2 text-right font-bold">Negotiated Price</th>
                          <th className="px-4 py-2 text-right font-bold">Negotiated Savings</th>
                        </tr>
                      </thead>
                      <tbody className="bg-white divide-y divide-slate-100">
                        {initialItems.map((initIt: any) => {
                          const finalIt: any = finalItems.find((f: any) => f.sku === initIt.sku) || {};
                          const finalQty = finalIt.accepted !== false ? (finalIt.quoted_quantity || 0) : 0;
                          const finalPrice = finalIt.final_price || finalIt.quoted_price || initIt.requested_price;
                          const saving = (initIt.requested_quantity * initIt.requested_price) - (finalQty * finalPrice);
                          
                          return (
                            <tr key={initIt.sku} className="hover:bg-slate-50/50">
                              <td className="px-4 py-2.5 font-bold text-slate-900">{initIt.sku}</td>
                              <td className="px-4 py-2.5 text-right font-semibold text-slate-500">{initIt.requested_quantity} units</td>
                              <td className="px-4 py-2.5 text-right font-bold text-slate-800">
                                {finalQty} units
                                {finalQty < initIt.requested_quantity && (
                                  <span className="text-[10px] text-red-500 block">
                                    -{initIt.requested_quantity - finalQty} ({finalIt.accepted === false ? "Declined" : "Reduced"})
                                  </span>
                                )}
                              </td>
                              <td className="px-4 py-2.5 text-right font-semibold text-slate-500">${initIt.requested_price.toFixed(2)}</td>
                              <td className="px-4 py-2.5 text-right font-bold text-slate-800">
                                ${finalPrice.toFixed(2)}
                                {finalPrice < initIt.requested_price && (
                                  <span className="text-[10px] text-green-600 block">
                                    -{(((initIt.requested_price - finalPrice) / initIt.requested_price) * 100).toFixed(0)}% discount
                                  </span>
                                )}
                              </td>
                              <td className={`px-4 py-2.5 text-right font-bold ${saving > 0 ? "text-green-600" : "text-slate-500"}`}>
                                {saving > 0 ? `$${saving.toFixed(2)}` : "$0.00"}
                              </td>
                            </tr>
                          );
                        })}
                      </tbody>
                    </table>
                  </div>
                </div>
              </div>
            </div>

            {/* Document outputs */}
            <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
              {activeWorkflow.documents.filter(d => ["PO", "Invoice", "DO"].includes(d.type)).map((doc) => {
                const Icon = doc.type === "PO" ? ShoppingCart : doc.type === "Invoice" ? Receipt : Truck;
                const title = doc.type === "PO" ? "Purchase Order" : doc.type === "Invoice" ? "Commercial Invoice" : "Delivery Order";
                const borderClr = doc.type === "PO" ? "border-blue-200 bg-blue-50/20" : doc.type === "Invoice" ? "border-orange-200 bg-orange-50/20" : "border-green-200 bg-green-50/20";
                const textClr = doc.type === "PO" ? "text-blue-700" : doc.type === "Invoice" ? "text-orange-700" : "text-green-700";
                
                return (
                  <div key={doc.id} className={`border rounded-xl p-4 shadow-sm ${borderClr}`}>
                    <div className="flex items-center space-x-2 mb-2">
                      <Icon className={`h-5 w-5 ${textClr}`} />
                      <span className="font-bold text-slate-900 text-xs uppercase tracking-wider">{title}</span>
                    </div>
                    <div className="text-xxs font-mono text-slate-500 mb-2">Ref: {doc.id}</div>
                    <pre className="text-xxs font-mono bg-white p-3 rounded-lg border border-slate-100 text-slate-700 leading-relaxed overflow-x-auto whitespace-pre-wrap max-h-36">
                      {doc.letter_text}
                    </pre>
                  </div>
                );
              })}
            </div>
          </div>
        );
      })()}

      {/* Activity Log (scrolling panel at the bottom) */}
      <div className="mt-6 border border-slate-200 rounded-xl overflow-hidden bg-slate-900 shadow-sm flex flex-col h-40 max-h-40">
        <div className="px-4 py-2 border-b border-slate-800 bg-slate-950 flex items-center justify-between text-xs text-slate-400 font-bold">
          <div className="flex items-center space-x-2">
            <Terminal className="h-4 w-4 text-blue-400" />
            <span>Simulation Event Terminal</span>
          </div>
          {activeWorkflow && (
            <span className="text-xxs text-slate-500 font-mono">
              Events: {activeWorkflow.timeline.length}
            </span>
          )}
        </div>
        
        <div className="p-4 flex-1 overflow-y-auto font-mono text-xs text-slate-300 space-y-2 leading-relaxed">
          {!activeWorkflow ? (
            <div className="text-slate-500 text-center py-6">
              Simulation idle. Waiting for start signal...
            </div>
          ) : (
            <>
              {activeWorkflow.timeline.map((evt, idx) => {
                let badgeClr = "text-blue-400";
                if (evt.actor === "Supplier") badgeClr = "text-orange-400";
                if (evt.actor === "Human") badgeClr = "text-green-400";
                
                return (
                  <div key={idx} className="flex items-start space-x-2 border-b border-slate-800/30 pb-1.5 last:border-0 last:pb-0">
                    <span className="text-slate-500 text-xxs font-light whitespace-nowrap">
                      [{new Date(evt.timestamp).toLocaleTimeString()}]
                    </span>
                    <span className={`font-bold text-xxs uppercase whitespace-nowrap ${badgeClr}`}>
                      {evt.actor}
                    </span>
                    <span className="text-slate-400 font-bold whitespace-nowrap">
                      {evt.event}:
                    </span>
                    <span className="text-slate-200">{evt.description}</span>
                  </div>
                );
              })}
              
              {agentGenerating && (
                <div className="flex items-center space-x-2 text-slate-400 py-1">
                  <span className="text-xxs font-light">[{new Date().toLocaleTimeString()}]</span>
                  <Loader2 className="h-3 w-3 animate-spin text-blue-400" />
                  <span className="animate-pulse">LLM agent analysis in progress... please hold...</span>
                </div>
              )}
              <div ref={logEndRef} />
            </>
          )}
        </div>
      </div>
    </div>
  );
};
export default WorkflowSimulator;
