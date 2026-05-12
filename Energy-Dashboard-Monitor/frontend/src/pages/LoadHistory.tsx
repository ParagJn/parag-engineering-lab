import { useEffect, useState } from 'react';
import axios from 'axios';

const API_URL = '/api';

const LoadHistory = () => {
  const [data, setData] = useState<any>(null);
  const [currentPage, setCurrentPage] = useState(1);
  const [chartView, setChartView] = useState<'volume' | 'quality'>('volume');
  const itemsPerPage = 5;

  const exportLogs = () => {
    if (!data?.logs || data.logs.length === 0) return;
    const header = "Run ID,Target Pipeline,Status,Volume,Errors,Duration,Timestamp\n";
    const csvContent = data.logs.map((l: any) => 
      `"${l.id}","${l.target}","${l.status}","${l.volume}","${l.errors}","${l.duration}","${l.timestamp}"`
    ).join("\n");
    
    const blob = new Blob([header + csvContent], { type: 'text/csv;charset=utf-8;' });
    const url = URL.createObjectURL(blob);
    const link = document.createElement('a');
    link.href = url;
    link.setAttribute('download', 'load_history_export.csv');
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);
  };

  const fetchData = () => {
    axios.get(`${API_URL}/history`).then(res => setData(res.data)).catch(console.error);
  };

  useEffect(() => {
    fetchData();
    window.addEventListener('refresh-data', fetchData);
    return () => window.removeEventListener('refresh-data', fetchData);
  }, []);

  const getStatusClass = (status: string) => {
    if (status === 'Completed') return 'text-emerald-600 bg-emerald-100';
    if (status === 'Warning') return 'text-amber-600 bg-amber-100';
    return 'text-error bg-error-container';
  };

  const getRowClass = (status: string) => {
    if (status === 'Warning') return 'bg-tertiary-container/10 hover:bg-tertiary-container/20 border-l-4 border-tertiary-container';
    if (status === 'Failed') return 'bg-error-container/20 hover:bg-error-container/30 border-l-4 border-error';
    return 'hover:bg-surface-container-lowest';
  };

  const totalRuns = (data?.orchestration?.completed || 0) + (data?.orchestration?.failed || 0) + (data?.orchestration?.retrying || 0);
  const uptime = totalRuns > 0 ? ((data?.orchestration?.completed || 0) / totalRuns * 100).toFixed(1) : 100;

  const logsList = data?.logs || [];
  const totalPages = Math.max(1, Math.ceil(logsList.length / itemsPerPage));
  const currentLogs = logsList.slice((currentPage - 1) * itemsPerPage, currentPage * itemsPerPage);

  return (
    <div className="pb-12">
      {/* Action Header */}
      <div className="flex flex-col md:flex-row justify-between items-start md:items-end mb-section-gap gap-4">
        <div>
          <h3 className="font-headline-md text-headline-md text-primary mb-1">Load History</h3>
          <p className="font-body-md text-on-surface-variant">Historical performance for the Lakehouse database loads.</p>
        </div>
        <div className="flex gap-3">
          <button onClick={exportLogs} className="px-4 py-2 bg-surface-container-low border border-outline-variant text-primary rounded-lg text-sm font-medium hover:bg-surface-container transition-colors flex items-center gap-2">
            <span className="material-symbols-outlined text-sm">file_download</span>
            Export Logs
          </button>
          <button onClick={fetchData} className="px-4 py-2 bg-primary text-white rounded-lg text-sm font-medium hover:bg-primary/90 transition-colors flex items-center gap-2">
            <span className="material-symbols-outlined text-sm">refresh</span>
            Refresh Data
          </button>
        </div>
      </div>

      {/* Bento Grid Layout */}
      <div className="grid grid-cols-12 gap-gutter mb-section-gap">
        {/* Time-Series Chart Area */}
        <div className="col-span-12 lg:col-span-8 bg-surface/70 backdrop-blur border border-outline-variant rounded-xl p-card-padding shadow-sm">
          <div className="flex flex-col sm:flex-row justify-between sm:items-center mb-8 gap-4">
            <div>
              <h3 className="font-headline-sm text-headline-sm text-primary">Volume Trends</h3>
              <p className="font-label-sm text-label-sm text-on-surface-variant">Records processed per pipeline run (last 10)</p>
            </div>
            <div className="flex gap-2">
              <button
                onClick={() => setChartView('volume')}
                className={`px-3 py-1 rounded text-xs font-medium transition-colors ${
                  chartView === 'volume'
                    ? 'bg-surface-container border border-outline-variant text-primary'
                    : 'text-on-surface-variant hover:bg-surface-container border border-transparent'
                }`}
              >
                Per Run
              </button>
              <button
                onClick={() => setChartView('quality')}
                className={`px-3 py-1 rounded text-xs font-medium transition-colors ${
                  chartView === 'quality'
                    ? 'bg-surface-container border border-outline-variant text-primary'
                    : 'text-on-surface-variant hover:bg-surface-container border border-transparent'
                }`}
              >
                Quality
              </button>
            </div>
          </div>
          
          {/* Dynamic Bar Chart — bound to real pipeline_runs snapshots */}
          <div className="relative h-64 w-full bg-surface-container-lowest rounded-lg border border-outline-variant/30 p-4 overflow-hidden">
            {(() => {
              const runs: any[] = data?.pipeline_runs || [];
              if (runs.length === 0) {
                return (
                  <div className="absolute inset-0 flex flex-col items-center justify-center gap-2 text-on-surface-variant">
                    <span className="material-symbols-outlined text-4xl opacity-30">bar_chart</span>
                    <p className="text-sm font-medium">No runs yet</p>
                    <p className="text-xs opacity-70">Run a simulation to populate this chart</p>
                  </div>
                );
              }
              
              // Determine what to display based on chartView
              const maxValue = chartView === 'volume'
                ? Math.max(...runs.map((r: any) => r.records_processed ?? 0))
                : 100; // Quality is percentage
              
              const yAxisLabel = chartView === 'volume' ? 'Records' : 'Quality %';
              
              return (
                <>
                  {/* Y-axis gridlines */}
                  <div className="absolute inset-0 flex flex-col justify-between py-4 px-10 pointer-events-none">
                    <div className="w-full border-t border-outline-variant/20 text-[10px] text-outline pt-1">
                      {chartView === 'volume' ? maxValue.toLocaleString() : '100%'}
                    </div>
                    <div className="w-full border-t border-outline-variant/20 text-[10px] text-outline pt-1">
                      {chartView === 'volume' ? Math.round(maxValue / 2).toLocaleString() : '50%'}
                    </div>
                    <div className="w-full border-t border-outline-variant/20 text-[10px] text-outline pt-1">
                      {chartView === 'volume' ? '0' : '0%'}
                    </div>
                  </div>
                  {/* Bars */}
                  <div className="relative h-full flex items-end justify-around gap-1 px-2 pt-2 pb-5">
                    {runs.map((run: any, i: number) => {
                      const isLatest = i === runs.length - 1;
                      
                      // Calculate height based on view
                      let heightPct: number;
                      let displayValue: string;
                      let barColor: string;
                      
                      if (chartView === 'volume') {
                        heightPct = maxValue > 0 ? Math.max(4, (run.records_processed / maxValue) * 90) : 4;
                        displayValue = `${run.records_processed?.toLocaleString()} rec`;
                        barColor = isLatest ? 'bg-primary' : 'bg-primary/35 group-hover:bg-primary/55';
                      } else {
                        // Quality view - use quality_score from run
                        const quality = run.quality_score ?? 85; // Default to 85% if not available
                        heightPct = Math.max(4, (quality / 100) * 90);
                        displayValue = `${quality.toFixed(1)}%`;
                        
                        // Color based on quality
                        if (quality >= 95) {
                          barColor = isLatest ? 'bg-emerald-500' : 'bg-emerald-500/35 group-hover:bg-emerald-500/55';
                        } else if (quality >= 85) {
                          barColor = isLatest ? 'bg-amber-500' : 'bg-amber-500/35 group-hover:bg-amber-500/55';
                        } else {
                          barColor = isLatest ? 'bg-error' : 'bg-error/35 group-hover:bg-error/55';
                        }
                      }
                      
                      const label = new Date(run.timestamp).toLocaleTimeString('en-US', { hour: '2-digit', minute: '2-digit', hour12: false });
                      
                      return (
                        <div key={i} className="relative flex flex-col items-center gap-0.5 flex-1 h-full justify-end group">
                          <div
                            className={`w-full rounded-t-md transition-all duration-700 ${barColor}`}
                            style={{ height: `${heightPct}%` }}
                          />
                          {isLatest && (
                            <div className="absolute -top-9 left-1/2 -translate-x-1/2 bg-surface/95 backdrop-blur border border-outline-variant rounded shadow-lg px-2 py-1 flex items-center gap-1.5 whitespace-nowrap z-10">
                              <div className="w-1.5 h-1.5 rounded-full bg-primary animate-pulse" />
                              <span className="text-[10px] font-bold">{displayValue}</span>
                            </div>
                          )}
                          <span className="absolute bottom-0 text-[9px] text-on-surface-variant truncate max-w-full">{label}</span>
                        </div>
                      );
                    })}
                  </div>
                </>
              );
            })()}
          </div>
        </div>


        {/* Orchestration Pie Chart */}
        <div className="col-span-12 lg:col-span-4 bg-surface/70 backdrop-blur border border-outline-variant rounded-xl p-card-padding shadow-sm flex flex-col">
          <h3 className="font-headline-sm text-headline-sm text-primary mb-1">Orchestration Health</h3>
          <p className="font-label-sm text-label-sm text-on-surface-variant mb-6">Overall Run Success vs Failure</p>
          <div className="flex-1 flex flex-col items-center justify-center relative">
            <div className="w-40 h-40 rounded-full border-[16px] border-emerald-500 relative flex items-center justify-center">
              <div className="absolute inset-[-16px] rounded-full border-[16px] border-error border-l-transparent border-t-transparent border-b-transparent transform rotate-[45deg]" style={{ opacity: data?.orchestration?.failed > 0 ? 1 : 0 }}></div>
              <div className="text-center">
                <span className="block font-display-lg text-display-lg text-primary">{uptime}%</span>
                <span className="text-[10px] uppercase tracking-widest text-on-surface-variant font-bold">Uptime</span>
              </div>
            </div>
            <div className="mt-8 w-full space-y-3">
              <div className="flex items-center justify-between">
                <div className="flex items-center gap-2">
                  <span className="w-3 h-3 rounded-sm bg-emerald-500"></span>
                  <span className="text-sm font-medium">Successful Runs</span>
                </div>
                <span className="font-mono-data text-mono-data font-bold text-on-surface">{data?.orchestration?.completed || 0}</span>
              </div>
              <div className="flex items-center justify-between">
                <div className="flex items-center gap-2">
                  <span className="w-3 h-3 rounded-sm bg-error"></span>
                  <span className="text-sm font-medium text-on-surface">Critical Failures</span>
                </div>
                <span className="font-mono-data text-mono-data font-bold text-error">{data?.orchestration?.failed || 0}</span>
              </div>
              <div className="flex items-center justify-between">
                <div className="flex items-center gap-2">
                  <span className="w-3 h-3 rounded-sm bg-tertiary-fixed"></span>
                  <span className="text-sm font-medium text-on-surface">Warnings/Retries</span>
                </div>
                <span className="font-mono-data text-mono-data font-bold text-on-surface">{data?.orchestration?.retrying || 0}</span>
              </div>
            </div>
          </div>
        </div>
      </div>

      {/* Historical Log Table */}
      <div className="bg-surface/70 backdrop-blur border border-outline-variant rounded-xl overflow-hidden shadow-sm">
        <div className="px-card-padding py-5 border-b border-outline-variant flex justify-between items-center bg-surface-container-lowest">
          <h3 className="font-headline-sm text-headline-sm text-primary">Detailed Historical Log</h3>
          <div className="flex items-center gap-4">
            <div className="flex items-center border border-outline-variant rounded overflow-hidden">
              <button className="p-1.5 hover:bg-surface-container bg-surface flex items-center justify-center">
                <span className="material-symbols-outlined text-sm">filter_list</span>
              </button>
              <button className="p-1.5 border-l border-outline-variant hover:bg-surface-container bg-surface flex items-center justify-center">
                <span className="material-symbols-outlined text-sm">sort</span>
              </button>
            </div>
          </div>
        </div>
        
        <div className="overflow-x-auto">
          <table className="w-full text-left">
            <thead className="bg-surface-container-low border-b border-outline-variant">
              <tr>
                <th className="px-6 py-4 font-label-md text-label-md text-on-surface-variant uppercase tracking-wider">Date & Time</th>
                <th className="px-6 py-4 font-label-md text-label-md text-on-surface-variant uppercase tracking-wider">Source Engine</th>
                <th className="px-6 py-4 font-label-md text-label-md text-on-surface-variant uppercase tracking-wider">Records Loaded</th>
                <th className="px-6 py-4 font-label-md text-label-md text-on-surface-variant uppercase tracking-wider">Status</th>
                <th className="px-6 py-4 font-label-md text-label-md text-on-surface-variant uppercase tracking-wider">Errors/Duration</th>
                <th className="px-6 py-4 font-label-md text-label-md text-on-surface-variant uppercase tracking-wider">Action</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-outline-variant">
              {currentLogs.map((log: any, i: number) => (
                <tr key={i} className={`transition-colors ${getRowClass(log.status)}`}>
                  <td className="px-6 py-4">
                    <div className={`font-mono-data font-medium ${log.status === 'Failed' ? 'text-error' : 'text-primary'}`}>{log.timestamp}</div>
                    <div className={`text-[10px] ${log.status === 'Failed' ? 'text-error' : 'text-on-surface-variant'}`}>{log.job_id}</div>
                  </td>
                  <td className="px-6 py-4 flex items-center gap-2">
                    <span className={`material-symbols-outlined text-lg ${log.status === 'Failed' ? 'text-error' : 'text-primary'}`}>
                      {log.source.includes('Smart') ? 'sensors' : log.source.includes('Grid') ? 'cloud' : 'database'}
                    </span>
                    <span className={`text-sm ${log.status === 'Failed' ? 'font-bold text-error' : ''}`}>{log.source}</span>
                  </td>
                  <td className="px-6 py-4 font-mono-data text-sm font-bold">{log.volume}</td>
                  <td className="px-6 py-4">
                    <span className={`px-2 py-0.5 text-xs font-semibold rounded ${getStatusClass(log.status)}`}>
                      {log.status}
                    </span>
                  </td>
                  <td className="px-6 py-4 font-mono-data text-sm">
                    {log.status === 'Failed' ? (
                      <span className="text-error">Critical Failure</span>
                    ) : (
                      <span>{log.errors} errors / {log.duration}</span>
                    )}
                  </td>
                  <td className="px-6 py-4">
                    {log.status === 'Failed' ? (
                      <button className="bg-error text-white px-3 py-1 rounded text-[10px] font-bold uppercase tracking-wider hover:bg-error/90 transition-colors">Debug Log</button>
                    ) : log.status === 'Warning' ? (
                      <button className="text-primary hover:underline text-xs font-bold">Review Warning</button>
                    ) : (
                      <button className="text-primary hover:underline text-xs font-bold">View Details</button>
                    )}
                  </td>
                </tr>
              ))}
              {(!data?.logs || data.logs.length === 0) && (
                <tr>
                  <td colSpan={6} className="px-6 py-8 text-center text-on-surface-variant">No logs available for this period.</td>
                </tr>
              )}
            </tbody>
          </table>
        </div>
        
        <div className="px-6 py-4 bg-surface-container-lowest border-t border-outline-variant flex justify-between items-center">
          <span className="text-sm text-on-surface-variant">
            Showing {currentLogs.length > 0 ? (currentPage - 1) * itemsPerPage + 1 : 0} - {Math.min(currentPage * itemsPerPage, logsList.length)} of {logsList.length} logs
          </span>
          <div className="flex gap-1 items-center">
            <button 
              onClick={() => setCurrentPage(p => Math.max(1, p - 1))}
              disabled={currentPage === 1}
              className="p-1 rounded hover:bg-surface-container disabled:opacity-30 flex items-center"
            >
              <span className="material-symbols-outlined">chevron_left</span>
            </button>
            <span className="text-xs text-on-surface mx-2 font-bold">Page {currentPage} of {totalPages}</span>
            <button 
              onClick={() => setCurrentPage(p => Math.min(totalPages, p + 1))}
              disabled={currentPage === totalPages}
              className="p-1 rounded hover:bg-surface-container disabled:opacity-30 flex items-center"
            >
              <span className="material-symbols-outlined">chevron_right</span>
            </button>
          </div>
        </div>
      </div>

      {/* Floating Action */}
      <button className="fixed bottom-8 right-8 w-14 h-14 bg-primary text-white rounded-full flex items-center justify-center shadow-xl hover:scale-105 active:scale-95 transition-all z-50">
        <span className="material-symbols-outlined text-2xl">add_chart</span>
      </button>
    </div>
  );
};

export default LoadHistory;
