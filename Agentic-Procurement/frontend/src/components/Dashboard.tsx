import React, { useEffect, useState } from "react";
import { api, type HistorySummary } from "../services/api";
import { FileSpreadsheet, DollarSign, Calendar, TrendingDown, Layers, X, Loader2, Award } from "lucide-react";

interface DashboardProps {
  onStartSimulation: () => void;
}

export const Dashboard: React.FC<DashboardProps> = ({ onStartSimulation }) => {
  const [history, setHistory] = useState<HistorySummary[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  // Report Modal States
  const [selectedWorkflowId, setSelectedWorkflowId] = useState<string | null>(null);
  const [reportText, setReportText] = useState<string | null>(null);
  const [loadingReport, setLoadingReport] = useState(false);
  const [showModal, setShowModal] = useState(false);

  useEffect(() => {
    const loadHistory = async () => {
      try {
        const data = await api.getHistory();
        setHistory(data);
      } catch (err: any) {
        setError(err.message || "Failed to load dashboard metrics.");
      } finally {
        setLoading(false);
      }
    };
    loadHistory();
  }, []);

  const handleOpenReport = async (workflowId: string) => {
    setSelectedWorkflowId(workflowId);
    setLoadingReport(true);
    setShowModal(true);
    setReportText(null);
    try {
      const data = await api.getWorkflowReport(workflowId);
      setReportText(data.report);
    } catch (err: any) {
      setReportText("### Error\nFailed to generate report. Details: " + err.message);
    } finally {
      setLoadingReport(false);
    }
  };

  const totalSpend = history.reduce((sum, h) => {
    const poDoc = h.documents.find((d) => d.type === "PO");
    return sum + (poDoc?.content?.total_value || 0);
  }, 0);

  const totalItems = history.reduce((sum, h) => {
    const poDoc = h.documents.find((d) => d.type === "PO");
    const itemQuantity = poDoc?.content?.items?.reduce((s: number, i: any) => s + (i.quoted_quantity || 0), 0) || 0;
    return sum + itemQuantity;
  }, 0);

  // Average discount applied
  const avgDiscount = history.length > 0 
    ? (history.reduce((sum, h) => {
        const poDoc = h.documents.find((d) => d.type === "PO");
        const discounts = poDoc?.content?.items?.map((i: any) => i.discount || 0) || [];
        const avgItemDisc = discounts.length > 0 ? (discounts.reduce((s: number, d: number) => s + d, 0) / discounts.length) : 0;
        return sum + avgItemDisc;
      }, 0) / history.length) * 100
    : 0;

  // Helper function to parse bold text **like this**
  const parseBold = (text: string) => {
    if (!text) return "";
    const parts = text.split("**");
    return parts.map((part, i) => i % 2 === 1 ? <strong key={i} className="font-extrabold text-slate-900">{part}</strong> : part);
  };

  // Helper custom React Markdown Renderer for friendly Gemini reports
  const renderMarkdown = (md: string | null) => {
    if (!md) return null;
    const lines = md.split("\n");
    let inTable = false;
    let tableRows: React.ReactNode[] = [];
    let tableHeaderParts: string[] = [];

    const elements: React.ReactNode[] = [];

    lines.forEach((line, idx) => {
      const trimmed = line.trim();
      
      // Handle Headers
      if (trimmed.startsWith("# ")) {
        elements.push(<h1 key={idx} className="text-xl font-extrabold text-slate-950 mt-6 mb-3 flex items-center space-x-2 border-b border-slate-100 pb-2">{trimmed.substring(2)}</h1>);
        return;
      }
      if (trimmed.startsWith("## ")) {
        elements.push(<h2 key={idx} className="text-base font-bold text-slate-900 mt-5 mb-2.5 flex items-center space-x-2 border-b border-slate-100/50 pb-1">{trimmed.substring(3)}</h2>);
        return;
      }
      if (trimmed.startsWith("### ")) {
        elements.push(<h3 key={idx} className="text-sm font-bold text-slate-800 mt-4 mb-2">{trimmed.substring(4)}</h3>);
        return;
      }
      
      // Handle Lists
      if (trimmed.startsWith("* ") || trimmed.startsWith("- ")) {
        const content = parseBold(trimmed.substring(2));
        elements.push(<li key={idx} className="ml-5 list-disc text-xs text-slate-600 mb-1">{content}</li>);
        return;
      }

      // Handle Tables
      if (trimmed.startsWith("|")) {
        const parts = trimmed.split("|").map(p => p.trim()).filter((_, i, arr) => i > 0 && i < arr.length - 1);
        if (parts.length > 0 && parts[0].includes("---")) {
          // Skip separation line
          return;
        }
        
        if (!inTable) {
          inTable = true;
          tableHeaderParts = parts;
          tableRows = [];
          return;
        }

        tableRows.push(
          <tr key={idx} className="hover:bg-slate-50 transition-colors">
            {parts.map((p, i) => (
              <td key={i} className="px-3 py-1.5 border-b border-slate-100 text-slate-700">
                {parseBold(p)}
              </td>
            ))}
          </tr>
        );
        return;
      }

      // If we were in a table and table line ended, output table
      if (inTable && !trimmed.startsWith("|")) {
        inTable = false;
        const currentHeader = [...tableHeaderParts];
        const currentRows = [...tableRows];
        elements.push(
          <div key={`table-${idx}`} className="overflow-x-auto my-4 border border-slate-200 rounded-lg shadow-sm">
            <table className="min-w-full divide-y divide-slate-200 text-xxs">
              <thead className="bg-slate-50">
                <tr>
                  {currentHeader.map((h, i) => (
                    <th key={i} className="px-3 py-2 text-left font-bold text-slate-600 uppercase tracking-wider">{h}</th>
                  ))}
                </tr>
              </thead>
              <tbody className="bg-white divide-y divide-slate-100">
                {currentRows}
              </tbody>
            </table>
          </div>
        );
        tableRows = [];
        tableHeaderParts = [];
      }

      if (trimmed === "") {
        elements.push(<div key={idx} className="h-1.5" />);
        return;
      }

      // Standard Paragraph
      elements.push(<p key={idx} className="text-xs text-slate-600 leading-relaxed mb-2">{parseBold(trimmed)}</p>);
    });

    // Handle trailing tables if file ends while inTable
    if (inTable && tableHeaderParts.length > 0) {
      elements.push(
        <div key="table-trail" className="overflow-x-auto my-4 border border-slate-200 rounded-lg shadow-sm">
          <table className="min-w-full divide-y divide-slate-200 text-xxs">
            <thead className="bg-slate-50">
              <tr>
                {tableHeaderParts.map((h, i) => (
                  <th key={i} className="px-3 py-2 text-left font-bold text-slate-600 uppercase tracking-wider">{h}</th>
                ))}
              </tr>
            </thead>
            <tbody className="bg-white divide-y divide-slate-100">
              {tableRows}
            </tbody>
          </table>
        </div>
      );
    }

    return elements;
  };

  if (loading) {
    return (
      <div className="flex justify-center items-center py-20">
        <div className="animate-spin rounded-full h-10 w-10 border-b-2 border-blue-600"></div>
      </div>
    );
  }

  return (
    <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
      {/* Welcome header */}
      <div className="md:flex md:items-center md:justify-between mb-8">
        <div className="flex-1 min-w-0">
          <h2 className="text-2xl font-bold leading-7 text-slate-900 sm:text-3xl sm:truncate">
            Procurement Operations Center
          </h2>
          <p className="mt-1 text-sm text-slate-500">
            Monitor agent-to-agent negotiations, audit history summaries, and track supply-chain value.
          </p>
        </div>
        <div className="mt-4 flex md:mt-0 md:ml-4">
          <button
            onClick={onStartSimulation}
            className="ml-3 inline-flex items-center px-4 py-2 border border-transparent rounded-lg shadow-sm text-sm font-semibold text-white bg-blue-600 hover:bg-blue-700 focus:outline-none transition-colors cursor-pointer"
          >
            New Negotiation Run
          </button>
        </div>
      </div>

      {error && (
        <div className="bg-red-50 border-l-4 border-red-400 p-4 mb-6 rounded-r-lg">
          <div className="text-sm text-red-700">{error}</div>
        </div>
      )}

      {/* KPI Cards */}
      <div className="grid grid-cols-1 gap-5 sm:grid-cols-2 lg:grid-cols-4 mb-8">
        <div className="bg-white overflow-hidden shadow-sm border border-slate-200 rounded-xl p-5 flex items-center space-x-4">
          <div className="p-3 bg-blue-50 rounded-lg text-blue-600">
            <Layers className="h-6 w-6" />
          </div>
          <div>
            <p className="text-sm font-semibold text-slate-500 uppercase tracking-wider">Total Runs</p>
            <p className="text-2xl font-bold text-slate-900">{history.length}</p>
          </div>
        </div>

        <div className="bg-white overflow-hidden shadow-sm border border-slate-200 rounded-xl p-5 flex items-center space-x-4">
          <div className="p-3 bg-green-50 rounded-lg text-green-600">
            <DollarSign className="h-6 w-6" />
          </div>
          <div>
            <p className="text-sm font-semibold text-slate-500 uppercase tracking-wider">Total Value</p>
            <p className="text-2xl font-bold text-slate-900">${totalSpend.toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 })}</p>
          </div>
        </div>

        <div className="bg-white overflow-hidden shadow-sm border border-slate-200 rounded-xl p-5 flex items-center space-x-4">
          <div className="p-3 bg-amber-50 rounded-lg text-amber-600">
            <FileSpreadsheet className="h-6 w-6" />
          </div>
          <div>
            <p className="text-sm font-semibold text-slate-500 uppercase tracking-wider">Fulfillments</p>
            <p className="text-2xl font-bold text-slate-900">{totalItems} units</p>
          </div>
        </div>

        <div className="bg-white overflow-hidden shadow-sm border border-slate-200 rounded-xl p-5 flex items-center space-x-4">
          <div className="p-3 bg-purple-50 rounded-lg text-purple-600">
            <TrendingDown className="h-6 w-6" />
          </div>
          <div>
            <p className="text-sm font-semibold text-slate-500 uppercase tracking-wider">Avg Discount</p>
            <p className="text-2xl font-bold text-slate-900">{avgDiscount.toFixed(2)}%</p>
          </div>
        </div>
      </div>

      {/* History Log Table */}
      <div className="bg-white border border-slate-200 rounded-xl shadow-sm overflow-hidden">
        <div className="px-6 py-4 border-b border-slate-200">
          <h3 className="text-lg font-bold text-slate-900">Completed Negotiation History</h3>
        </div>
        
        {history.length === 0 ? (
          <div className="p-12 text-center text-slate-500">
            No completed simulations yet. Click "New Negotiation Run" above to start your first simulation!
          </div>
        ) : (
          <div className="overflow-x-auto">
            <table className="min-w-full divide-y divide-slate-200">
              <thead className="bg-slate-50">
                <tr>
                  <th scope="col" className="px-6 py-3 text-left text-xs font-semibold text-slate-500 uppercase tracking-wider">Run ID</th>
                  <th scope="col" className="px-6 py-3 text-left text-xs font-semibold text-slate-500 uppercase tracking-wider">Time Window</th>
                  <th scope="col" className="px-6 py-3 text-left text-xs font-semibold text-slate-500 uppercase tracking-wider">Financial Summary</th>
                  <th scope="col" className="px-6 py-3 text-left text-xs font-semibold text-slate-500 uppercase tracking-wider">Transaction Narrative</th>
                </tr>
              </thead>
              <tbody className="bg-white divide-y divide-slate-200">
                {history.map((run) => {
                  const poDoc = run.documents.find((d) => d.type === "PO");
                  const value = poDoc?.content?.total_value || 0;
                  const itemTypes = poDoc?.content?.items?.length || 0;
                  
                  return (
                    <tr key={run.workflow_id} className="hover:bg-slate-50 transition-colors">
                      <td className="px-6 py-4 whitespace-nowrap text-sm font-bold">
                        <button
                          onClick={() => handleOpenReport(run.workflow_id)}
                          className="text-blue-600 hover:text-blue-800 hover:underline font-bold text-left focus:outline-none cursor-pointer"
                        >
                          {run.workflow_id}
                        </button>
                      </td>
                      <td className="px-6 py-4 whitespace-nowrap text-sm text-slate-500 flex flex-col">
                        <span className="flex items-center text-slate-700">
                          <Calendar className="h-3.5 w-3.5 mr-1 text-slate-400" />
                          {new Date(run.start_time).toLocaleDateString()}
                        </span>
                        <span className="text-xs text-slate-400 mt-0.5">
                          {new Date(run.start_time).toLocaleTimeString()} - {new Date(run.end_time).toLocaleTimeString()}
                        </span>
                      </td>
                      <td className="px-6 py-4 whitespace-nowrap text-sm text-slate-900">
                        <span className="font-bold block">${value.toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 })}</span>
                        <span className="text-xs text-slate-500">{itemTypes} catalog product lines</span>
                      </td>
                      <td className="px-6 py-4 text-xs text-slate-600 max-w-md line-clamp-2 mt-2">
                        {/* Strip markdown hashes for simple narrative column preview */}
                        {run.summary.replace(/[#*|]/g, "").substring(0, 140)}...
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        )}
      </div>

      {/* High-Level Report Modal */}
      {showModal && (
        <div className="fixed inset-0 z-50 overflow-y-auto flex items-center justify-center p-4">
          {/* Backdrop */}
          <div 
            className="fixed inset-0 bg-slate-900/60 backdrop-blur-sm transition-opacity"
            onClick={() => setShowModal(false)}
          />

          {/* Modal Content */}
          <div className="relative bg-white border border-slate-200 rounded-2xl shadow-2xl max-w-3xl w-full max-h-[85vh] flex flex-col overflow-hidden transform transition-all">
            {/* Header */}
            <div className="px-6 py-4 border-b border-slate-200 bg-slate-50 flex items-center justify-between">
              <div className="flex items-center space-x-2">
                <Award className="h-5 w-5 text-blue-600 animate-pulse" />
                <h3 className="text-lg font-bold text-slate-900">
                  Negotiation Audit Report ({selectedWorkflowId})
                </h3>
              </div>
              <button 
                onClick={() => setShowModal(false)}
                className="p-1 rounded-lg text-slate-400 hover:text-slate-600 hover:bg-slate-100 transition-colors focus:outline-none cursor-pointer"
              >
                <X className="h-5 w-5" />
              </button>
            </div>

            {/* Body */}
            <div className="p-6 flex-1 overflow-y-auto max-h-[60vh] scrollbar-thin">
              {loadingReport ? (
                <div className="flex flex-col justify-center items-center py-20 space-y-3">
                  <Loader2 className="h-8 w-8 animate-spin text-blue-600" />
                  <span className="text-xs text-slate-500 font-semibold animate-pulse">
                    Gemini AI compiling friendly negotiation report... please hold...
                  </span>
                </div>
              ) : (
                <div className="prose prose-slate max-w-none">
                  {renderMarkdown(reportText)}
                </div>
              )}
            </div>

            {/* Footer */}
            <div className="px-6 py-4 border-t border-slate-200 bg-slate-50 flex justify-end">
              <button
                onClick={() => setShowModal(false)}
                className="px-4 py-2 bg-blue-600 hover:bg-blue-700 text-white font-bold text-xs rounded-lg shadow-sm transition-colors cursor-pointer"
              >
                Close Report
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};
export default Dashboard;
