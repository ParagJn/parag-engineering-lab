import React, { useState } from "react";
import { api } from "../services/api";
import { ShieldAlert, Database, RotateCcw, Download, Upload, CheckCircle2 } from "lucide-react";

export const Admin: React.FC = () => {
  const [loading, setLoading] = useState(false);
  const [successMsg, setSuccessMsg] = useState<string | null>(null);
  const [errorMsg, setErrorMsg] = useState<string | null>(null);

  const handleAction = async (actionFn: () => Promise<void>, message: string) => {
    setLoading(true);
    setSuccessMsg(null);
    setErrorMsg(null);
    try {
      await actionFn();
      setSuccessMsg(message);
      // Automatically clear message after 4s
      setTimeout(() => setSuccessMsg(null), 4000);
    } catch (err: any) {
      setErrorMsg(err.message || "Failed to execute administration action.");
    } finally {
      setLoading(false);
    }
  };

  const handleExport = async () => {
    setLoading(true);
    setSuccessMsg(null);
    setErrorMsg(null);
    try {
      const [products, settings, history] = await Promise.all([
        api.getProducts(),
        api.getSettings(),
        api.getHistory()
      ]);
      
      const backupData = {
        products,
        settings,
        history,
        exported_at: new Date().toISOString()
      };
      
      const jsonString = `data:text/json;charset=utf-8,${encodeURIComponent(
        JSON.stringify(backupData, null, 2)
      )}`;
      
      const downloadAnchor = document.createElement("a");
      downloadAnchor.setAttribute("href", jsonString);
      downloadAnchor.setAttribute("download", `procurement_backup_${new Date().toISOString().split('T')[0]}.json`);
      document.body.appendChild(downloadAnchor);
      downloadAnchor.click();
      downloadAnchor.remove();
      
      setSuccessMsg("System configuration and history logs exported successfully.");
      setTimeout(() => setSuccessMsg(null), 4000);
    } catch (err: any) {
      setErrorMsg(err.message || "Failed to export data.");
    } finally {
      setLoading(false);
    }
  };

  const handleImport = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const files = e.target.files;
    if (!files || files.length === 0) return;
    
    setLoading(true);
    setSuccessMsg(null);
    setErrorMsg(null);
    
    const file = files[0];
    const reader = new FileReader();
    reader.onload = async (event) => {
      try {
        const json = JSON.parse(event.target?.result as string);
        
        // Import settings
        if (json.settings) {
          await api.saveSettings(json.settings);
        }
        
        // Clear active sessions & reset inventory/history
        await api.resetDatabase();
        
        setSuccessMsg("Configuration imported successfully (settings updated, database reset).");
        setTimeout(() => setSuccessMsg(null), 4000);
      } catch (err: any) {
        setErrorMsg(err.message || "Failed to parse or import data file.");
      } finally {
        setLoading(false);
        // Clear input value so same file can be selected again
        e.target.value = "";
      }
    };
    reader.readAsText(file);
  };

  return (
    <div className="max-w-4xl mx-auto px-4 py-8">
      <div className="mb-8">
        <h2 className="text-2xl font-bold leading-7 text-slate-900 sm:text-3xl flex items-center space-x-2">
          <ShieldAlert className="h-8 w-8 text-blue-600" />
          <span>System Administration</span>
        </h2>
        <p className="mt-1 text-sm text-slate-500">
          Rebuild databases, reset active workflows, and perform backups for the procurement simulator.
        </p>
      </div>

      {successMsg && (
        <div className="bg-green-50 border-l-4 border-green-500 p-4 mb-6 rounded-r-lg flex items-center space-x-3">
          <CheckCircle2 className="h-5 w-5 text-green-600" />
          <div className="text-sm font-semibold text-green-700">{successMsg}</div>
        </div>
      )}

      {errorMsg && (
        <div className="bg-red-50 border-l-4 border-red-500 p-4 mb-6 rounded-r-lg">
          <div className="text-sm text-red-700">{errorMsg}</div>
        </div>
      )}

      <div className="bg-white border border-slate-200 rounded-xl shadow-sm overflow-hidden divide-y divide-slate-200">
        {/* Rebuild Catalog */}
        <div className="p-6 flex flex-col md:flex-row justify-between items-start md:items-center gap-4">
          <div className="flex-1">
            <h3 className="font-bold text-slate-950 flex items-center space-x-2 text-base">
              <Database className="h-5 w-5 text-slate-500" />
              <span>Rebuild Product Database</span>
            </h3>
            <p className="text-sm text-slate-500 mt-1">
              Overwrites the active products catalog in `products.json` back to default seed settings. 
              Useful if items have been corrupted or need general restoration.
            </p>
          </div>
          <button
            disabled={loading}
            onClick={() => handleAction(api.rebuildCatalog, "Product catalog database rebuilt successfully.")}
            className="w-full md:w-auto inline-flex justify-center items-center px-4 py-2 border border-slate-300 rounded-lg text-sm font-semibold text-slate-700 bg-white hover:bg-slate-50 disabled:opacity-50 transition-colors"
          >
            Rebuild Database
          </button>
        </div>

        {/* Reset Database */}
        <div className="p-6 flex flex-col md:flex-row justify-between items-start md:items-center gap-4">
          <div className="flex-1">
            <h3 className="font-bold text-slate-950 flex items-center space-x-2 text-base">
              <RotateCcw className="h-5 w-5 text-slate-500" />
              <span>Reset Inventory & History</span>
            </h3>
            <p className="text-sm text-slate-500 mt-1">
              Restores product inventory numbers, terminates all running negotiation workflows, and clears all logged items in `history.json`.
            </p>
          </div>
          <button
            disabled={loading}
            onClick={() => handleAction(api.resetDatabase, "Inventory, history, and active sessions reset successfully.")}
            className="w-full md:w-auto inline-flex justify-center items-center px-4 py-2 border border-transparent rounded-lg text-sm font-semibold text-white bg-red-600 hover:bg-red-700 disabled:opacity-50 transition-colors"
          >
            Reset Simulator
          </button>
        </div>

        {/* Export JSON */}
        <div className="p-6 flex flex-col md:flex-row justify-between items-start md:items-center gap-4">
          <div className="flex-1">
            <h3 className="font-bold text-slate-950 flex items-center space-x-2 text-base">
              <Download className="h-5 w-5 text-slate-500" />
              <span>Export System Data</span>
            </h3>
            <p className="text-sm text-slate-500 mt-1">
              Downloads a backup file containing all products, system settings, and completed transaction histories.
            </p>
          </div>
          <button
            disabled={loading}
            onClick={handleExport}
            className="w-full md:w-auto inline-flex justify-center items-center px-4 py-2 border border-slate-300 rounded-lg text-sm font-semibold text-slate-700 bg-white hover:bg-slate-50 disabled:opacity-50 transition-colors"
          >
            Export Backup
          </button>
        </div>

        {/* Import JSON */}
        <div className="p-6 flex flex-col md:flex-row justify-between items-start md:items-center gap-4">
          <div className="flex-1">
            <h3 className="font-bold text-slate-950 flex items-center space-x-2 text-base">
              <Upload className="h-5 w-5 text-slate-500" />
              <span>Import System Data</span>
            </h3>
            <p className="text-sm text-slate-500 mt-1">
              Uploads a previous backup file to restore system settings. This will automatically trigger a database reset.
            </p>
          </div>
          <div className="w-full md:w-auto relative">
            <input
              type="file"
              id="import-file"
              accept=".json"
              onChange={handleImport}
              className="absolute inset-0 opacity-0 cursor-pointer w-full h-full"
              disabled={loading}
            />
            <button
              disabled={loading}
              className="w-full inline-flex justify-center items-center px-4 py-2 border border-slate-300 rounded-lg text-sm font-semibold text-slate-700 bg-white hover:bg-slate-50 disabled:opacity-50 transition-colors"
            >
              Import Backup
            </button>
          </div>
        </div>
      </div>
    </div>
  );
};
export default Admin;
