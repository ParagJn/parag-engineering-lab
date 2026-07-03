import { useState } from "react";
import Navbar from "./components/Navbar";
import Dashboard from "./components/Dashboard";
import WorkflowSimulator from "./components/WorkflowSimulator";
import Catalog from "./components/Catalog";
import Admin from "./components/Admin";
import SettingsComponent from "./components/Settings";

function App() {
  const [activeTab, setActiveTab] = useState<string>("dashboard");

  const renderContent = () => {
    switch (activeTab) {
      case "dashboard":
        return <Dashboard onStartSimulation={() => setActiveTab("simulator")} />;
      case "simulator":
        return <WorkflowSimulator />;
      case "catalog":
        return <Catalog />;
      case "admin":
        return <Admin />;
      case "settings":
        return <SettingsComponent />;
      default:
        return <Dashboard onStartSimulation={() => setActiveTab("simulator")} />;
    }
  };

  return (
    <div className="min-h-screen bg-slate-50 flex flex-col">
      <Navbar activeTab={activeTab} setActiveTab={setActiveTab} />
      <main className="flex-1">
        {renderContent()}
      </main>
    </div>
  );
}

export default App;
