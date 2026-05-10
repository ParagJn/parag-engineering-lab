import { useEffect, useState, useRef } from 'react';

const RealTimeMonitor = () => {
  const [simStage, setSimStage] = useState('idle');
  const [logs, setLogs] = useState<string[]>([
    "[14:22:01] INFO: Initializing cleansing sequence for bucket_882",
    "[14:22:03] WARN: Duplicate entries detected in set 04 (auto-merged)",
    "[14:22:05] INFO: Applying schema transformation ruleset v2.4.1",
    "SUCCESS: Batch 091 verified and ready for Lakehouse export"
  ]);
  const logsEndRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    logsEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [logs]);

  useEffect(() => {
    const handleSimulate = () => {
      if (simStage !== 'idle') return;
      
      setSimStage('acquisition');
      setLogs(["[SIM] INFO: Simulator started. Acquiring streaming data..."]);
      
      // Delays to simulate production cycle load
      setTimeout(() => {
        setSimStage('validation');
        setLogs(prev => [...prev, "[SIM] INFO: 10,000 records acquired. Starting validation..."]);
      }, 2500);

      setTimeout(() => {
        setSimStage('cleansing');
        setLogs(prev => [...prev, "[SIM] WARN: Found 124 outliers. Initiating cleansing protocols..."]);
      }, 5500);

      setTimeout(() => {
        setLogs(prev => [...prev, "[SIM] INFO: Applying custom interpolation for null values..."]);
      }, 7000);

      setTimeout(() => {
        setSimStage('transformation');
        setLogs(prev => [...prev, "[SIM] INFO: Cleansing complete. Transforming schema for Lakehouse..."]);
      }, 9500);

      setTimeout(() => {
        setSimStage('lakehouse');
        setLogs(prev => [...prev, "[SIM] INFO: Transformations successful. Loading to Lakehouse..."]);
      }, 12500);

      setTimeout(() => {
        setSimStage('idle');
        setLogs(prev => [...prev, "[SIM] SUCCESS: Cycle complete. Pipeline idle."]);
      }, 15000);
    };

    window.addEventListener('run-simulation', handleSimulate);
    return () => window.removeEventListener('run-simulation', handleSimulate);
  }, [simStage]);

  // Helpers for stage styling
  const getStageClass = (stage: string, isActive: boolean, isPast: boolean) => {
    void stage;
    if (isActive) return "bg-emerald-500 text-white pipeline-pulse shadow-lg ring-4 ring-emerald-100 border-2 border-emerald-500 scale-110 transition-all";
    if (isPast) return "bg-primary text-on-primary ring-4 ring-white transition-all";
    return "bg-white border-2 border-outline-variant text-outline ring-4 ring-white transition-all";
  };

  const getConnectorClass = (isActive: boolean, isPast: boolean) => {
    if (isActive) return "bg-emerald-500 relative overflow-hidden";
    if (isPast) return "bg-primary";
    return "bg-outline-variant";
  };

  const stageOrder = ['idle', 'acquisition', 'validation', 'cleansing', 'transformation', 'lakehouse'];
  const currentIndex = stageOrder.indexOf(simStage);

  const getStageStatus = (stage: string) => {
    const idx = stageOrder.indexOf(stage);
    if (currentIndex === idx && simStage !== 'idle') return { label: 'Active', class: 'bg-emerald-100 text-emerald-800' };
    if (currentIndex > idx || simStage === 'idle') return { label: 'Done', class: 'bg-surface-container text-on-surface-variant' };
    return { label: 'Pending', class: 'bg-surface-container text-on-surface-variant opacity-50' };
  };

  return (
    <div className="pb-12">
      {/* Real-Time Stats Overview */}
      <div className="grid grid-cols-1 md:grid-cols-4 gap-gutter mb-section-gap">
        <div className="bg-surface border border-outline-variant p-card-padding rounded-xl shadow-sm">
          <p className="font-label-md text-label-md text-on-surface-variant mb-1">Active Streams</p>
          <h3 className="font-headline-md text-headline-md font-bold text-primary">{simStage !== 'idle' ? '28' : '24'}</h3>
          <div className="flex items-center gap-1 text-emerald-600 mt-2">
            <span className="material-symbols-outlined text-[16px]">trending_up</span>
            <span className="font-label-sm text-label-sm">{simStage !== 'idle' ? '+4 from last minute' : '+3 from last hour'}</span>
          </div>
        </div>
        
        <div className="bg-surface border border-outline-variant p-card-padding rounded-xl shadow-sm text-primary">
          <p className="font-label-md text-label-md text-on-surface-variant mb-1">Throughput</p>
          <h3 className="font-headline-md text-headline-md font-bold">{simStage !== 'idle' ? '4.8 GB/s' : '1.2 GB/s'}</h3>
          <div className="w-full bg-surface-container h-1 rounded-full mt-4 overflow-hidden">
            <div className={`h-full transition-all duration-1000 ${simStage !== 'idle' ? 'bg-emerald-500 w-[95%]' : 'bg-primary w-[65%]'}`}></div>
          </div>
        </div>
        
        <div className="bg-surface border border-outline-variant p-card-padding rounded-xl shadow-sm">
          <p className="font-label-md text-label-md text-on-surface-variant mb-1">Avg. Latency</p>
          <h3 className="font-headline-md text-headline-md font-bold text-primary">{simStage !== 'idle' ? '214 ms' : '842 ms'}</h3>
          <p className="font-label-sm text-label-sm text-on-surface-variant mt-2">Nominal Performance</p>
        </div>
        
        <div className="bg-surface border border-outline-variant p-card-padding rounded-xl shadow-sm">
          <p className="font-label-md text-label-md text-on-surface-variant mb-1">Error Rate</p>
          <h3 className="font-headline-md text-headline-md font-bold text-error">0.02%</h3>
          <p className="font-label-sm text-label-sm text-on-surface-variant mt-2">Last 5 minutes</p>
        </div>
      </div>

      {/* Pipeline Visualization Canvas */}
      <div className="relative bg-surface border border-outline-variant rounded-xl p-8 mb-section-gap overflow-hidden">
        <div className="flex flex-col md:flex-row md:items-center justify-between mb-12 gap-4">
          <div>
            <h4 className="font-headline-sm text-headline-sm font-bold text-primary">ETL Processing Flow</h4>
            <p className="font-body-sm text-body-sm text-on-surface-variant">Live visual representation of active data packets across nodes</p>
          </div>
          <div className="flex gap-4">
            <div className="flex items-center gap-2 font-label-sm text-label-sm">
              <span className="w-3 h-3 rounded-full bg-emerald-500"></span> Active
            </div>
            <div className="flex items-center gap-2 font-label-sm text-label-sm">
              <span className="w-3 h-3 rounded-full bg-primary-fixed border border-primary/20"></span> Queued
            </div>
          </div>
        </div>

        {/* Pipeline Stages Flow */}
        <div className="relative flex flex-col md:flex-row items-center justify-between gap-8 md:gap-0 my-8">
          {/* Flow Line Background (Desktop only) */}
          <div className="hidden md:block absolute top-8 left-0 w-full h-[2px] bg-outline-variant z-0"></div>

          {/* Stage: Acquisition */}
          <div className="relative z-10 flex flex-col items-center">
            <div className={`w-16 h-16 rounded-full flex items-center justify-center ${getStageClass('acquisition', simStage === 'acquisition', currentIndex > 1 || simStage === 'idle')}`}>
              <span className="material-symbols-outlined text-[32px]">cloud_download</span>
            </div>
            <div className="mt-4 text-center">
              <p className="font-label-md text-label-md font-bold">Acquisition</p>
              <p className="font-mono-data text-label-sm text-on-surface-variant">120ms</p>
              <span className={`inline-block mt-2 px-2 py-1 text-[10px] rounded font-bold uppercase ${getStageStatus('acquisition').class}`}>{getStageStatus('acquisition').label}</span>
            </div>
          </div>

          {/* Connector 1 */}
          <div className="hidden md:flex flex-1 justify-center relative -top-6">
            <div className={`w-12 h-1 rounded-full ${getConnectorClass(simStage === 'acquisition', currentIndex > 1 || simStage === 'idle')}`}>
              {simStage === 'acquisition' && <div className="absolute inset-0 bg-white/40 animate-[pulse_1.5s_linear_infinite]"></div>}
            </div>
          </div>

          {/* Stage: Validation */}
          <div className="relative z-10 flex flex-col items-center">
            <div className={`w-16 h-16 rounded-full flex items-center justify-center ${getStageClass('validation', simStage === 'validation', currentIndex > 2 || simStage === 'idle')}`}>
              <span className="material-symbols-outlined text-[32px]">verified_user</span>
            </div>
            <div className="mt-4 text-center">
              <p className="font-label-md text-label-md font-bold">Validation</p>
              <p className="font-mono-data text-label-sm text-on-surface-variant">215ms</p>
              <span className={`inline-block mt-2 px-2 py-1 text-[10px] rounded font-bold uppercase ${getStageStatus('validation').class}`}>{getStageStatus('validation').label}</span>
            </div>
          </div>

          {/* Connector 2 */}
          <div className="hidden md:flex flex-1 justify-center relative -top-6">
            <div className={`w-12 h-1 rounded-full ${getConnectorClass(simStage === 'validation', currentIndex > 2 || simStage === 'idle')}`}>
              {simStage === 'validation' && <div className="absolute inset-0 bg-white/40 animate-[pulse_1.5s_linear_infinite]"></div>}
            </div>
          </div>

          {/* Stage: Cleansing */}
          <div className="relative z-10 flex flex-col items-center">
            <div className={`w-20 h-20 rounded-full flex items-center justify-center ${getStageClass('cleansing', simStage === 'cleansing', currentIndex > 3 || simStage === 'idle')}`}>
              <span className="material-symbols-outlined text-[40px]">auto_fix_high</span>
            </div>
            <div className="mt-4 text-center">
              <p className="font-label-md text-label-md font-bold text-primary">Cleansing</p>
              <p className="font-mono-data text-label-sm text-primary">450ms</p>
              <span className={`inline-block mt-2 px-2 py-1 text-[10px] rounded font-bold uppercase ${getStageStatus('cleansing').class}`}>{getStageStatus('cleansing').label}</span>
            </div>
          </div>

          {/* Connector 3 */}
          <div className="hidden md:flex flex-1 justify-center relative -top-6">
            <div className={`w-12 h-1 rounded-full ${getConnectorClass(simStage === 'cleansing', currentIndex > 3 || simStage === 'idle')}`}>
              {simStage === 'cleansing' && <div className="absolute inset-0 bg-white/40 animate-[pulse_1.5s_linear_infinite]"></div>}
            </div>
          </div>

          {/* Stage: Transformation */}
          <div className={`relative z-10 flex flex-col items-center ${(currentIndex < 4 && simStage !== 'idle') ? 'opacity-60' : ''}`}>
            <div className={`w-16 h-16 rounded-full flex items-center justify-center ${getStageClass('transformation', simStage === 'transformation', currentIndex > 4 || simStage === 'idle')}`}>
              <span className="material-symbols-outlined text-[32px]">transform</span>
            </div>
            <div className="mt-4 text-center">
              <p className="font-label-md text-label-md font-bold">Transformation</p>
              <p className="font-mono-data text-label-sm text-on-surface-variant">280ms</p>
              <span className={`inline-block mt-2 px-2 py-1 text-[10px] rounded font-bold uppercase ${getStageStatus('transformation').class}`}>{getStageStatus('transformation').label}</span>
            </div>
          </div>

          {/* Connector 4 */}
          <div className="hidden md:flex flex-1 justify-center relative -top-6">
            <div className={`w-12 h-1 rounded-full ${getConnectorClass(simStage === 'transformation', currentIndex > 4 || simStage === 'idle')}`}>
              {simStage === 'transformation' && <div className="absolute inset-0 bg-white/40 animate-[pulse_1.5s_linear_infinite]"></div>}
            </div>
          </div>

          {/* Stage: Lakehouse Load */}
          <div className={`relative z-10 flex flex-col items-center ${(currentIndex < 5 && simStage !== 'idle') ? 'opacity-40' : ''}`}>
            <div className={`w-16 h-16 rounded-full flex items-center justify-center ${getStageClass('lakehouse', simStage === 'lakehouse', simStage === 'idle')}`}>
              <span className="material-symbols-outlined text-[32px]">database</span>
            </div>
            <div className="mt-4 text-center">
              <p className="font-label-md text-label-md font-bold">Lakehouse Load</p>
              <p className="font-mono-data text-label-sm text-on-surface-variant">Idle</p>
              <span className={`inline-block mt-2 px-2 py-1 text-[10px] rounded font-bold uppercase ${getStageStatus('lakehouse').class}`}>{getStageStatus('lakehouse').label}</span>
            </div>
          </div>
        </div>
      </div>

      {/* Detail Grid Layout */}
      <div className="grid grid-cols-1 xl:grid-cols-3 gap-gutter">
        {/* Selected Stage Details */}
        <div className="xl:col-span-2 space-y-gutter">
          <div className={`bg-surface border border-outline-variant rounded-xl overflow-hidden shadow-sm transition-colors duration-500 ${simStage === 'cleansing' ? 'ring-2 ring-emerald-500' : ''}`}>
            <div className="bg-surface-container-low px-6 py-4 border-b border-outline-variant flex items-center justify-between">
              <div className="flex items-center gap-3">
                <span className={`material-symbols-outlined ${simStage === 'cleansing' ? 'text-emerald-500 pipeline-pulse' : 'text-primary'}`}>terminal</span>
                <h5 className="font-headline-sm text-headline-sm font-bold">Cleansing Stage Detail</h5>
              </div>
              <span className={`font-label-sm text-label-sm px-3 py-1 rounded-full font-bold transition-colors ${simStage === 'cleansing' ? 'bg-emerald-500 text-white' : 'bg-surface-container-highest text-on-surface-variant'}`}>
                {simStage === 'cleansing' ? 'ACTIVE' : 'STANDBY'}
              </span>
            </div>
            
            <div className="p-card-padding">
              <div className="grid grid-cols-1 md:grid-cols-2 gap-8 mb-8">
                <div className="space-y-6">
                  <div>
                    <p className="font-label-sm text-label-sm text-on-surface-variant uppercase tracking-wider">Worker Threads</p>
                    <div className="flex items-center gap-4 mt-2">
                      <div className="flex -space-x-2">
                        <div className={`w-8 h-8 rounded-full border-2 border-white flex items-center justify-center text-[10px] text-white z-30 transition-colors ${simStage === 'cleansing' ? 'bg-emerald-500' : 'bg-primary'}`}>01</div>
                        <div className={`w-8 h-8 rounded-full border-2 border-white flex items-center justify-center text-[10px] text-white z-20 transition-colors ${simStage === 'cleansing' ? 'bg-emerald-500' : 'bg-primary'}`}>02</div>
                        <div className={`w-8 h-8 rounded-full border-2 border-white flex items-center justify-center text-[10px] text-white z-10 transition-colors ${simStage === 'cleansing' ? 'bg-emerald-500' : 'bg-primary'}`}>03</div>
                        <div className="w-8 h-8 rounded-full bg-surface-container-highest border-2 border-white flex items-center justify-center text-[10px] text-on-surface-variant z-0">+8</div>
                      </div>
                      <p className="text-body-sm font-semibold">{simStage === 'cleansing' ? '24 Active' : '11 Active'}</p>
                    </div>
                  </div>
                  <div>
                    <p className="font-label-sm text-label-sm text-on-surface-variant uppercase tracking-wider">Prefect Task Status</p>
                    <p className="font-body-md mt-1 font-bold text-primary">Flow ID: px-882-cleaning-prod</p>
                    <div className="flex items-center gap-2 mt-2">
                      <span className={`w-2 h-2 rounded-full ${simStage === 'cleansing' ? 'bg-emerald-500 animate-pulse' : 'bg-outline-variant'}`}></span>
                      <span className="text-label-md">{simStage === 'cleansing' ? 'Processing stream batch' : 'Heartbeat nominal'}</span>
                    </div>
                  </div>
                </div>
                
                <div className="bg-surface-container-low rounded-lg p-4">
                  <p className="font-label-sm text-label-sm text-on-surface-variant mb-3">Resource Utilization</p>
                  <div className="space-y-4">
                    <div>
                      <div className="flex justify-between text-label-sm mb-1">
                        <span>CPU Load</span>
                        <span className="font-mono-data transition-all duration-1000">{simStage === 'cleansing' ? '89%' : '42%'}</span>
                      </div>
                      <div className="w-full bg-surface-container h-1.5 rounded-full overflow-hidden">
                        <div className={`h-full rounded-full transition-all duration-1000 ${simStage === 'cleansing' ? 'bg-emerald-500 w-[89%]' : 'bg-secondary w-[42%]'}`}></div>
                      </div>
                    </div>
                    <div>
                      <div className="flex justify-between text-label-sm mb-1">
                        <span>Memory Usage</span>
                        <span className="font-mono-data transition-all duration-1000">{simStage === 'cleansing' ? '12.4 GB' : '6.8 GB'}</span>
                      </div>
                      <div className="w-full bg-surface-container h-1.5 rounded-full overflow-hidden">
                        <div className={`h-full rounded-full transition-all duration-1000 ${simStage === 'cleansing' ? 'bg-error w-[92%]' : 'bg-secondary w-[78%]'}`}></div>
                      </div>
                    </div>
                  </div>
                </div>
              </div>
              
              {/* Mini Log Console */}
              <div className="bg-primary text-primary-fixed-dim rounded-lg p-4 font-mono-data text-[13px] leading-relaxed max-h-48 overflow-y-auto">
                {logs.map((log, idx) => (
                  <p key={idx} className={`${log.includes('SUCCESS') ? 'text-emerald-400' : log.includes('WARN') ? 'text-amber-400' : ''}`}>
                    {!log.includes('SUCCESS') && !log.includes('WARN') && <span className="text-secondary-fixed opacity-70">[{new Date().toLocaleTimeString('en-US', { hour12: false })}] </span>}
                    {log}
                  </p>
                ))}
                <div ref={logsEndRef} />
              </div>
            </div>
          </div>
        </div>

        {/* Recent Anomalies / Sidebar Panel */}
        <div className="space-y-gutter mt-8 xl:mt-0">
          <div className="bg-surface border border-outline-variant rounded-xl p-card-padding shadow-sm">
            <div className="flex items-center justify-between mb-6">
              <h5 className="font-headline-sm text-headline-sm font-bold">Node Health</h5>
              <button className="text-primary font-label-sm hover:underline">View All</button>
            </div>
            <div className="space-y-4">
              <div className="flex items-start gap-3 p-3 rounded-lg border border-outline-variant">
                <div className="w-8 h-8 rounded bg-emerald-100 flex items-center justify-center shrink-0">
                  <span className="material-symbols-outlined text-emerald-600">check_circle</span>
                </div>
                <div>
                  <p className="font-label-md font-bold">US-East-1 (Primary)</p>
                  <p className="text-label-sm text-on-surface-variant">Latency: {simStage !== 'idle' ? '24ms' : '12ms'} | Load: {simStage !== 'idle' ? '85%' : '12%'}</p>
                </div>
              </div>
              
              <div className="flex items-start gap-3 p-3 rounded-lg border border-outline-variant">
                <div className="w-8 h-8 rounded bg-emerald-100 flex items-center justify-center shrink-0">
                  <span className="material-symbols-outlined text-emerald-600">check_circle</span>
                </div>
                <div>
                  <p className="font-label-md font-bold">US-West-2 (Secondary)</p>
                  <p className="text-label-sm text-on-surface-variant">Latency: {simStage !== 'idle' ? '68ms' : '45ms'} | Load: {simStage !== 'idle' ? '42%' : '8%'}</p>
                </div>
              </div>
              
              <div className="flex items-start gap-3 p-3 rounded-lg border border-error-container bg-error-container/10">
                <div className="w-8 h-8 rounded bg-error-container flex items-center justify-center shrink-0">
                  <span className="material-symbols-outlined text-error">warning</span>
                </div>
                <div>
                  <p className="font-label-md font-bold text-error">EU-Central-1 (Backup)</p>
                  <p className="text-label-sm text-on-error-container">Sync Lag: 4.2s | Retrying...</p>
                </div>
              </div>
            </div>
          </div>

          <div className="bg-primary text-on-primary rounded-xl p-card-padding shadow-lg relative overflow-hidden">
            <div className="relative z-10">
              <h6 className="font-headline-sm font-bold mb-2">Performance Optimization</h6>
              <p className="text-body-sm opacity-80 mb-6">Automated node scaling is currently managing {simStage !== 'idle' ? '12' : '4'} on-demand instances to handle peak morning load.</p>
              <button className="w-full bg-white text-primary py-3 rounded-lg font-bold hover:bg-white/90 transition-all">View Scaling Logs</button>
            </div>
            {/* Abstract overlay */}
            <div className="absolute -right-12 -bottom-12 w-48 h-48 bg-white opacity-5 rounded-full"></div>
          </div>
        </div>
      </div>
      
      {/* Floating Action for Alert */}
      <div className="fixed bottom-8 right-8 z-50">
        <button className="bg-error text-white h-14 w-14 rounded-full shadow-2xl flex items-center justify-center hover:scale-110 active:scale-95 transition-transform">
          <span className="material-symbols-outlined" style={{ fontVariationSettings: "'FILL' 1" }}>report</span>
        </button>
      </div>
    </div>
  );
};

export default RealTimeMonitor;
