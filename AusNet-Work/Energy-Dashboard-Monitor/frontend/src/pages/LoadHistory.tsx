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
          <div className="flex flex-col sm:flex-row justify-between sm:items-center mb-6 gap-4">
            <div>
              <h3 className="font-headline-sm text-headline-sm text-primary">Pipeline Performance Trends</h3>
              <p className="font-label-sm text-label-sm text-on-surface-variant">Track volume and quality metrics over time</p>
            </div>
            <div className="flex gap-2">
              <button
                onClick={() => setChartView('volume')}
                className={`px-4 py-2 rounded-lg text-sm font-medium transition-all flex items-center gap-2 ${
                  chartView === 'volume'
                    ? 'bg-blue-600 text-white shadow-lg'
                    : 'bg-white text-on-surface-variant hover:bg-surface-container border border-outline-variant'
                }`}
              >
                <span className="material-symbols-outlined text-base">trending_up</span>
                Volume
              </button>
              <button
                onClick={() => setChartView('quality')}
                className={`px-4 py-2 rounded-lg text-sm font-medium transition-all flex items-center gap-2 ${
                  chartView === 'quality'
                    ? 'bg-emerald-600 text-white shadow-lg'
                    : 'bg-white text-on-surface-variant hover:bg-surface-container border border-outline-variant'
                }`}
              >
                <span className="material-symbols-outlined text-base">verified</span>
                Quality
              </button>
            </div>
          </div>
          
          {/* Line Chart with meaningful data visualization */}
          <div className="relative h-80 w-full bg-white rounded-xl border border-outline-variant p-6 shadow-sm">
            {(() => {
              const runs: any[] = data?.pipeline_runs || [];
              if (runs.length === 0) {
                return (
                  <div className="absolute inset-0 flex flex-col items-center justify-center gap-3 text-on-surface-variant">
                    <span className="material-symbols-outlined text-5xl opacity-20">show_chart</span>
                    <p className="text-base font-medium">No pipeline runs yet</p>
                    <p className="text-sm opacity-70">Run a simulation to see performance trends</p>
                  </div>
                );
              }
              
              // Calculate values and prepare data
              const values = runs.map((r: any) =>
                chartView === 'volume' ? (r.records_processed ?? 0) : (r.quality_score ?? 85)
              );
              
              // Better centering: add padding above and below the data range
              let maxValue: number;
              let minValue: number;
              
              if (chartView === 'volume') {
                const dataMax = Math.max(...values);
                const dataMin = Math.min(...values);
                const range = dataMax - dataMin;
                const padding = range * 0.15; // 15% padding
                maxValue = Math.ceil(dataMax + padding);
                minValue = Math.floor(Math.max(0, dataMin - padding));
              } else {
                // Quality view
                const dataMax = Math.max(...values);
                const dataMin = Math.min(...values);
                maxValue = Math.min(100, dataMax + 5);
                minValue = Math.max(0, dataMin - 5);
              }
              
              // Calculate points for the line
              const points = runs.map((run: any, i: number) => {
                const value = chartView === 'volume' ? (run.records_processed ?? 0) : (run.quality_score ?? 85);
                const x = (i / (runs.length - 1)) * 100;
                const y = 100 - ((value - minValue) / (maxValue - minValue)) * 100;
                return { x, y, value, run, index: i };
              });
              
              // Create SVG path
              const pathData = points.map((p, i) =>
                `${i === 0 ? 'M' : 'L'} ${p.x}% ${p.y}%`
              ).join(' ');
              
              // Create area fill path
              const areaPath = `${pathData} L 100% 100% L 0% 100% Z`;
              
              // Determine colors based on view
              const lineColor = chartView === 'volume' ? '#2563eb' : '#10b981'; // blue-600 : emerald-500
              const gradientStart = chartView === 'volume' ? '#3b82f6' : '#34d399'; // blue-500 : emerald-400
              const gradientEnd = chartView === 'volume' ? '#dbeafe' : '#d1fae5'; // blue-100 : emerald-100
              
              return (
                <div className="relative w-full h-full">
                  {/* Y-axis labels */}
                  <div className="absolute left-0 top-0 bottom-10 w-12 flex flex-col justify-between text-xs font-medium text-gray-600">
                    <span>{chartView === 'volume' ? maxValue.toLocaleString() : `${maxValue}%`}</span>
                    <span>{chartView === 'volume' ? Math.round((maxValue + minValue) / 2).toLocaleString() : `${Math.round((maxValue + minValue) / 2)}%`}</span>
                    <span>{chartView === 'volume' ? minValue.toLocaleString() : `${minValue}%`}</span>
                  </div>
                  
                  {/* Chart area */}
                  <div className="absolute left-14 right-0 top-0 bottom-10 border-l-2 border-b-2 border-gray-200">
                    {/* Horizontal grid lines */}
                    <div className="absolute inset-0 flex flex-col justify-between pointer-events-none">
                      <div className="w-full border-t border-gray-100"></div>
                      <div className="w-full border-t border-gray-100"></div>
                      <div className="w-full border-t border-gray-100"></div>
                    </div>
                    
                    {/* SVG Line Chart */}
                    <svg className="absolute inset-0 w-full h-full overflow-visible" preserveAspectRatio="none">
                      <defs>
                        <linearGradient id={`areaGradient-${chartView}`} x1="0%" y1="0%" x2="0%" y2="100%">
                          <stop offset="0%" stopColor={gradientStart} stopOpacity="0.3" />
                          <stop offset="100%" stopColor={gradientEnd} stopOpacity="0.05" />
                        </linearGradient>
                      </defs>
                      
                      {/* Area fill */}
                      <path
                        d={areaPath}
                        fill={`url(#areaGradient-${chartView})`}
                        className="transition-all duration-700"
                      />
                      
                      {/* Line */}
                      <path
                        d={pathData}
                        fill="none"
                        stroke={lineColor}
                        strokeWidth="3"
                        strokeLinecap="round"
                        strokeLinejoin="round"
                        className="transition-all duration-700"
                        style={{ filter: 'drop-shadow(0 2px 4px rgba(0,0,0,0.1))' }}
                      />
                      
                      {/* Data points */}
                      {points.map((point, i) => {
                        const isLatest = i === points.length - 1;
                        return (
                          <g key={i}>
                            <circle
                              cx={`${point.x}%`}
                              cy={`${point.y}%`}
                              r={isLatest ? "6" : "4"}
                              fill="white"
                              stroke={lineColor}
                              strokeWidth={isLatest ? "3" : "2"}
                              className="transition-all duration-300 hover:r-6 cursor-pointer"
                              style={{ filter: isLatest ? 'drop-shadow(0 0 6px rgba(37, 99, 235, 0.5))' : 'none' }}
                            />
                            {isLatest && (
                              <circle
                                cx={`${point.x}%`}
                                cy={`${point.y}%`}
                                r="6"
                                fill={lineColor}
                                opacity="0.3"
                                className="animate-ping"
                              />
                            )}
                          </g>
                        );
                      })}
                    </svg>
                    
                    {/* Interactive tooltips */}
                    {points.map((point, i) => {
                      const isLatest = i === points.length - 1;
                      const displayValue = chartView === 'volume'
                        ? `${point.value.toLocaleString()} records`
                        : `${point.value.toFixed(1)}% quality`;
                      
                      return (
                        <div
                          key={i}
                          className="absolute group cursor-pointer z-50"
                          style={{
                            left: `${point.x}%`,
                            top: `${point.y}%`,
                            transform: 'translate(-50%, -50%)'
                          }}
                        >
                          {/* Hover area */}
                          <div className="w-8 h-8 -m-4"></div>
                          
                          {/* Tooltip - only show on hover for all points */}
                          <div className="absolute bottom-full left-1/2 -translate-x-1/2 mb-3 opacity-0 group-hover:opacity-100 transition-opacity pointer-events-none z-50">
                            <div className={`${isLatest ? 'bg-gradient-to-r from-blue-600 to-cyan-600' : 'bg-gray-900'} text-white px-3 py-2 rounded-lg shadow-xl whitespace-nowrap text-xs font-semibold`}>
                              <div className="flex items-center gap-2">
                                {isLatest && <span className="w-1.5 h-1.5 bg-white rounded-full animate-pulse"></span>}
                                <span>{displayValue}</span>
                              </div>
                              <div className="text-[10px] opacity-75 mt-0.5">
                                {new Date(point.run.timestamp).toLocaleTimeString('en-US', { hour: '2-digit', minute: '2-digit' })}
                              </div>
                            </div>
                            <div className={`w-2 h-2 ${isLatest ? 'bg-blue-600' : 'bg-gray-900'} rotate-45 mx-auto -mt-1`}></div>
                          </div>
                        </div>
                      );
                    })}
                  </div>
                  
                  {/* X-axis time labels */}
                  <div className="absolute left-14 right-0 bottom-0 h-10 flex justify-between items-center text-xs font-medium text-gray-600">
                    {runs.map((run: any, i: number) => {
                      // Show only first, middle, and last labels to avoid crowding
                      if (i === 0 || i === Math.floor(runs.length / 2) || i === runs.length - 1) {
                        return (
                          <span key={i} className="text-center">
                            {new Date(run.timestamp).toLocaleTimeString('en-US', {
                              hour: '2-digit',
                              minute: '2-digit',
                              hour12: false
                            })}
                          </span>
                        );
                      }
                      return null;
                    })}
                  </div>
                  
                  {/* Legend */}
                  <div className="absolute top-0 right-0 flex items-center gap-4 text-xs z-10">
                    <div className="flex items-center gap-2 bg-white px-3 py-1.5 rounded-full border border-gray-200 shadow-sm">
                      <div className={`w-3 h-3 rounded-full ${chartView === 'volume' ? 'bg-blue-600' : 'bg-emerald-500'}`}></div>
                      <span className="font-medium text-gray-700">
                        {chartView === 'volume' ? 'Records Processed' : 'Data Quality Score'}
                      </span>
                    </div>
                    <div className="bg-white px-3 py-1.5 rounded-full border border-gray-200 shadow-sm">
                      <span className="font-semibold text-gray-900">{runs.length}</span>
                      <span className="text-gray-500 ml-1">runs</span>
                    </div>
                  </div>
                </div>
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
