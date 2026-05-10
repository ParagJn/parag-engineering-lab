

const TopBar = () => {
  return (
    <header className="fixed top-0 left-[280px] right-0 z-40 bg-surface/80 backdrop-blur-md border-b border-outline-variant h-16 px-container-margin flex items-center justify-between">
      <h2 className="font-headline-sm text-headline-sm font-semibold text-primary">Pipeline Control Center</h2>
      
      <div className="flex items-center gap-6">
        {/* Search Bar */}
        <div className="relative w-64 hidden md:block">
          <span className="material-symbols-outlined absolute left-3 top-1/2 -translate-y-1/2 text-outline text-[20px]">search</span>
          <input 
            type="text" 
            className="w-full pl-10 pr-4 py-2 bg-surface-container-low border border-outline-variant rounded-lg font-body-sm focus:outline-none focus:ring-2 focus:ring-primary/20" 
            placeholder="Search tasks..." 
          />
        </div>

        {/* Quick Actions */}
        <div className="flex items-center gap-4">
          <button 
            onClick={async () => {
              const btn = document.getElementById('sim-btn');
              if (btn) btn.innerHTML = '<span class="material-symbols-outlined text-[18px] animate-spin">refresh</span>Simulating...';
              try {
                await fetch('http://localhost:8000/api/simulate', { method: 'POST' });
                window.dispatchEvent(new CustomEvent('run-simulation'));
                window.dispatchEvent(new CustomEvent('refresh-data'));
              } catch (e) {
                console.error("Simulation failed", e);
              } finally {
                if (btn) btn.innerHTML = '<span class="material-symbols-outlined text-[18px]">play_circle</span>Run-Simulator';
              }
            }}
            id="sim-btn"
            className="flex items-center gap-2 px-4 py-2 bg-primary text-on-primary rounded font-label-md hover:opacity-90 active:scale-95 transition-all"
          >
            <span className="material-symbols-outlined text-[18px]">play_circle</span>
            Run-Simulator
          </button>
          
          <button className="p-2 text-on-surface-variant hover:text-primary transition-colors">
            <span className="material-symbols-outlined">notifications_active</span>
          </button>
          
          <div className="w-8 h-8 rounded-full bg-surface-container-highest overflow-hidden flex items-center justify-center font-bold text-on-surface-variant">
            P
          </div>
        </div>
      </div>
    </header>
  );
};

export default TopBar;
