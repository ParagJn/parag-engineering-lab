import { useEffect, useState } from 'react';
import axios from 'axios';

const API_URL = '/api';

const LoadHistory = () => {
  const [data, setData] = useState<any>(null);
  const [currentPage, setCurrentPage] = useState(1);
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
              <p className="font-label-sm text-label-sm text-on-surface-variant">Total Volume Loaded (Last 7 Days)</p>
            </div>
            <div className="flex gap-2">
              <button className="px-3 py-1 rounded bg-surface-container border border-outline-variant text-xs font-medium text-primary">Daily</button>
              <button className="px-3 py-1 rounded text-xs font-medium text-on-surface-variant hover:bg-surface-container border border-transparent">Weekly</button>
            </div>
          </div>
          
          {/* Simulated Line Chart */}
          <div className="relative h-64 w-full bg-surface-container-lowest rounded-lg border border-outline-variant/30 flex items-end p-4">
            <div className="absolute inset-0 flex flex-col justify-between py-4 px-2 pointer-events-none">
              <div className="w-full border-t border-outline-variant/20 text-[10px] text-outline pt-1">5.0 TB</div>
              <div className="w-full border-t border-outline-variant/20 text-[10px] text-outline pt-1">2.5 TB</div>
              <div className="w-full border-t border-outline-variant/20 text-[10px] text-outline pt-1">1.0 TB</div>
              <div className="w-full border-t border-outline-variant/20 text-[10px] text-outline pt-1">0 TB</div>
            </div>
            <div className="relative w-full h-full flex items-end justify-between px-8">
              {/* Chart Logic: Dynamic shapes */}
              <svg className="absolute bottom-0 left-0 w-full h-[80%] text-primary/10 fill-current overflow-visible" viewBox="0 0 1000 200" preserveAspectRatio="none">
                <path d="M0 200 L0 150 C 100 120, 200 180, 300 140 C 400 100, 500 160, 600 80 C 700 40, 800 120, 900 60 C 950 40, 1000 20, 1000 20 L1000 200 Z"></path>
                <path className="text-primary" d="M0 150 C 100 120, 200 180, 300 140 C 400 100, 500 160, 600 80 C 700 40, 800 120, 900 60 C 950 40, 1000 20, 1000 20" fill="none" stroke="currentColor" strokeWidth="3"></path>
              </svg>
              <div className="absolute right-10 top-10 flex items-center gap-2 bg-surface/90 backdrop-blur px-3 py-2 border border-outline-variant rounded shadow-lg transition-all duration-300">
                <div className="w-2 h-2 rounded-full bg-primary animate-pulse"></div>
                <span className="text-xs font-bold">Today: {data?.volume_chart?.[6]?.success || 0}00 GB</span>
              </div>
            </div>
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
