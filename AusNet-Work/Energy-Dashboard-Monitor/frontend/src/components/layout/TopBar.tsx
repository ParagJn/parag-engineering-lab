import { useSimulation } from '../../context/SimulationContext';

const TopBar = () => {
  const { triggerSimulation, simStage } = useSimulation();

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
              if (simStage !== 'idle') return;
              await triggerSimulation();
            }}
            id="sim-btn"
            disabled={simStage !== 'idle'}
            className={`flex items-center gap-2 px-4 py-2 text-on-primary rounded font-label-md transition-all ${simStage !== 'idle' ? 'bg-primary/50 cursor-not-allowed' : 'bg-primary hover:opacity-90 active:scale-95'}`}
          >
            {simStage !== 'idle' ? (
              <><span className="material-symbols-outlined text-[18px] animate-spin">refresh</span>Simulating...</>
            ) : (
              <><span className="material-symbols-outlined text-[18px]">play_circle</span>Run-ETL Pipeline</>
            )}
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
