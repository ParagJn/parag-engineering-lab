
import { NavLink } from 'react-router-dom';

const Sidebar = () => {
  return (
    <aside className="w-[280px] h-screen fixed left-0 top-0 flex flex-col bg-surface border-r border-outline-variant shadow-sm z-50">
      <div className="flex flex-col gap-unit py-container-margin h-full">
        {/* Brand Header */}
        <div className="px-6 mb-8 flex items-center gap-3">
          <div className="w-10 h-10 bg-primary-container rounded flex items-center justify-center">
            <span className="material-symbols-outlined text-on-primary-container">energy_savings_leaf</span>
          </div>
          <div>
            <h1 className="font-headline-md text-headline-md font-bold tracking-tight text-primary">GridData Dashboard</h1>
            <p className="font-label-md text-label-md text-on-surface-variant">Enterprise Pipeline Control</p>
          </div>
        </div>

        {/* Navigation Links */}
        <nav className="flex-1 px-4 space-y-1">
          <NavLink
            to="/"
            className={({ isActive }) =>
              `flex items-center gap-3 px-4 py-3 font-label-md text-label-md rounded-lg transition-colors duration-150 ${isActive
                ? "text-primary font-bold border-r-2 border-primary bg-surface-container-low"
                : "text-on-surface-variant hover:bg-surface-container hover:text-primary"
              }`
            }
          >
            <span className="material-symbols-outlined">dashboard</span>
            Pipeline Overview
          </NavLink>
          <NavLink
            to="/monitor"
            className={({ isActive }) =>
              `flex items-center gap-3 px-4 py-3 font-label-md text-label-md rounded-lg transition-colors duration-150 ${isActive
                ? "text-primary font-bold border-r-2 border-primary bg-surface-container-low"
                : "text-on-surface-variant hover:bg-surface-container hover:text-primary"
              }`
            }
          >
            <span className="material-symbols-outlined">monitoring</span>
            Real-Time Monitor
          </NavLink>
          <NavLink
            to="/quality"
            className={({ isActive }) =>
              `flex items-center gap-3 px-4 py-3 font-label-md text-label-md rounded-lg transition-colors duration-150 ${isActive
                ? "text-primary font-bold border-r-2 border-primary bg-surface-container-low"
                : "text-on-surface-variant hover:bg-surface-container hover:text-primary"
              }`
            }
          >
            <span className="material-symbols-outlined">fact_check</span>
            Data Quality Lab
          </NavLink>
          <NavLink
            to="/history"
            className={({ isActive }) =>
              `flex items-center gap-3 px-4 py-3 font-label-md text-label-md rounded-lg transition-colors duration-150 ${isActive
                ? "text-primary font-bold border-r-2 border-primary bg-surface-container-low"
                : "text-on-surface-variant hover:bg-surface-container hover:text-primary"
              }`
            }
          >
            <span className="material-symbols-outlined">history_edu</span>
            Load History
          </NavLink>
        </nav>

        {/* CTA Status */}
        <div className="px-6 py-4">
          <div className="bg-secondary-container text-on-secondary-container rounded-full px-4 py-2 flex items-center justify-center gap-2 text-label-md font-bold">
            <span className="w-2 h-2 bg-emerald-500 rounded-full animate-pulse"></span>
            System Status: Healthy
          </div>
        </div>

        {/* Footer Nav */}
        <div className="mt-auto px-4 pb-6 space-y-1">
          <a href="#" className="flex items-center gap-3 px-4 py-3 font-label-md text-label-md text-on-surface-variant hover:text-primary transition-colors duration-150">
            <span className="material-symbols-outlined">settings</span>
            Settings
          </a>
          <a href="#" className="flex items-center gap-3 px-4 py-3 font-label-md text-label-md text-on-surface-variant hover:text-primary transition-colors duration-150">
            <span className="material-symbols-outlined">help</span>
            Support
          </a>
        </div>
      </div>
    </aside>
  );
};

export default Sidebar;
