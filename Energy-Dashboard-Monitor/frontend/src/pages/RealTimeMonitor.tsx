import { useEffect, useRef } from 'react';
import { useSimulation } from '../context/SimulationContext';

const RealTimeMonitor = () => {
  const { simStage, logs, summary } = useSimulation();
  const logsEndRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    logsEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [logs]);

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
        </div>
      </div>

      {/* Simulation Summary - Shows after completion */}
      {summary && simStage === 'idle' && (
        <div className="mt-section-gap bg-gradient-to-br from-emerald-500 to-emerald-600 text-white rounded-xl p-8 shadow-2xl animate-[fadeIn_0.5s_ease-in]">
          <div className="flex items-center gap-3 mb-6">
            <div className="w-12 h-12 bg-white/20 rounded-full flex items-center justify-center">
              <span className="material-symbols-outlined text-3xl">check_circle</span>
            </div>
            <div>
              <h3 className="font-headline-lg text-headline-lg font-bold">ETL Simulation Complete</h3>
              <p className="text-body-sm opacity-90">All datasets processed successfully</p>
            </div>
          </div>

          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6 mb-6">
            {/* Total Records */}
            <div className="bg-white/10 backdrop-blur rounded-lg p-4">
              <p className="text-label-sm opacity-80 mb-1">Total Records</p>
              <p className="font-display-md text-display-md font-bold">{summary.totalRecordsProcessed.toLocaleString()}</p>
            </div>

            {/* Duration */}
            <div className="bg-white/10 backdrop-blur rounded-lg p-4">
              <p className="text-label-sm opacity-80 mb-1">Duration</p>
              <p className="font-display-md text-display-md font-bold">{summary.duration}</p>
            </div>

            {/* Quality Score */}
            <div className="bg-white/10 backdrop-blur rounded-lg p-4">
              <p className="text-label-sm opacity-80 mb-1">Quality Score</p>
              <p className="font-display-md text-display-md font-bold">{summary.qualityScore.toFixed(1)}%</p>
            </div>

            {/* Issues Fixed */}
            <div className="bg-white/10 backdrop-blur rounded-lg p-4">
              <p className="text-label-sm opacity-80 mb-1">Issues Fixed</p>
              <p className="font-display-md text-display-md font-bold">{summary.issuesFixed.toLocaleString()}</p>
            </div>
          </div>

          <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
            {/* Records by Dataset */}
            <div className="bg-white/10 backdrop-blur rounded-lg p-6">
              <h4 className="font-headline-sm font-bold mb-4 flex items-center gap-2">
                <span className="material-symbols-outlined">folder_open</span>
                Records by Dataset
              </h4>
              <div className="space-y-3">
                <div className="flex justify-between items-center">
                  <span className="text-body-sm">Customers</span>
                  <span className="font-mono-data font-bold">{summary.recordsByDataset.customers.toLocaleString()}</span>
                </div>
                <div className="flex justify-between items-center">
                  <span className="text-body-sm">Smart Meters</span>
                  <span className="font-mono-data font-bold">{summary.recordsByDataset.smartMeters.toLocaleString()}</span>
                </div>
                <div className="flex justify-between items-center">
                  <span className="text-body-sm">Meter Readings</span>
                  <span className="font-mono-data font-bold">{summary.recordsByDataset.meterReadings.toLocaleString()}</span>
                </div>
                <div className="flex justify-between items-center">
                  <span className="text-body-sm">Grid Sensors</span>
                  <span className="font-mono-data font-bold">{summary.recordsByDataset.gridSensors.toLocaleString()}</span>
                </div>
                <div className="flex justify-between items-center">
                  <span className="text-body-sm">Sensor Readings</span>
                  <span className="font-mono-data font-bold">{summary.recordsByDataset.sensorReadings.toLocaleString()}</span>
                </div>
                <div className="flex justify-between items-center">
                  <span className="text-body-sm">Billing Records</span>
                  <span className="font-mono-data font-bold">{summary.recordsByDataset.billingRecords.toLocaleString()}</span>
                </div>
                <div className="flex justify-between items-center">
                  <span className="text-body-sm">Weather Data</span>
                  <span className="font-mono-data font-bold">{summary.recordsByDataset.weatherData.toLocaleString()}</span>
                </div>
              </div>
            </div>

            {/* Data Quality Issues */}
            <div className="bg-white/10 backdrop-blur rounded-lg p-6">
              <h4 className="font-headline-sm font-bold mb-4 flex items-center gap-2">
                <span className="material-symbols-outlined">bug_report</span>
                Data Quality Issues
              </h4>
              <div className="space-y-4">
                <div>
                  <div className="flex justify-between items-center mb-2">
                    <span className="text-body-sm">NULL Values</span>
                    <span className="font-mono-data font-bold">{summary.issuesFound.nulls.toLocaleString()}</span>
                  </div>
                  <div className="w-full bg-white/20 h-2 rounded-full overflow-hidden">
                    <div
                      className="h-full bg-white rounded-full"
                      style={{ width: `${Math.min(100, (summary.issuesFound.nulls / 1000) * 100)}%` }}
                    ></div>
                  </div>
                </div>

                <div>
                  <div className="flex justify-between items-center mb-2">
                    <span className="text-body-sm">Outliers</span>
                    <span className="font-mono-data font-bold">{summary.issuesFound.outliers.toLocaleString()}</span>
                  </div>
                  <div className="w-full bg-white/20 h-2 rounded-full overflow-hidden">
                    <div
                      className="h-full bg-white rounded-full"
                      style={{ width: `${Math.min(100, (summary.issuesFound.outliers / 1000) * 100)}%` }}
                    ></div>
                  </div>
                </div>

                <div>
                  <div className="flex justify-between items-center mb-2">
                    <span className="text-body-sm">Schema Mismatches</span>
                    <span className="font-mono-data font-bold">{summary.issuesFound.schemaMismatch.toLocaleString()}</span>
                  </div>
                  <div className="w-full bg-white/20 h-2 rounded-full overflow-hidden">
                    <div
                      className="h-full bg-white rounded-full"
                      style={{ width: `${Math.min(100, (summary.issuesFound.schemaMismatch / 500) * 100)}%` }}
                    ></div>
                  </div>
                </div>

                <div className="pt-4 border-t border-white/20">
                  <div className="flex justify-between items-center">
                    <span className="text-body-md font-bold">Total Issues</span>
                    <span className="font-display-sm font-bold">
                      {(summary.issuesFound.nulls + summary.issuesFound.outliers + summary.issuesFound.schemaMismatch).toLocaleString()}
                    </span>
                  </div>
                </div>
              </div>
            </div>
          </div>

          <div className="mt-6 flex justify-center">
            <button
              onClick={() => window.location.href = '/quality'}
              className="bg-white text-emerald-600 px-6 py-3 rounded-lg font-bold hover:bg-white/90 transition-all flex items-center gap-2"
            >
              <span className="material-symbols-outlined">analytics</span>
              View Detailed Quality Report
            </button>
          </div>
        </div>
      )}
      
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
