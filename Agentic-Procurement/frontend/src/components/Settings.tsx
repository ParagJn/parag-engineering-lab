import React, { useEffect, useState } from "react";
import { api, type Settings } from "../services/api";
import { Settings as SettingsIcon, Save, Eye, EyeOff, CheckCircle2 } from "lucide-react";

export const SettingsComponent: React.FC = () => {
  const [settings, setSettings] = useState<Settings>({
    gemini_key: "",
    claude_key: "",
    buyer_model: "gemini-1.5-flash",
    supplier_model: "claude-3-5-sonnet-20240620",
  });
  
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [success, setSuccess] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const [showGemini, setShowGemini] = useState(false);
  const [showClaude, setShowClaude] = useState(false);

  useEffect(() => {
    const fetchSettings = async () => {
      try {
        const data = await api.getSettings();
        setSettings(data);
      } catch (err: any) {
        setError(err.message || "Failed to load settings.");
      } finally {
        setLoading(false);
      }
    };
    fetchSettings();
  }, []);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setSaving(true);
    setSuccess(false);
    setError(null);
    try {
      await api.saveSettings(settings);
      setSuccess(true);
      setTimeout(() => setSuccess(false), 4000);
    } catch (err: any) {
      setError(err.message || "Failed to save settings.");
    } finally {
      setSaving(false);
    }
  };

  if (loading) {
    return (
      <div className="flex justify-center items-center py-20">
        <div className="animate-spin rounded-full h-10 w-10 border-b-2 border-blue-600"></div>
      </div>
    );
  }

  return (
    <div className="max-w-2xl mx-auto px-4 py-8">
      <div className="mb-8">
        <h2 className="text-2xl font-bold leading-7 text-slate-900 sm:text-3xl flex items-center space-x-2">
          <SettingsIcon className="h-8 w-8 text-blue-600" />
          <span>LLM Credentials & Settings</span>
        </h2>
        <p className="mt-1 text-sm text-slate-500">
          Configure API credentials and choose LLM model versions for the Buyer and Supplier agents.
        </p>
      </div>

      {success && (
        <div className="bg-green-50 border-l-4 border-green-500 p-4 mb-6 rounded-r-lg flex items-center space-x-3">
          <CheckCircle2 className="h-5 w-5 text-green-600" />
          <div className="text-sm font-semibold text-green-700">Settings saved and applied successfully.</div>
        </div>
      )}

      {error && (
        <div className="bg-red-50 border-l-4 border-red-500 p-4 mb-6 rounded-r-lg">
          <div className="text-sm text-red-700">{error}</div>
        </div>
      )}

      <form onSubmit={handleSubmit} className="bg-white border border-slate-200 shadow-sm rounded-xl p-6 space-y-6">
        {/* Gemini Settings */}
        <div>
          <h3 className="font-bold text-slate-900 text-sm uppercase tracking-wider mb-3">Buyer Agent (Google Gemini)</h3>
          
          <div className="space-y-4">
            <div>
              <label className="block text-sm font-semibold text-slate-700 mb-1">Gemini API Key</label>
              <div className="relative rounded-lg shadow-sm">
                <input
                  type={showGemini ? "text" : "password"}
                  placeholder={settings.gemini_key ? "••••••••••••••••••••••••" : "Enter Google Gemini API Key"}
                  value={settings.gemini_key}
                  onChange={(e) => setSettings({ ...settings, gemini_key: e.target.value })}
                  className="block w-full pr-10 border border-slate-300 rounded-lg py-2 px-3 text-sm focus:outline-none focus:ring-1 focus:ring-blue-500 focus:border-blue-500"
                />
                <button
                  type="button"
                  onClick={() => setShowGemini(!showGemini)}
                  className="absolute inset-y-0 right-0 pr-3 flex items-center text-slate-400 hover:text-slate-600"
                >
                  {showGemini ? <EyeOff className="h-4.5 w-4.5" /> : <Eye className="h-4.5 w-4.5" />}
                </button>
              </div>
              <p className="mt-1.5 text-xs text-slate-500">
                If left blank, the simulator will automatically use **Mock Mode** fallbacks for testing.
              </p>
            </div>

            <div>
              <label className="block text-sm font-semibold text-slate-700 mb-1">Gemini Model Model</label>
              <select
                value={settings.buyer_model}
                onChange={(e) => setSettings({ ...settings, buyer_model: e.target.value })}
                className="block w-full border border-slate-300 rounded-lg py-2 px-3 text-sm bg-white focus:outline-none focus:ring-1 focus:ring-blue-500 focus:border-blue-500"
              >
                <option value="gemini-1.5-flash">Gemini 1.5 Flash (Fast & Efficient)</option>
                <option value="gemini-1.5-pro">Gemini 1.5 Pro (High Reasoning)</option>
                <option value="gemini-2.0-flash-exp">Gemini 2.0 Flash (Experimental)</option>
              </select>
            </div>
          </div>
        </div>

        <hr className="border-slate-200" />

        {/* Claude Settings */}
        <div>
          <h3 className="font-bold text-slate-900 text-sm uppercase tracking-wider mb-3">Supplier Agent (Anthropic Claude)</h3>
          
          <div className="space-y-4">
            <div>
              <label className="block text-sm font-semibold text-slate-700 mb-1">Claude API Key</label>
              <div className="relative rounded-lg shadow-sm">
                <input
                  type={showClaude ? "text" : "password"}
                  placeholder={settings.claude_key ? "••••••••••••••••••••••••" : "Enter Anthropic Claude API Key"}
                  value={settings.claude_key}
                  onChange={(e) => setSettings({ ...settings, claude_key: e.target.value })}
                  className="block w-full pr-10 border border-slate-300 rounded-lg py-2 px-3 text-sm focus:outline-none focus:ring-1 focus:ring-blue-500 focus:border-blue-500"
                />
                <button
                  type="button"
                  onClick={() => setShowClaude(!showClaude)}
                  className="absolute inset-y-0 right-0 pr-3 flex items-center text-slate-400 hover:text-slate-600"
                >
                  {showClaude ? <EyeOff className="h-4.5 w-4.5" /> : <Eye className="h-4.5 w-4.5" />}
                </button>
              </div>
              <p className="mt-1.5 text-xs text-slate-500">
                If left blank, the simulator will automatically use **Mock Mode** fallbacks for testing.
              </p>
            </div>

            <div>
              <label className="block text-sm font-semibold text-slate-700 mb-1">Claude Model Version</label>
              <select
                value={settings.supplier_model}
                onChange={(e) => setSettings({ ...settings, supplier_model: e.target.value })}
                className="block w-full border border-slate-300 rounded-lg py-2 px-3 text-sm bg-white focus:outline-none focus:ring-1 focus:ring-blue-500 focus:border-blue-500"
              >
                <option value="claude-3-5-sonnet-20240620">Claude 3.5 Sonnet (Recommended)</option>
                <option value="claude-3-5-haiku-20241022">Claude 3.5 Haiku (Fast)</option>
                <option value="claude-3-opus-20240229">Claude 3 Opus (Complex Logic)</option>
              </select>
            </div>
          </div>
        </div>


        <div className="pt-4">
          <button
            type="submit"
            disabled={saving}
            className="w-full flex justify-center items-center space-x-2 px-4 py-2 border border-transparent rounded-lg shadow-sm text-sm font-semibold text-white bg-blue-600 hover:bg-blue-700 focus:outline-none disabled:opacity-50 transition-colors cursor-pointer"
          >
            <Save className="h-4.5 w-4.5" />
            <span>{saving ? "Saving Configurations..." : "Save Settings"}</span>
          </button>
        </div>
      </form>
    </div>
  );
};
export default SettingsComponent;
