import React from "react";
import { LayoutDashboard, PlayCircle, Library, ShieldAlert, Settings as SettingsIcon } from "lucide-react";

interface NavbarProps {
  activeTab: string;
  setActiveTab: (tab: string) => void;
}

export const Navbar: React.FC<NavbarProps> = ({ activeTab, setActiveTab }) => {
  const tabs = [
    { id: "dashboard", label: "Dashboard", icon: LayoutDashboard },
    { id: "simulator", label: "Simulator", icon: PlayCircle },
    { id: "catalog", label: "Catalog", icon: Library },
    { id: "admin", label: "Admin Tools", icon: ShieldAlert },
    { id: "settings", label: "Settings", icon: SettingsIcon },
  ];

  return (
    <header className="bg-white border-b border-slate-200 sticky top-0 z-50 shadow-sm">
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
        <div className="flex justify-between h-16 items-center">
          <div className="flex items-center space-x-3">
            <div className="h-9 w-9 bg-blue-600 rounded-lg flex items-center justify-center text-white font-bold text-lg">
              P
            </div>
            <div>
              <span className="font-bold text-lg text-slate-900 block leading-tight">Agentic Procurement</span>
              <span className="text-xs text-slate-500 font-medium">Multi-Agent Enterprise Simulator</span>
            </div>
          </div>
          <nav className="flex space-x-1">
            {tabs.map((tab) => {
              const Icon = tab.icon;
              const isActive = activeTab === tab.id;
              return (
                <button
                  key={tab.id}
                  onClick={() => setActiveTab(tab.id)}
                  className={`flex items-center space-x-2 px-4 py-2 rounded-lg text-sm font-medium transition-colors ${isActive
                    ? "bg-blue-50 text-blue-700"
                    : "text-slate-600 hover:text-slate-950 hover:bg-slate-50"
                    }`}
                >
                  <Icon className={`h-4.5 w-4.5 ${isActive ? "text-blue-600" : "text-slate-400"}`} />
                  <span>{tab.label}</span>
                </button>
              );
            })}
          </nav>
        </div>
      </div>
    </header>
  );
};
export default Navbar;
