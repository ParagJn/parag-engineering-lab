import { useEffect, useState } from 'react';
import axios from 'axios';

const API_URL = '/api';

const PipelineOverview = () => {
  const [status, setStatus] = useState<any>(null);
  const [datasetStats, setDatasetStats] = useState<any>({});

  const fetchStatus = () => {
    axios.get(`${API_URL}/system-status`).then(res => setStatus(res.data)).catch(console.error);
  };

  const fetchDatasetStats = async () => {
    try {
      const [customers, meters, readings, sensors, sensorReadings, billing, weather] = await Promise.all([
        axios.get(`${API_URL}/customers?limit=1`),
        axios.get(`${API_URL}/smart-meters?limit=1`),
        axios.get(`${API_URL}/meter-readings?limit=1`),
        axios.get(`${API_URL}/grid-sensors?limit=1`),
        axios.get(`${API_URL}/sensor-readings?limit=1`),
        axios.get(`${API_URL}/billing?limit=1`),
        axios.get(`${API_URL}/weather?limit=1`)
      ]);

      setDatasetStats({
        customers: customers.data.total,
        meters: meters.data.total,
        readings: readings.data.total,
        sensors: sensors.data.total,
        sensorReadings: sensorReadings.data.total,
        billing: billing.data.total,
        weather: weather.data.total
      });
    } catch (error) {
      console.error('Error fetching dataset stats:', error);
    }
  };

  useEffect(() => {
    fetchStatus();
    fetchDatasetStats();
    window.addEventListener('refresh-data', () => {
      fetchStatus();
      fetchDatasetStats();
    });
    return () => window.removeEventListener('refresh-data', fetchStatus);
  }, []);

  const totalRecords = Object.values(datasetStats).reduce((sum: number, val: any) => sum + (val || 0), 0);

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

      <div className="grid grid-cols-12 gap-gutter mb-section-gap">
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
              <span className="font-label-sm text-label-sm text-on-surface-variant uppercase mt-1">
                {(status?.overall_quality_score || 0) > 95 ? 'Excellent' : (status?.overall_quality_score || 0) > 90 ? 'Good' : 'Warning'}
              </span>
            </div>
          </div>
          <p className="font-body-sm text-body-sm text-on-surface-variant max-w-[240px]">
            Aggregate quality score across all active ingestion nodes. System performing {(status?.overall_quality_score || 0) > 90 ? 'above' : 'below'} SLA.
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
              <p className="font-display-lg text-display-lg text-primary leading-tight">{((status?.global_error_rate || 0) * 100).toFixed(2)}%</p>
            </div>
            <div className="mt-4 pt-4 border-t border-outline-variant">
              <div className="w-full h-2 progress-bar-bg rounded-full overflow-hidden">
                <div className="bg-error h-full" style={{ width: `${Math.min(100, (status?.global_error_rate || 0) * 100 * 10)}%` }}></div>
              </div>
              <p className="font-label-sm text-label-sm text-on-surface-variant mt-2">Critical threshold: 0.50%</p>
            </div>
          </div>
        </div>
      </div>

      {/* Dataset Overview Grid */}
      <div className="mb-section-gap">
        <h3 className="font-headline-sm text-headline-sm text-primary mb-4">Data Pipeline Sources</h3>
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-gutter">
          {/* Customers */}
          <div className="bg-surface border border-outline-variant rounded-xl p-card-padding hover:shadow-lg transition-shadow">
            <div className="flex items-start justify-between mb-4">
              <div className="p-3 rounded-lg bg-primary-container text-on-primary-container">
                <span className="material-symbols-outlined text-2xl">person</span>
              </div>
              <span className="px-2 py-1 bg-emerald-100 text-emerald-700 text-xs font-bold rounded">ACTIVE</span>
            </div>
            <h4 className="font-label-lg text-label-lg font-bold mb-1">Customers</h4>
            <p className="font-display-sm text-display-sm text-primary font-bold mb-2">{datasetStats.customers?.toLocaleString() || '0'}</p>
            <p className="text-body-sm text-on-surface-variant">Master customer records</p>
          </div>

          {/* Smart Meters */}
          <div className="bg-surface border border-outline-variant rounded-xl p-card-padding hover:shadow-lg transition-shadow">
            <div className="flex items-start justify-between mb-4">
              <div className="p-3 rounded-lg bg-secondary-container text-on-secondary-container">
                <span className="material-symbols-outlined text-2xl">sensors</span>
              </div>
              <span className="px-2 py-1 bg-emerald-100 text-emerald-700 text-xs font-bold rounded">ACTIVE</span>
            </div>
            <h4 className="font-label-lg text-label-lg font-bold mb-1">Smart Meters</h4>
            <p className="font-display-sm text-display-sm text-primary font-bold mb-2">{datasetStats.meters?.toLocaleString() || '0'}</p>
            <p className="text-body-sm text-on-surface-variant">Physical meter devices</p>
          </div>

          {/* Meter Readings */}
          <div className="bg-surface border border-outline-variant rounded-xl p-card-padding hover:shadow-lg transition-shadow">
            <div className="flex items-start justify-between mb-4">
              <div className="p-3 rounded-lg bg-tertiary-container text-on-tertiary-container">
                <span className="material-symbols-outlined text-2xl">bolt</span>
              </div>
              <span className="px-2 py-1 bg-emerald-100 text-emerald-700 text-xs font-bold rounded">STREAMING</span>
            </div>
            <h4 className="font-label-lg text-label-lg font-bold mb-1">Meter Readings</h4>
            <p className="font-display-sm text-display-sm text-primary font-bold mb-2">{datasetStats.readings?.toLocaleString() || '0'}</p>
            <p className="text-body-sm text-on-surface-variant">Power consumption data</p>
          </div>

          {/* Grid Sensors */}
          <div className="bg-surface border border-outline-variant rounded-xl p-card-padding hover:shadow-lg transition-shadow">
            <div className="flex items-start justify-between mb-4">
              <div className="p-3 rounded-lg bg-error-container text-on-error-container">
                <span className="material-symbols-outlined text-2xl">router</span>
              </div>
              <span className="px-2 py-1 bg-emerald-100 text-emerald-700 text-xs font-bold rounded">ACTIVE</span>
            </div>
            <h4 className="font-label-lg text-label-lg font-bold mb-1">Grid Sensors</h4>
            <p className="font-display-sm text-display-sm text-primary font-bold mb-2">{datasetStats.sensors?.toLocaleString() || '0'}</p>
            <p className="text-body-sm text-on-surface-variant">Infrastructure sensors</p>
          </div>

          {/* Sensor Readings */}
          <div className="bg-surface border border-outline-variant rounded-xl p-card-padding hover:shadow-lg transition-shadow">
            <div className="flex items-start justify-between mb-4">
              <div className="p-3 rounded-lg bg-primary-container text-on-primary-container">
                <span className="material-symbols-outlined text-2xl">monitoring</span>
              </div>
              <span className="px-2 py-1 bg-emerald-100 text-emerald-700 text-xs font-bold rounded">STREAMING</span>
            </div>
            <h4 className="font-label-lg text-label-lg font-bold mb-1">Sensor Readings</h4>
            <p className="font-display-sm text-display-sm text-primary font-bold mb-2">{datasetStats.sensorReadings?.toLocaleString() || '0'}</p>
            <p className="text-body-sm text-on-surface-variant">Grid monitoring data</p>
          </div>

          {/* Billing Records */}
          <div className="bg-surface border border-outline-variant rounded-xl p-card-padding hover:shadow-lg transition-shadow">
            <div className="flex items-start justify-between mb-4">
              <div className="p-3 rounded-lg bg-secondary-container text-on-secondary-container">
                <span className="material-symbols-outlined text-2xl">receipt_long</span>
              </div>
              <span className="px-2 py-1 bg-amber-100 text-amber-700 text-xs font-bold rounded">BATCH</span>
            </div>
            <h4 className="font-label-lg text-label-lg font-bold mb-1">Billing Records</h4>
            <p className="font-display-sm text-display-sm text-primary font-bold mb-2">{datasetStats.billing?.toLocaleString() || '0'}</p>
            <p className="text-body-sm text-on-surface-variant">Customer billing data</p>
          </div>

          {/* Weather Data */}
          <div className="bg-surface border border-outline-variant rounded-xl p-card-padding hover:shadow-lg transition-shadow">
            <div className="flex items-start justify-between mb-4">
              <div className="p-3 rounded-lg bg-tertiary-container text-on-tertiary-container">
                <span className="material-symbols-outlined text-2xl">cloud</span>
              </div>
              <span className="px-2 py-1 bg-emerald-100 text-emerald-700 text-xs font-bold rounded">ACTIVE</span>
            </div>
            <h4 className="font-label-lg text-label-lg font-bold mb-1">Weather Data</h4>
            <p className="font-display-sm text-display-sm text-primary font-bold mb-2">{datasetStats.weather?.toLocaleString() || '0'}</p>
            <p className="text-body-sm text-on-surface-variant">Weather observations</p>
          </div>

          {/* Total Records */}
          <div className="bg-primary text-on-primary rounded-xl p-card-padding hover:shadow-lg transition-shadow">
            <div className="flex items-start justify-between mb-4">
              <div className="p-3 rounded-lg bg-white/20">
                <span className="material-symbols-outlined text-2xl">database</span>
              </div>
              <span className="px-2 py-1 bg-white/20 text-white text-xs font-bold rounded">TOTAL</span>
            </div>
            <h4 className="font-label-lg text-label-lg font-bold mb-1">Total Records</h4>
            <p className="font-display-sm text-display-sm font-bold mb-2">{totalRecords.toLocaleString()}</p>
            <p className="text-body-sm opacity-80">Across all pipelines</p>
          </div>
        </div>
      </div>

      {/* System Information */}
      <div className="bg-surface border border-outline-variant rounded-xl p-card-padding">
        <h3 className="font-headline-sm text-headline-sm text-primary mb-4">System Information</h3>
        <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
          <div>
            <p className="font-label-sm text-label-sm text-on-surface-variant mb-2">Last Simulation</p>
            <p className="font-body-md text-on-surface">
              {status?.last_simulation ? new Date(status.last_simulation).toLocaleString() : 'Never'}
            </p>
          </div>
          <div>
            <p className="font-label-sm text-label-sm text-on-surface-variant mb-2">Total Simulations</p>
            <p className="font-body-md text-on-surface font-bold">{status?.total_simulations || 0}</p>
          </div>
          <div>
            <p className="font-label-sm text-label-sm text-on-surface-variant mb-2">System Status</p>
            <p className={`font-body-md font-bold ${status?.status === 'Healthy' ? 'text-emerald-600' : 'text-amber-600'}`}>
              {status?.status || 'Unknown'}
            </p>
          </div>
        </div>
      </div>
    </div>
  );
};

export default PipelineOverview;

// Made with Bob
