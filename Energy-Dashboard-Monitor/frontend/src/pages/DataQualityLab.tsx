import { useEffect, useState } from 'react';
import axios from 'axios';

const API_URL = 'http://localhost:8000/api';

const DataQualityLab = () => {
  const [data, setData] = useState<any>(null);

  const fetchData = () => {
    axios.get(`${API_URL}/quality`).then(res => setData(res.data)).catch(console.error);
  };

  useEffect(() => {
    fetchData();
    window.addEventListener('refresh-data', fetchData);
    return () => window.removeEventListener('refresh-data', fetchData);
  }, []);

  const nulls = data?.issues?.nulls || 0;
  const outliers = data?.issues?.outliers || 0;
  const schema_mismatch = data?.issues?.schema_mismatch || 0;
  const score = data?.score || 100;

  return (
    <div className="pb-12">
      {/* Header Section */}
      <div className="mb-section-gap flex justify-between items-end">
        <div>
          <h3 className="font-headline-md text-headline-md text-primary mb-1">Data Quality Lab</h3>
          <p className="font-body-md text-on-surface-variant max-w-2xl">Deep dive into the cleansing and validation stages for the Western Region Energy Cluster.</p>
        </div>
        <div className="flex items-center gap-2 px-3 py-1.5 bg-surface-container-high rounded border border-outline-variant">
          <span className="material-symbols-outlined text-label-md">calendar_today</span>
          <span className="font-label-md text-label-md">Last 24 Hours</span>
        </div>
      </div>

      {/* Metrics Bento Grid */}
      <div className="grid grid-cols-1 md:grid-cols-4 gap-gutter mb-section-gap">
        <div className="bg-surface/70 backdrop-blur border border-outline-variant p-card-padding rounded-xl shadow-sm">
          <div className="flex justify-between items-start mb-4">
            <span className="font-label-md text-label-md text-on-surface-variant">Null Rate</span>
            <span className={`px-2 py-1 text-xs font-bold rounded ${nulls > 50 ? 'bg-amber-100 text-amber-700' : 'bg-emerald-100 text-emerald-700'}`}>
              {nulls > 50 ? 'Warning' : 'Low'}
            </span>
          </div>
          <div className="flex items-baseline gap-2">
            <span className="font-display-lg text-display-lg text-primary">{nulls}</span>
            <span className="text-on-surface-variant text-body-sm">Count</span>
          </div>
          <div className="mt-4 h-1 w-full bg-surface-container rounded-full overflow-hidden">
            <div className={`h-full ${nulls > 50 ? 'bg-amber-500' : 'bg-secondary'}`} style={{ width: `${Math.min(100, nulls)}%` }}></div>
          </div>
        </div>
        
        <div className="bg-surface/70 backdrop-blur border border-outline-variant p-card-padding rounded-xl shadow-sm">
          <div className="flex justify-between items-start mb-4">
            <span className="font-label-md text-label-md text-on-surface-variant">Schema Drift</span>
            <span className={`px-2 py-1 text-xs font-bold rounded ${schema_mismatch > 0 ? 'bg-amber-100 text-amber-700' : 'bg-emerald-100 text-emerald-700'}`}>
              {schema_mismatch > 0 ? 'Warning' : 'Normal'}
            </span>
          </div>
          <div className="flex items-baseline gap-2">
            <span className="font-display-lg text-display-lg text-primary">{schema_mismatch}</span>
            <span className="text-amber-600 text-body-sm font-mono-data">ALERTS</span>
          </div>
          <div className="mt-4 flex gap-1">
            {[...Array(4)].map((_, i) => (
              <span key={i} className={`w-2 h-2 rounded-full ${i < schema_mismatch ? 'bg-amber-500' : 'bg-surface-container'}`}></span>
            ))}
          </div>
        </div>
        
        <div className="bg-surface/70 backdrop-blur border border-outline-variant p-card-padding rounded-xl shadow-sm">
          <div className="flex justify-between items-start mb-4">
            <span className="font-label-md text-label-md text-on-surface-variant">Outliers</span>
            <span className={`px-2 py-1 text-xs font-bold rounded ${outliers > 200 ? 'bg-error-container text-on-error-container' : 'bg-surface-container-high text-on-surface-variant'}`}>
              {outliers > 200 ? 'High' : 'Normal'}
            </span>
          </div>
          <div className="flex items-baseline gap-2">
            <span className="font-display-lg text-display-lg text-primary">{outliers}</span>
            <span className="text-on-surface-variant text-body-sm">Detected</span>
          </div>
          <div className="mt-4 h-1 w-full bg-surface-container rounded-full overflow-hidden">
            <div className="h-full bg-primary" style={{ width: `${Math.min(100, outliers / 5)}%` }}></div>
          </div>
        </div>
        
        <div className="bg-surface/70 backdrop-blur border border-outline-variant p-card-padding rounded-xl shadow-sm">
          <div className="flex justify-between items-start mb-4">
            <span className="font-label-md text-label-md text-on-surface-variant">Total Error Count</span>
            <span className={`px-2 py-1 text-xs font-bold rounded ${score < 95 ? 'bg-error-container text-on-error-container' : 'bg-emerald-100 text-emerald-700'}`}>
              {score < 95 ? 'Critical' : 'Good'}
            </span>
          </div>
          <div className="flex items-baseline gap-2">
            <span className="font-display-lg text-display-lg text-primary">{nulls + outliers + schema_mismatch}</span>
            <span className="text-error text-body-sm">Issues</span>
          </div>
          <div className="mt-4 h-1 w-full bg-error-container/50 rounded-full overflow-hidden">
            <div className="h-full bg-error" style={{ width: `${Math.max(5, 100 - score)}%` }}></div>
          </div>
        </div>
      </div>

      {/* Comparison & Charts Section */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-gutter mb-section-gap">
        {/* Comparison View */}
        <div className="lg:col-span-2 bg-surface/70 backdrop-blur rounded-xl border border-outline-variant flex flex-col">
          <div className="p-card-padding border-b border-outline-variant flex justify-between items-center">
            <h4 className="font-headline-sm text-headline-sm text-primary">Transformation Preview</h4>
            <div className="flex bg-surface-container-low p-1 rounded-lg">
              <button className="px-3 py-1 text-label-sm bg-white shadow-sm rounded">Side-by-Side</button>
              <button className="px-3 py-1 text-label-sm text-on-surface-variant">Diff Only</button>
            </div>
          </div>
          <div className="flex flex-col md:flex-row flex-1 divide-y md:divide-y-0 md:divide-x divide-outline-variant">
            <div className="md:w-1/2 p-4">
              <div className="mb-2 font-label-md text-on-surface-variant flex items-center gap-2">
                <span className="w-2 h-2 rounded-full bg-error"></span>
                'Dirty' Incoming Data
              </div>
              <pre className="bg-surface-container-lowest p-4 rounded text-mono-data text-body-sm overflow-x-auto border border-outline-variant/30 leading-relaxed text-on-surface-variant">
{`{
  "sensor_id": "G-409",
  "ts": "2023-10-27 14:02:11",
  "val": "NaN",
  "unit": null,
  "flag": 999,
  "meta": "{\\"raw\\":\\"err_0x2\\"}"
}`}
              </pre>
            </div>
            <div className="md:w-1/2 p-4 bg-primary/5">
              <div className="mb-2 font-label-md text-primary flex items-center gap-2">
                <span className="w-2 h-2 rounded-full bg-emerald-500"></span>
                'Clean' Processed Data
              </div>
              <pre className="bg-surface-container-lowest p-4 rounded text-mono-data text-body-sm overflow-x-auto border border-outline-variant/30 leading-relaxed shadow-inner">
{`{
  "sensor_id": "G-409",
  "timestamp": "2023-10-27T14:02:11Z",
  "value": 0.0,
  "unit": "kW",
  "status": "VALIDATED_ZERO",
  "origin": "GRID_SENSOR"
}`}
              </pre>
            </div>
          </div>
        </div>

        {/* Quality by Source Chart */}
        <div className="bg-surface/70 backdrop-blur rounded-xl border border-outline-variant p-card-padding">
          <h4 className="font-headline-sm text-headline-sm text-primary mb-6">Quality by Source</h4>
          <div className="space-y-6">
            <div>
              <div className="flex justify-between mb-2">
                <span className="font-label-md text-on-surface">Smart Meters</span>
                <span className="font-mono-data text-on-surface-variant">{Math.min(100, score + 1.2).toFixed(1)}%</span>
              </div>
              <div className="h-6 w-full bg-surface-container rounded overflow-hidden">
                <div className="h-full bg-secondary transition-all" style={{ width: `${Math.min(100, score + 1.2)}%` }}></div>
              </div>
            </div>
            <div>
              <div className="flex justify-between mb-2">
                <span className="font-label-md text-on-surface">Grid Sensors</span>
                <span className="font-mono-data text-on-surface-variant">{(score - 2.8).toFixed(1)}%</span>
              </div>
              <div className="h-6 w-full bg-surface-container rounded overflow-hidden">
                <div className="h-full bg-secondary transition-all" style={{ width: `${score - 2.8}%` }}></div>
              </div>
            </div>
            <div>
              <div className="flex justify-between mb-2">
                <span className="font-label-md text-on-surface">Substation Feed</span>
                <span className="font-mono-data text-on-surface-variant">88.5%</span>
              </div>
              <div className="h-6 w-full bg-surface-container rounded overflow-hidden">
                <div className="h-full bg-amber-500 w-[88.5%]"></div>
              </div>
            </div>
            <div>
              <div className="flex justify-between mb-2">
                <span className="font-label-md text-on-surface">External API</span>
                <span className="font-mono-data text-on-surface-variant">72.1%</span>
              </div>
              <div className="h-6 w-full bg-surface-container rounded overflow-hidden">
                <div className="h-full bg-error w-[72.1%]"></div>
              </div>
            </div>
          </div>
        </div>
      </div>

      {/* Quarantine Table */}
      <div className="bg-surface/70 backdrop-blur rounded-xl border border-outline-variant overflow-hidden">
        <div className="p-card-padding border-b border-outline-variant flex justify-between items-center bg-surface-container-low">
          <div>
            <h4 className="font-headline-sm text-headline-sm text-primary">Quarantine Management</h4>
            <p className="font-body-sm text-on-surface-variant">Sample records that failed validation and require manual attention.</p>
          </div>
          <button className="px-4 py-2 bg-error text-on-error rounded font-label-md flex items-center gap-2 hover:opacity-90 transition-opacity">
            <span className="material-symbols-outlined text-[18px]">delete_sweep</span>
            Purge All Failures
          </button>
        </div>
        <div className="overflow-x-auto">
          <table className="w-full text-left border-collapse">
            <thead>
              <tr className="bg-surface-container-lowest border-b border-outline-variant">
                <th className="px-6 py-4 font-label-md text-on-surface-variant">Record ID</th>
                <th className="px-6 py-4 font-label-md text-on-surface-variant">Origin Source</th>
                <th className="px-6 py-4 font-label-md text-on-surface-variant">Failure Reason</th>
                <th className="px-6 py-4 font-label-md text-on-surface-variant">Timestamp</th>
                <th className="px-6 py-4 font-label-md text-on-surface-variant text-right">Actions</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-outline-variant">
              {data?.quarantine?.map((item: any, i: number) => (
                <tr key={i} className="hover:bg-surface-container-low/50 transition-colors">
                  <td className="px-6 py-4 font-mono-data text-primary">{item.id}</td>
                  <td className="px-6 py-4 font-body-sm">{item.source}</td>
                  <td className="px-6 py-4">
                    <span className={`px-2 py-0.5 text-xs font-semibold rounded ${item.severity === 'Critical' ? 'bg-error-container text-on-error-container' : 'bg-amber-100 text-amber-700'}`}>
                      {item.issue}
                    </span>
                  </td>
                  <td className="px-6 py-4 font-mono-data text-on-surface-variant">{item.timestamp?.split('T')[0] || 'N/A'}</td>
                  <td className="px-6 py-4 text-right">
                    <div className="flex justify-end gap-3">
                      <button className="text-primary hover:underline font-label-sm">Edit</button>
                      <button className="text-error hover:underline font-label-sm">Drop</button>
                    </div>
                  </td>
                </tr>
              ))}
              {(!data?.quarantine || data.quarantine.length === 0) && (
                <tr>
                  <td colSpan={5} className="px-6 py-8 text-center text-on-surface-variant">No quarantined items currently in queue.</td>
                </tr>
              )}
            </tbody>
          </table>
        </div>
        <div className="p-4 border-t border-outline-variant bg-surface-container-lowest flex justify-between items-center">
          <span className="font-body-sm text-on-surface-variant">Showing {data?.quarantine?.length || 0} of {nulls + outliers} failed records</span>
          <div className="flex gap-2">
            <button className="p-1 flex items-center justify-center border border-outline-variant rounded hover:bg-surface-container transition-colors disabled:opacity-50">
              <span className="material-symbols-outlined">chevron_left</span>
            </button>
            <button className="p-1 flex items-center justify-center border border-outline-variant rounded hover:bg-surface-container transition-colors disabled:opacity-50">
              <span className="material-symbols-outlined">chevron_right</span>
            </button>
          </div>
        </div>
      </div>
    </div>
  );
};

export default DataQualityLab;
