import { useEffect, useState } from 'react';
import axios from 'axios';

const API_URL = `http://${window.location.hostname}:8000/api`;

const PipelineOverview = () => {
  const [status, setStatus] = useState<any>(null);

  const fetchStatus = () => {
    axios.get(`${API_URL}/system-status`).then(res => setStatus(res.data)).catch(console.error);
  };

  useEffect(() => {
    fetchStatus();
    window.addEventListener('refresh-data', fetchStatus);
    return () => window.removeEventListener('refresh-data', fetchStatus);
  }, []);

  return (
    <div>
      <div className="mb-10 flex flex-col md:flex-row md:items-end justify-between gap-6">
        <div>
          <h2 className="font-headline-md text-headline-md text-primary mb-1">VoltStream Dashboard</h2>
          <p className="font-body-md text-on-surface-variant">Real-time visualization of energy grid data flows and ingestion health.</p>
        </div>
        <div className="flex gap-3">
          <div className="bg-surface border border-outline-variant rounded-xl p-4 flex items-center gap-4 shadow-sm">
            <div className="p-3 rounded-full bg-primary-container text-on-primary-container flex items-center justify-center">
              <span className="material-symbols-outlined" style={{ fontVariationSettings: "'FILL' 1" }}>speed</span>
            </div>
            <div>
              <p className="font-label-sm text-label-sm text-on-surface-variant uppercase tracking-wider">Today's Throughput</p>
              <p className="font-headline-sm text-headline-sm font-bold">{status?.throughput_million || 12.4}M Records</p>
            </div>
          </div>
        </div>
      </div>

      <div className="grid grid-cols-12 gap-gutter">
        {/* Overall Quality Score */}
        <div className="col-span-12 lg:col-span-4 bg-surface pipeline-card rounded-xl p-card-padding flex flex-col items-center justify-center text-center">
          <div className="w-full flex items-center justify-between mb-8">
            <h3 className="font-headline-sm text-headline-sm text-primary">Data Health Index</h3>
            <span className="material-symbols-outlined text-on-surface-variant">info</span>
          </div>
          <div className="relative w-48 h-48 mb-6">
            <svg className="w-full h-full transform -rotate-90">
              <circle className="text-surface-container-high" cx="96" cy="96" fill="transparent" r="80" stroke="currentColor" strokeWidth="12"></circle>
              <circle className="text-emerald-500" cx="96" cy="96" fill="transparent" r="80" stroke="currentColor" strokeDasharray="502.6" strokeDashoffset={502.6 - (502.6 * (status?.overall_quality_score || 0) / 100)} strokeLinecap="round" strokeWidth="12"></circle>
            </svg>
            <div className="absolute inset-0 flex flex-col items-center justify-center">
              <span className="font-display-lg text-display-lg text-primary leading-none">{status?.overall_quality_score || 0}%</span>
              <span className="font-label-sm text-label-sm text-on-surface-variant uppercase mt-1">Excellent</span>
            </div>
          </div>
          <p className="font-body-sm text-body-sm text-on-surface-variant max-w-[240px]">
            Aggregate quality score across all active ingestion nodes. System performing above SLA.
          </p>
        </div>

        {/* KPI Row */}
        <div className="col-span-12 lg:col-span-8 grid grid-cols-1 md:grid-cols-2 gap-gutter">
          <div className="bg-surface pipeline-card rounded-xl p-card-padding flex flex-col justify-between">
            <div>
              <div className="flex items-center justify-between mb-4">
                <span className="p-2 bg-secondary-container text-on-secondary-container rounded-lg flex items-center">
                  <span className="material-symbols-outlined">hub</span>
                </span>
                <span className="text-emerald-500 font-label-md">+2 from yesterday</span>
              </div>
              <h4 className="font-label-md text-label-md text-on-surface-variant uppercase tracking-wider mb-1">Active Pipelines</h4>
              <p className="font-display-lg text-display-lg text-primary leading-tight">{status?.active_pipelines || 0}</p>
            </div>
          </div>

          <div className="bg-surface pipeline-card rounded-xl p-card-padding flex flex-col justify-between">
            <div>
              <div className="flex items-center justify-between mb-4">
                <span className="p-2 bg-error-container text-on-error-container rounded-lg flex items-center">
                  <span className="material-symbols-outlined">warning</span>
                </span>
                <span className="text-error font-label-md">-0.4% improvement</span>
              </div>
              <h4 className="font-label-md text-label-md text-on-surface-variant uppercase tracking-wider mb-1">Global Error Rate</h4>
              <p className="font-display-lg text-display-lg text-primary leading-tight">{(status?.global_error_rate || 0) * 100}%</p>
            </div>
            <div className="mt-4 pt-4 border-t border-outline-variant">
              <div className="w-full h-2 progress-bar-bg rounded-full overflow-hidden">
                <div className="bg-error h-full" style={{ width: '12%' }}></div>
              </div>
              <p className="font-label-sm text-label-sm text-on-surface-variant mt-2">Critical threshold: 0.50%</p>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
};

export default PipelineOverview;
