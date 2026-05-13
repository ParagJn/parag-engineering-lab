import { useEffect, useRef, useState } from 'react';
import axios from 'axios';

const API_URL = '/api';

const DataQualityLab = () => {
  const [data, setData] = useState<any>(null);
  const [datasetStats, setDatasetStats] = useState<any>({});
  const [currentPage, setCurrentPage] = useState(1);
  const [isPurging, setIsPurging] = useState(false);
  const [selectedFilter, setSelectedFilter] = useState<'all' | 'nulls' | 'outliers' | 'schema'>('all');
  const [showAIModal, setShowAIModal] = useState(false);
  const [aiFixStage, setAiFixStage] = useState<'idle' | 'analyzing' | 'identifying' | 'fixing' | 'validating' | 'complete'>('idle');
  const [aiProgress, setAiProgress] = useState(0);
  const [aiFixedCounts, setAiFixedCounts] = useState({ nulls: 0, schema: 0, outliers: 0 });
  const [aiApplied, setAiApplied] = useState(false);
  const [explanations, setExplanations] = useState<string[]>([]);
  const explanationsEndRef = useRef<HTMLDivElement>(null);
  const [isQuarantineCollapsed, setIsQuarantineCollapsed] = useState(false);
  const [showLineageModal, setShowLineageModal] = useState(false);
  const [lineageLoading, setLineageLoading] = useState(false);
  const [selectedRecord, setSelectedRecord] = useState<any>(null);
  const [lineageSvg, setLineageSvg] = useState<string>('');
  const itemsPerPage = 5;

  const fetchData = () => {
    axios.get(`${API_URL}/quality`).then(res => setData(res.data)).catch(console.error);
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
    if (explanations.length > 0) {
      explanationsEndRef.current?.scrollIntoView({ behavior: 'smooth' });
    }
  }, [explanations]);

  useEffect(() => {
    fetchData();
    fetchDatasetStats();
    window.addEventListener('refresh-data', () => {
      fetchData();
      fetchDatasetStats();
    });
    return () => window.removeEventListener('refresh-data', fetchData);
  }, []);

  const handlePurge = async () => {
    if (isPurging) return;
    setIsPurging(true);
    try {
      await axios.post(`${API_URL}/quality/purge`);
      fetchData();
      setCurrentPage(1);
    } catch (e) {
      console.error(e);
    } finally {
      setIsPurging(false);
    }
  };

  const handleViewLineage = async (record: any) => {
    setSelectedRecord(record);
    setShowLineageModal(true);
    setLineageLoading(true);
    setLineageSvg('');

    // Simulate AI lineage generation with random failure points
    const failureStages = ['Acquisition', 'Validation', 'Cleansing', 'Transformation', 'Lakehouse Load'];
    const randomFailureStage = failureStages[Math.floor(Math.random() * failureStages.length)];
    
    // Simulate API call delay (2-4 seconds)
    const delay = 2000 + Math.random() * 2000;
    
    setTimeout(() => {
      // Generate SVG lineage diagram
      const svg = generateLineageSVG(record, randomFailureStage);
      setLineageSvg(svg);
      setLineageLoading(false);
    }, delay);
  };

  const generateLineageSVG = (record: any, failureStage: string) => {
    const stages = [
      { name: 'Acquisition', icon: 'cloud_download', time: '120ms' },
      { name: 'Validation', icon: 'verified_user', time: '215ms' },
      { name: 'Cleansing', icon: 'auto_fix_high', time: '450ms' },
      { name: 'Transformation', icon: 'transform', time: '280ms' },
      { name: 'Lakehouse Load', icon: 'database', time: 'Idle' }
    ];

    const stageWidth = 180;
    const stageHeight = 100;
    const spacing = 80;
    const totalWidth = stages.length * (stageWidth + spacing) - spacing + 100;
    const svgHeight = 300;

    let svgContent = `<svg width="${totalWidth}" height="${svgHeight}" viewBox="0 0 ${totalWidth} ${svgHeight}" xmlns="http://www.w3.org/2000/svg">`;
    
    // Background
    svgContent += `<rect width="100%" height="100%" fill="#f8f9fa"/>`;
    
    // Title
    svgContent += `<text x="50%" y="30" text-anchor="middle" font-family="system-ui, sans-serif" font-size="18" font-weight="600" fill="#1a1a1a">ETL Processing Flow - Record ${record.id}</text>`;
    svgContent += `<text x="50%" y="55" text-anchor="middle" font-family="system-ui, sans-serif" font-size="13" fill="#666">Live visual representation of data packet journey</text>`;

    stages.forEach((stage, index) => {
      const x = 50 + index * (stageWidth + spacing);
      const y = 100;
      const isFailed = stage.name === failureStage;
      const isPassed = stages.findIndex(s => s.name === failureStage) > index;
      
      const bgColor = isFailed ? '#fee' : isPassed ? '#e8f5e9' : '#f5f5f5';
      const borderColor = isFailed ? '#dc3545' : isPassed ? '#28a745' : '#dee2e6';
      const textColor = isFailed ? '#dc3545' : isPassed ? '#28a745' : '#495057';

      // Stage box
      svgContent += `<rect x="${x}" y="${y}" width="${stageWidth}" height="${stageHeight}" rx="8" fill="${bgColor}" stroke="${borderColor}" stroke-width="2"/>`;
      
      // Stage name
      svgContent += `<text x="${x + stageWidth/2}" y="${y + 35}" text-anchor="middle" font-family="system-ui, sans-serif" font-size="15" font-weight="600" fill="${textColor}">${stage.name}</text>`;
      
      // Time
      svgContent += `<text x="${x + stageWidth/2}" y="${y + 55}" text-anchor="middle" font-family="system-ui, sans-serif" font-size="12" fill="#666">${stage.time}</text>`;
      
      // Status badge
      const status = isFailed ? 'FAILED' : isPassed ? 'DONE' : 'QUEUED';
      const badgeColor = isFailed ? '#dc3545' : isPassed ? '#28a745' : '#6c757d';
      svgContent += `<rect x="${x + stageWidth/2 - 30}" y="${y + 70}" width="60" height="20" rx="4" fill="${badgeColor}"/>`;
      svgContent += `<text x="${x + stageWidth/2}" y="${y + 83}" text-anchor="middle" font-family="system-ui, sans-serif" font-size="10" font-weight="600" fill="white">${status}</text>`;

      // Connector arrow
      if (index < stages.length - 1) {
        const arrowX = x + stageWidth + 10;
        const arrowY = y + stageHeight / 2;
        const arrowEndX = arrowX + spacing - 20;
        const arrowColor = isPassed ? '#28a745' : '#dee2e6';
        
        svgContent += `<line x1="${arrowX}" y1="${arrowY}" x2="${arrowEndX}" y2="${arrowY}" stroke="${arrowColor}" stroke-width="3"/>`;
        svgContent += `<polygon points="${arrowEndX},${arrowY} ${arrowEndX - 8},${arrowY - 5} ${arrowEndX - 8},${arrowY + 5}" fill="${arrowColor}"/>`;
      }
    });

    // Legend
    const legendY = 230;
    svgContent += `<circle cx="50" cy="${legendY}" r="6" fill="#28a745"/>`;
    svgContent += `<text x="65" y="${legendY + 4}" font-family="system-ui, sans-serif" font-size="12" fill="#666">Active</text>`;
    
    svgContent += `<circle cx="150" cy="${legendY}" r="6" fill="#6c757d"/>`;
    svgContent += `<text x="165" y="${legendY + 4}" font-family="system-ui, sans-serif" font-size="12" fill="#666">Queued</text>`;

    svgContent += `<circle cx="250" cy="${legendY}" r="6" fill="#dc3545"/>`;
    svgContent += `<text x="265" y="${legendY + 4}" font-family="system-ui, sans-serif" font-size="12" fill="#666">Failed</text>`;

    svgContent += `</svg>`;
    return svgContent;
  };

  const applyAIFixes = () => {
    // Apply the AI fixes - update the data to show reduced values
    setAiApplied(true);
    setShowAIModal(false);
    setAiFixStage('idle');
    setAiProgress(0);
    // Optionally refresh data to show updated state
    fetchData();
  };

  const handleAIFix = async () => {
    setShowAIModal(true);
    setAiFixStage('analyzing');
    setAiProgress(0);
    setExplanations([]);

    // Helper: generate a human-readable AI explanation for a quarantine item
    const explainFix = (item: any): string => {
      const ts = new Date().toLocaleTimeString('en-US', { hour12: false });
      const id = item.id?.length > 14 ? item.id.substring(0, 14) + '…' : (item.id || 'UNKNOWN');
      if (item.issue_type === 'null') {
        const field = item.issue?.toLowerCase().includes('email') ? 'email' :
                      item.issue?.toLowerCase().includes('phone') ? 'phone' :
                      item.issue?.toLowerCase().includes('temperature') ? 'temperature_c' :
                      item.issue?.toLowerCase().includes('tension') ? 'line_tension_kg' :
                      item.issue?.toLowerCase().includes('power') ? 'power_usage_kwh' :
                      item.issue?.toLowerCase().includes('billing') ? 'billing_period_start' :
                      item.issue?.toLowerCase().includes('install') ? 'installation_date' : 'field';
        const strategy = field === 'email' ? 'domain pattern (id@example.com)' :
                         field === 'phone' ? 'E.164 placeholder (+1-555-0100)' :
                         field === 'temperature_c' ? 'sensor baseline → 20.0°C' :
                         field === 'installation_date' ? 'registration date proxy' :
                         'historical average imputation';
        return `[${ts}] ✓ ${id} | null ${field} → ${strategy}`;
      }
      if (item.issue_type === 'outlier') {
        const fix = item.issue?.toLowerCase().includes('negative') ? 'reflected to absolute value' :
                    item.issue?.toLowerCase().includes('voltage') ? 'clamped to 249V (safe threshold)' :
                    item.issue?.toLowerCase().includes('temperature') ? 'bounded to ±50°C operational range' :
                    item.issue?.toLowerCase().includes('wind') ? 'capped at 199 km/h' :
                    'clamped to 99th percentile';
        return `[${ts}] ✓ ${id} | outlier → ${fix}`;
      }
      if (item.issue_type === 'schema') {
        const fix = item.issue?.toLowerCase().includes('email') ? 'regex-corrected format' :
                    item.issue?.toLowerCase().includes('state') ? 'geolocation lookup → CA' :
                    item.issue?.toLowerCase().includes('status') ? 'enum standardized → PENDING' :
                    'schema constraint enforced';
        return `[${ts}] ✓ ${id} | schema → ${fix}`;
      }
      return `[${ts}] ✓ ${id} | resolved`;
    };

    let localProgress = 0;
    const stages = [
      { stage: 'analyzing' as const, duration: 1500, targetProgress: 20 },
      { stage: 'identifying' as const, duration: 2000, targetProgress: 40 },
      { stage: 'fixing' as const, duration: 2800, targetProgress: 70 },
      { stage: 'validating' as const, duration: 1500, targetProgress: 90 },
      { stage: 'complete' as const, duration: 1000, targetProgress: 100 }
    ];

    for (const { stage, duration, targetProgress } of stages) {
      setAiFixStage(stage);

      if (stage === 'identifying') {
        // Seed the log with scanner header lines
        const ts = new Date().toLocaleTimeString('en-US', { hour12: false });
        setExplanations([
          `[${ts}] 🔍 AI ENGINE: Initializing remediation pipeline...`,
          `[${ts}] 🔍 Scanning ${data?.total_records_analyzed?.toLocaleString() || '35,050'} records across 7 datasets`,
          `[${ts}] 🔍 Detected ${allQuarantineItems.length} violations — classifying by type...`
        ]);
      }

      if (stage === 'fixing') {
        // Calculate fix counts first
        const fixedNulls = Math.floor(originalNulls * 0.95);
        const fixedSchema = Math.floor(originalSchema * 0.95);
        const fixedOutliers = Math.floor(originalOutliers * 0.95);
        setAiFixedCounts({ nulls: fixedNulls, schema: fixedSchema, outliers: fixedOutliers });

        // Pick a random sample of up to 35 items to show as rolling log
        const sample = [...allQuarantineItems]
          .sort(() => 0.5 - Math.random())
          .slice(0, 35);

        const delayMs = Math.floor(duration / (sample.length + 1));
        for (const item of sample) {
          await new Promise(resolve => setTimeout(resolve, delayMs));
          const line = explainFix(item);
          setExplanations(prev => [...prev, line]);
          // Advance progress proportionally during fixing stage
          localProgress = Math.min(targetProgress, localProgress + (targetProgress - 40) / sample.length);
          setAiProgress(localProgress);
        }
        localProgress = targetProgress;
        setAiProgress(localProgress);
      } else {
        // Smooth progress animation for non-fixing stages
        const steps = 20;
        const stepSize = (targetProgress - localProgress) / steps;
        for (let i = 0; i < steps; i++) {
          await new Promise(resolve => setTimeout(resolve, duration / steps));
          localProgress = Math.min(targetProgress, localProgress + stepSize);
          setAiProgress(localProgress);
        }
      }

      if (stage === 'complete') {
        const total = Math.floor(allQuarantineItems.length * 0.95);
        const residual = allQuarantineItems.length - total;
        const ts = new Date().toLocaleTimeString('en-US', { hour12: false });
        setExplanations(prev => [
          ...prev,
          `[${ts}] ────────────────────────────────`,
          `[${ts}] ✨ ${total.toLocaleString()} issues resolved automatically`,
          `[${ts}] ⚠️  ${residual} residual issues → human review queue`,
          `[${ts}] 🎯 COMPLETE — quality score improved ~18%`
        ]);
      }
    }

    // Modal stays open — user dismisses via X button or clicking backdrop
  };

  // Filter quarantine items based on selected filter
  const allQuarantineItems = data?.quarantine || [];
  const filteredQuarantineItems = allQuarantineItems.filter((item: any) => {
    if (selectedFilter === 'all') return true;
    // Use issue_type field for accurate filtering
    if (selectedFilter === 'nulls') return item.issue_type === 'null';
    if (selectedFilter === 'outliers') return item.issue_type === 'outlier';
    if (selectedFilter === 'schema') return item.issue_type === 'schema';
    return true;
  });
  
  const totalPages = Math.max(1, Math.ceil(filteredQuarantineItems.length / itemsPerPage));
  const currentItems = filteredQuarantineItems.slice((currentPage - 1) * itemsPerPage, currentPage * itemsPerPage);

  // Calculate displayed values based on whether AI fixes have been applied
  const originalNulls = data?.issues?.nulls || 0;
  const originalOutliers = data?.issues?.outliers || 0;
  const originalSchema = data?.issues?.schema_mismatch || 0;
  
  const nulls = aiApplied ? Math.ceil(originalNulls * 0.05) : originalNulls;
  const outliers = aiApplied ? Math.ceil(originalOutliers * 0.05) : originalOutliers;
  const schema_mismatch = aiApplied ? Math.ceil(originalSchema * 0.05) : originalSchema;
  const score = data?.score || 100;

  // Calculate quality scores for each dataset (simulated based on known error rates)
  const datasetQuality = {
    customers: 91.4,      // 8.6% issues
    smartMeters: 93.7,    // 6.3% issues
    meterReadings: 92.9,  // 7.1% issues
    gridSensors: 100.0,   // 0% issues
    sensorReadings: 75.2, // 24.8% issues
    billing: 24.0,        // 76% issues
    weather: 69.2         // 30.8% issues
  };

  return (
    <div className="pb-12">
      {/* Header Section */}
      <div className="mb-section-gap flex justify-between items-end">
        <div>
          <h3 className="font-headline-md text-headline-md text-primary mb-1">Data Quality Lab</h3>
          <p className="font-body-md text-on-surface-variant max-w-2xl">
            Deep dive into data quality across all pipelines. Analyzing {data?.total_records_analyzed?.toLocaleString() || '0'} records.
          </p>
        </div>
        <div className="flex items-center gap-2 px-3 py-1.5 bg-surface-container-high rounded border border-outline-variant">
          <span className="material-symbols-outlined text-label-md">calendar_today</span>
          <span className="font-label-md text-label-md">Last 24 Hours</span>
        </div>
      </div>

      {/* Metrics Bento Grid - Clickable to filter quarantine */}
      <div className="grid grid-cols-1 md:grid-cols-4 gap-gutter mb-section-gap">
        <button
          onClick={() => { setSelectedFilter('nulls'); setCurrentPage(1); }}
          className={`bg-surface/70 backdrop-blur border-2 p-card-padding rounded-xl shadow-sm text-left transition-all hover:shadow-lg hover:scale-105 ${selectedFilter === 'nulls' ? 'border-amber-500 ring-2 ring-amber-200' : 'border-outline-variant'} ${aiApplied ? 'border-emerald-500' : ''}`}
        >
          <div className="flex justify-between items-start mb-4">
            <span className="font-label-md text-label-md text-on-surface-variant">Null Rate</span>
            <span className={`px-2 py-1 text-xs font-bold rounded ${aiApplied ? 'bg-emerald-100 text-emerald-700' : nulls > 500 ? 'bg-amber-100 text-amber-700' : 'bg-emerald-100 text-emerald-700'}`}>
              {aiApplied ? '🤖 AI Fixed' : nulls > 500 ? 'Warning' : 'Low'}
            </span>
          </div>
          <div className="flex items-baseline gap-2">
            <span className="font-display-lg text-display-lg text-primary">{nulls.toLocaleString()}</span>
            <span className="text-on-surface-variant text-body-sm">Count</span>
            {aiApplied && <span className="text-xs text-emerald-600 font-bold">↓95%</span>}
          </div>
          <div className="mt-4 h-1 w-full bg-surface-container rounded-full overflow-hidden">
            <div className={`h-full ${aiApplied ? 'bg-emerald-500' : nulls > 500 ? 'bg-amber-500' : 'bg-secondary'}`} style={{ width: `${Math.min(100, (nulls / 1000) * 100)}%` }}></div>
          </div>
          <div className="mt-2 space-y-0.5">
            <p className="text-xs text-on-surface-variant">
              ⏱️ Time to fix: <span className="font-semibold">{Math.ceil(nulls / 60)} hrs</span> <span className="opacity-60">(1 hr per 60 errors)</span>
            </p>
            <p className="text-xs text-on-surface-variant">
              💰 Cost to fix: <span className={`font-semibold ${aiApplied ? 'text-emerald-700' : 'text-amber-700'}`}>${(Math.ceil(nulls / 60) * 36).toLocaleString()}</span> <span className="opacity-60">(@$36/hr)</span>
            </p>
            {aiApplied && (
              <p className="text-xs text-emerald-600 font-bold">✨ Saved ${(Math.ceil(originalNulls / 60) * 36 * 0.95).toLocaleString()} with AI</p>
            )}
          </div>
          {selectedFilter === 'nulls' && (
            <p className="mt-1 text-xs text-primary font-bold">✓ Filtering quarantine</p>
          )}
        </button>
        
        <button
          onClick={() => { setSelectedFilter('schema'); setCurrentPage(1); }}
          className={`bg-surface/70 backdrop-blur border-2 p-card-padding rounded-xl shadow-sm text-left transition-all hover:shadow-lg hover:scale-105 ${selectedFilter === 'schema' ? 'border-amber-500 ring-2 ring-amber-200' : 'border-outline-variant'} ${aiApplied ? 'border-emerald-500' : ''}`}
        >
          <div className="flex justify-between items-start mb-4">
            <span className="font-label-md text-label-md text-on-surface-variant">Schema Drift</span>
            <span className={`px-2 py-1 text-xs font-bold rounded ${aiApplied ? 'bg-emerald-100 text-emerald-700' : schema_mismatch > 200 ? 'bg-amber-100 text-amber-700' : 'bg-emerald-100 text-emerald-700'}`}>
              {aiApplied ? '🤖 AI Fixed' : schema_mismatch > 200 ? 'Warning' : 'Normal'}
            </span>
          </div>
          <div className="flex items-baseline gap-2">
            <span className="font-display-lg text-display-lg text-primary">{schema_mismatch.toLocaleString()}</span>
            <span className="text-amber-600 text-body-sm font-mono-data">ALERTS</span>
            {aiApplied && <span className="text-xs text-emerald-600 font-bold">↓95%</span>}
          </div>
          <div className="mt-4 flex gap-1">
            {[...Array(5)].map((_, i) => (
              <span key={i} className={`w-2 h-2 rounded-full ${aiApplied ? 'bg-emerald-500' : i < Math.min(5, Math.floor(schema_mismatch / 100)) ? 'bg-amber-500' : 'bg-surface-container'}`}></span>
            ))}
          </div>
          <div className="mt-2 space-y-0.5">
            <p className="text-xs text-on-surface-variant">
              ⏱️ Time to fix: <span className="font-semibold">{Math.ceil(schema_mismatch / 20)} hrs</span> <span className="opacity-60">(3 hrs per 60 errors)</span>
            </p>
            <p className="text-xs text-on-surface-variant">
              💰 Cost to fix: <span className={`font-semibold ${aiApplied ? 'text-emerald-700' : 'text-amber-700'}`}>${(Math.ceil(schema_mismatch / 20) * 36).toLocaleString()}</span> <span className="opacity-60">(@$36/hr)</span>
            </p>
            {aiApplied && (
              <p className="text-xs text-emerald-600 font-bold">✨ Saved ${(Math.ceil(originalSchema / 20) * 36 * 0.95).toLocaleString()} with AI</p>
            )}
          </div>
          {selectedFilter === 'schema' && (
            <p className="mt-1 text-xs text-primary font-bold">✓ Filtering quarantine</p>
          )}
        </button>
        
        <button
          onClick={() => { setSelectedFilter('outliers'); setCurrentPage(1); }}
          className={`bg-surface/70 backdrop-blur border-2 p-card-padding rounded-xl shadow-sm text-left transition-all hover:shadow-lg hover:scale-105 ${selectedFilter === 'outliers' ? 'border-error ring-2 ring-error/20' : 'border-outline-variant'} ${aiApplied ? 'border-emerald-500' : ''}`}
        >
          <div className="flex justify-between items-start mb-4">
            <span className="font-label-md text-label-md text-on-surface-variant">Outliers</span>
            <span className={`px-2 py-1 text-xs font-bold rounded ${aiApplied ? 'bg-emerald-100 text-emerald-700' : outliers > 400 ? 'bg-error-container text-on-error-container' : 'bg-surface-container-high text-on-surface-variant'}`}>
              {aiApplied ? '🤖 AI Fixed' : outliers > 400 ? 'High' : 'Normal'}
            </span>
          </div>
          <div className="flex items-baseline gap-2">
            <span className="font-display-lg text-display-lg text-primary">{outliers.toLocaleString()}</span>
            <span className="text-on-surface-variant text-body-sm">Detected</span>
            {aiApplied && <span className="text-xs text-emerald-600 font-bold">↓95%</span>}
          </div>
          <div className="mt-4 h-1 w-full bg-surface-container rounded-full overflow-hidden">
            <div className={`h-full ${aiApplied ? 'bg-emerald-500' : 'bg-primary'}`} style={{ width: `${Math.min(100, (outliers / 1000) * 100)}%` }}></div>
          </div>
          <div className="mt-2 space-y-0.5">
            <p className="text-xs text-on-surface-variant">
              ⏱️ Time to fix: <span className="font-semibold">{Math.ceil(outliers / 15)} hrs</span> <span className="opacity-60">(4 hrs per 60 errors)</span>
            </p>
            <p className="text-xs text-on-surface-variant">
              💰 Cost to fix: <span className={`font-semibold ${aiApplied ? 'text-emerald-700' : 'text-amber-700'}`}>${(Math.ceil(outliers / 15) * 36).toLocaleString()}</span> <span className="opacity-60">(@$36/hr)</span>
            </p>
            {aiApplied && (
              <p className="text-xs text-emerald-600 font-bold">✨ Saved ${(Math.ceil(originalOutliers / 15) * 36 * 0.95).toLocaleString()} with AI</p>
            )}
          </div>
          {selectedFilter === 'outliers' && (
            <p className="mt-1 text-xs text-primary font-bold">✓ Filtering quarantine</p>
          )}
        </button>
        
        <button
          onClick={() => { setSelectedFilter('all'); setCurrentPage(1); }}
          className={`bg-surface/70 backdrop-blur border-2 p-card-padding rounded-xl shadow-sm text-left transition-all hover:shadow-lg hover:scale-105 ${selectedFilter === 'all' ? 'border-primary ring-2 ring-primary/20' : 'border-outline-variant'} ${aiApplied ? 'border-emerald-500' : ''}`}
        >
          <div className="flex justify-between items-start mb-4">
            <span className="font-label-md text-label-md text-on-surface-variant">Total Error Count</span>
            <span className={`px-2 py-1 text-xs font-bold rounded ${aiApplied ? 'bg-emerald-100 text-emerald-700' : score < 90 ? 'bg-error-container text-on-error-container' : 'bg-emerald-100 text-emerald-700'}`}>
              {aiApplied ? '🤖 AI Fixed' : score < 90 ? 'Critical' : 'Good'}
            </span>
          </div>
          <div className="flex items-baseline gap-2">
            <span className="font-display-lg text-display-lg text-primary">{(nulls + outliers + schema_mismatch).toLocaleString()}</span>
            <span className="text-error text-body-sm">Issues</span>
            {aiApplied && <span className="text-xs text-emerald-600 font-bold">↓95%</span>}
          </div>
          <div className="mt-4 h-1 w-full bg-error-container/50 rounded-full overflow-hidden">
            <div className={`h-full ${aiApplied ? 'bg-emerald-500' : 'bg-error'}`} style={{ width: `${Math.max(5, 100 - score)}%` }}></div>
          </div>
          <div className="mt-2 space-y-0.5">
            <p className="text-xs text-on-surface-variant">
              ⏱️ Total time to fix: <span className="font-semibold">{Math.ceil(nulls / 60 + schema_mismatch / 20 + outliers / 15)} hrs</span>
            </p>
            <p className="text-xs text-on-surface-variant">
              💰 Total cost: <span className={`font-semibold ${aiApplied ? 'text-emerald-700' : 'text-error'}`}>${(Math.ceil(nulls / 60 + schema_mismatch / 20 + outliers / 15) * 36).toLocaleString()}</span> <span className="opacity-60">(@$36/hr)</span>
            </p>
            {aiApplied && (
              <p className="text-xs text-emerald-600 font-bold">✨ Total saved: ${(Math.ceil(originalNulls / 60 + originalSchema / 20 + originalOutliers / 15) * 36 * 0.95).toLocaleString()} with AI</p>
            )}
          </div>
          {selectedFilter === 'all' && (
            <p className="mt-1 text-xs text-primary font-bold">✓ Showing all issues</p>
          )}
        </button>
      </div>

      {/* Dataset Quality Overview */}
      <div className="mb-section-gap">
        <h3 className="font-headline-sm text-headline-sm text-primary mb-4">Quality by Dataset</h3>
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-gutter">
          {/* Customers */}
          <div className="bg-surface/70 backdrop-blur border border-outline-variant rounded-xl p-card-padding hover:shadow-lg transition-shadow">
            <div className="flex items-center justify-between mb-3">
              <div className="flex items-center gap-2">
                <span className="material-symbols-outlined text-primary">person</span>
                <h4 className="font-label-lg font-bold">Customers</h4>
              </div>
              <span className={`px-2 py-0.5 text-xs font-bold rounded ${datasetQuality.customers > 90 ? 'bg-emerald-100 text-emerald-700' : 'bg-amber-100 text-amber-700'}`}>
                {datasetQuality.customers.toFixed(1)}%
              </span>
            </div>
            <p className="text-body-sm text-on-surface-variant mb-3">{datasetStats.customers?.toLocaleString() || '0'} records</p>
            <div className="w-full bg-surface-container h-2 rounded-full overflow-hidden">
              <div className={`h-full ${datasetQuality.customers > 90 ? 'bg-emerald-500' : 'bg-amber-500'}`} style={{ width: `${datasetQuality.customers}%` }}></div>
            </div>
            <p className="text-xs text-on-surface-variant mt-2">~431 issues (8.6%)</p>
          </div>

          {/* Smart Meters */}
          <div className="bg-surface/70 backdrop-blur border border-outline-variant rounded-xl p-card-padding hover:shadow-lg transition-shadow">
            <div className="flex items-center justify-between mb-3">
              <div className="flex items-center gap-2">
                <span className="material-symbols-outlined text-primary">sensors</span>
                <h4 className="font-label-lg font-bold">Smart Meters</h4>
              </div>
              <span className={`px-2 py-0.5 text-xs font-bold rounded ${datasetQuality.smartMeters > 90 ? 'bg-emerald-100 text-emerald-700' : 'bg-amber-100 text-amber-700'}`}>
                {datasetQuality.smartMeters.toFixed(1)}%
              </span>
            </div>
            <p className="text-body-sm text-on-surface-variant mb-3">{datasetStats.meters?.toLocaleString() || '0'} records</p>
            <div className="w-full bg-surface-container h-2 rounded-full overflow-hidden">
              <div className={`h-full ${datasetQuality.smartMeters > 90 ? 'bg-emerald-500' : 'bg-amber-500'}`} style={{ width: `${datasetQuality.smartMeters}%` }}></div>
            </div>
            <p className="text-xs text-on-surface-variant mt-2">~313 issues (6.3%)</p>
          </div>

          {/* Meter Readings */}
          <div className="bg-surface/70 backdrop-blur border border-outline-variant rounded-xl p-card-padding hover:shadow-lg transition-shadow">
            <div className="flex items-center justify-between mb-3">
              <div className="flex items-center gap-2">
                <span className="material-symbols-outlined text-primary">bolt</span>
                <h4 className="font-label-lg font-bold">Meter Readings</h4>
              </div>
              <span className={`px-2 py-0.5 text-xs font-bold rounded ${datasetQuality.meterReadings > 90 ? 'bg-emerald-100 text-emerald-700' : 'bg-amber-100 text-amber-700'}`}>
                {datasetQuality.meterReadings.toFixed(1)}%
              </span>
            </div>
            <p className="text-body-sm text-on-surface-variant mb-3">{datasetStats.readings?.toLocaleString() || '0'} records</p>
            <div className="w-full bg-surface-container h-2 rounded-full overflow-hidden">
              <div className={`h-full ${datasetQuality.meterReadings > 90 ? 'bg-emerald-500' : 'bg-amber-500'}`} style={{ width: `${datasetQuality.meterReadings}%` }}></div>
            </div>
            <p className="text-xs text-on-surface-variant mt-2">~708 issues (7.1%)</p>
          </div>

          {/* Grid Sensors */}
          <div className="bg-surface/70 backdrop-blur border border-outline-variant rounded-xl p-card-padding hover:shadow-lg transition-shadow">
            <div className="flex items-center justify-between mb-3">
              <div className="flex items-center gap-2">
                <span className="material-symbols-outlined text-primary">router</span>
                <h4 className="font-label-lg font-bold">Grid Sensors</h4>
              </div>
              <span className="px-2 py-0.5 text-xs font-bold rounded bg-emerald-100 text-emerald-700">
                {datasetQuality.gridSensors.toFixed(1)}%
              </span>
            </div>
            <p className="text-body-sm text-on-surface-variant mb-3">{datasetStats.sensors?.toLocaleString() || '0'} records</p>
            <div className="w-full bg-surface-container h-2 rounded-full overflow-hidden">
              <div className="h-full bg-emerald-500" style={{ width: `${datasetQuality.gridSensors}%` }}></div>
            </div>
            <p className="text-xs text-emerald-600 mt-2">✓ Clean data (0%)</p>
          </div>

          {/* Sensor Readings */}
          <div className="bg-surface/70 backdrop-blur border border-outline-variant rounded-xl p-card-padding hover:shadow-lg transition-shadow">
            <div className="flex items-center justify-between mb-3">
              <div className="flex items-center gap-2">
                <span className="material-symbols-outlined text-primary">monitoring</span>
                <h4 className="font-label-lg font-bold">Sensor Readings</h4>
              </div>
              <span className="px-2 py-0.5 text-xs font-bold rounded bg-error-container text-on-error-container">
                {datasetQuality.sensorReadings.toFixed(1)}%
              </span>
            </div>
            <p className="text-body-sm text-on-surface-variant mb-3">{datasetStats.sensorReadings?.toLocaleString() || '0'} records</p>
            <div className="w-full bg-surface-container h-2 rounded-full overflow-hidden">
              <div className="h-full bg-error" style={{ width: `${datasetQuality.sensorReadings}%` }}></div>
            </div>
            <p className="text-xs text-error mt-2">~1,981 issues (24.8%)</p>
          </div>

          {/* Billing Records */}
          <div className="bg-surface/70 backdrop-blur border border-outline-variant rounded-xl p-card-padding hover:shadow-lg transition-shadow">
            <div className="flex items-center justify-between mb-3">
              <div className="flex items-center gap-2">
                <span className="material-symbols-outlined text-primary">receipt_long</span>
                <h4 className="font-label-lg font-bold">Billing Records</h4>
              </div>
              <span className="px-2 py-0.5 text-xs font-bold rounded bg-error-container text-on-error-container">
                {datasetQuality.billing.toFixed(1)}%
              </span>
            </div>
            <p className="text-body-sm text-on-surface-variant mb-3">{datasetStats.billing?.toLocaleString() || '0'} records</p>
            <div className="w-full bg-surface-container h-2 rounded-full overflow-hidden">
              <div className="h-full bg-error" style={{ width: `${datasetQuality.billing}%` }}></div>
            </div>
            <p className="text-xs text-error mt-2">~3,800 issues (76%)</p>
          </div>

          {/* Weather Data */}
          <div className="bg-surface/70 backdrop-blur border border-outline-variant rounded-xl p-card-padding hover:shadow-lg transition-shadow">
            <div className="flex items-center justify-between mb-3">
              <div className="flex items-center gap-2">
                <span className="material-symbols-outlined text-primary">cloud</span>
                <h4 className="font-label-lg font-bold">Weather Data</h4>
              </div>
              <span className="px-2 py-0.5 text-xs font-bold rounded bg-amber-100 text-amber-700">
                {datasetQuality.weather.toFixed(1)}%
              </span>
            </div>
            <p className="text-body-sm text-on-surface-variant mb-3">{datasetStats.weather?.toLocaleString() || '0'} records</p>
            <div className="w-full bg-surface-container h-2 rounded-full overflow-hidden">
              <div className="h-full bg-amber-500" style={{ width: `${datasetQuality.weather}%` }}></div>
            </div>
            <p className="text-xs text-amber-600 mt-2">~616 issues (30.8%)</p>
          </div>

          {/* Overall Summary */}
          <div className="bg-primary text-on-primary rounded-xl p-card-padding hover:shadow-lg transition-shadow">
            <div className="flex items-center justify-between mb-3">
              <div className="flex items-center gap-2">
                <span className="material-symbols-outlined">analytics</span>
                <h4 className="font-label-lg font-bold">Overall Quality</h4>
              </div>
              <span className="px-2 py-0.5 text-xs font-bold rounded bg-white/20">
                {score.toFixed(1)}%
              </span>
            </div>
            <p className="text-body-sm opacity-80 mb-3">{data?.total_records_analyzed?.toLocaleString() || '0'} total records</p>
            <div className="w-full bg-white/20 h-2 rounded-full overflow-hidden">
              <div className="h-full bg-white" style={{ width: `${score}%` }}></div>
            </div>
            <p className="text-xs opacity-80 mt-2">~{(nulls + outliers + schema_mismatch).toLocaleString()} total issues</p>
          </div>
        </div>
      </div>

      {/* AI Fixes Button */}
      <div className="mb-section-gap">
        <button
          onClick={handleAIFix}
          className="group relative px-8 py-4 bg-gradient-to-r from-purple-600 to-blue-600 text-white rounded-xl shadow-lg hover:shadow-xl transition-all hover:scale-105 flex items-center gap-3"
        >
          <span className="material-symbols-outlined text-2xl">auto_awesome</span>
          <div className="text-left">
            <div className="font-headline-sm text-headline-sm">Run AI Fixes</div>
            <div className="text-xs opacity-90">Identify common data issues and fix them</div>
          </div>
          <span className="material-symbols-outlined text-2xl group-hover:translate-x-1 transition-transform">arrow_forward</span>
        </button>
      </div>

      {/* Comparison & Charts Section */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-gutter mb-section-gap">
        {/* Transformation Preview - HIDDEN (may use later) */}
        {/* <div className="lg:col-span-2 bg-surface/70 backdrop-blur rounded-xl border border-outline-variant flex flex-col">
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
  "customer_id": "CUST-10034",
  "email": "invalid.email.format",
  "phone": "123-INVALID",
  "zip_code": "ABCDE",
  "state": "XX",
  "amount_due": -50.00,
  "status": "TRUE"
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
  "customer_id": "CUST-10034",
  "email": "fixed_CUST-10034@example.com",
  "phone": "+1-555-0100",
  "zip_code": "10001",
  "state": "CA",
  "amount_due": 50.00,
  "status": "PENDING"
}`}
              </pre>
            </div>
          </div>
        </div> */}

        {/* Issue Distribution Chart - HIDDEN (may use later) */}
        {/* <div className="bg-surface/70 backdrop-blur rounded-xl border border-outline-variant p-card-padding">
          <h4 className="font-headline-sm text-headline-sm text-primary mb-6">Issue Distribution</h4>
          <div className="space-y-6">
            <div>
              <div className="flex justify-between mb-2">
                <span className="font-label-md text-on-surface">NULL Values</span>
                <span className="font-mono-data text-on-surface-variant">{nulls}</span>
              </div>
              <div className="h-6 w-full bg-surface-container rounded overflow-hidden">
                <div className="h-full bg-amber-500 transition-all" style={{ width: `${Math.min(100, (nulls / (nulls + outliers + schema_mismatch)) * 100)}%` }}></div>
              </div>
            </div>
            <div>
              <div className="flex justify-between mb-2">
                <span className="font-label-md text-on-surface">Outliers</span>
                <span className="font-mono-data text-on-surface-variant">{outliers}</span>
              </div>
              <div className="h-6 w-full bg-surface-container rounded overflow-hidden">
                <div className="h-full bg-error transition-all" style={{ width: `${Math.min(100, (outliers / (nulls + outliers + schema_mismatch)) * 100)}%` }}></div>
              </div>
            </div>
            <div>
              <div className="flex justify-between mb-2">
                <span className="font-label-md text-on-surface">Schema Issues</span>
                <span className="font-mono-data text-on-surface-variant">{schema_mismatch}</span>
              </div>
              <div className="h-6 w-full bg-surface-container rounded overflow-hidden">
                <div className="h-full bg-secondary transition-all" style={{ width: `${Math.min(100, (schema_mismatch / (nulls + outliers + schema_mismatch)) * 100)}%` }}></div>
              </div>
            </div>
          </div>
        </div> */}
      </div>

      {/* Horizontal Divider */}
      <div className="my-8 border-t border-outline-variant"></div>

      {/* Quarantine Table */}
      <div className="bg-surface/70 backdrop-blur rounded-xl border border-outline-variant overflow-hidden">
        <div
          className="p-card-padding border-b border-outline-variant flex justify-between items-center bg-surface-container-low cursor-pointer hover:bg-surface-container-low/80 transition-colors"
          onClick={() => setIsQuarantineCollapsed(!isQuarantineCollapsed)}
        >
          <div className="flex items-center gap-3">
            <span className="material-symbols-outlined text-primary transition-transform" style={{ transform: isQuarantineCollapsed ? 'rotate(-90deg)' : 'rotate(0deg)' }}>
              expand_more
            </span>
            <div>
              <div className="flex items-center gap-3 mb-1">
                <h4 className="font-headline-sm text-headline-sm text-primary">Quarantine Management</h4>
                {selectedFilter !== 'all' && (
                  <span className="px-3 py-1 bg-primary text-on-primary text-xs font-bold rounded-full flex items-center gap-1">
                    <span className="material-symbols-outlined text-sm">filter_alt</span>
                    {selectedFilter === 'nulls' ? 'NULL Values' : selectedFilter === 'outliers' ? 'Outliers' : 'Schema Issues'}
                  </span>
                )}
              </div>
              <p className="font-body-sm text-on-surface-variant">
                {selectedFilter === 'all'
                  ? 'Sample records that failed validation and require manual attention.'
                  : `Showing ${filteredQuarantineItems.length} records with ${selectedFilter === 'nulls' ? 'NULL values' : selectedFilter === 'outliers' ? 'outlier' : 'schema'} issues. Click "Total Error Count" to see all.`
                }
              </p>
            </div>
          </div>
          <button
            onClick={(e) => {
              e.stopPropagation();
              handlePurge();
            }}
            disabled={isPurging || allQuarantineItems.length === 0}
            className={`px-4 py-2 text-on-error rounded font-label-md flex items-center gap-2 transition-opacity ${isPurging || allQuarantineItems.length === 0 ? 'bg-error/50 cursor-not-allowed' : 'bg-error hover:opacity-90'}`}
          >
            <span className={`material-symbols-outlined text-[18px] ${isPurging ? 'animate-spin' : ''}`}>
              {isPurging ? 'refresh' : 'delete_sweep'}
            </span>
            {isPurging ? 'Purging...' : 'Purge All Failures'}
          </button>
        </div>
        {!isQuarantineCollapsed && (
          <>
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
              {currentItems.map((item: any, i: number) => (
                <tr key={i} className="hover:bg-surface-container-low/50 transition-colors">
                  <td className="px-6 py-4 font-mono-data text-primary">{item.id}</td>
                  <td className="px-6 py-4 font-body-sm">{item.source}</td>
                  <td className="px-6 py-4">
                    <span className={`px-2 py-0.5 text-xs font-semibold rounded ${item.severity === 'Critical' ? 'bg-error-container text-on-error-container' : item.severity === 'High' ? 'bg-amber-100 text-amber-700' : 'bg-surface-container-high text-on-surface-variant'}`}>
                      {item.issue}
                    </span>
                  </td>
                  <td className="px-6 py-4 font-mono-data text-on-surface-variant">{item.timestamp?.split('T')[0] || 'N/A'}</td>
                  <td className="px-6 py-4 text-right">
                    <div className="flex justify-end gap-3">
                      <button
                        onClick={() => handleViewLineage(item)}
                        className="text-primary hover:underline font-label-sm flex items-center gap-1"
                      >
                        <span className="material-symbols-outlined text-sm">account_tree</span>
                        View Lineage
                      </button>
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
             <span className="font-body-sm text-on-surface-variant">
               Showing {currentItems.length > 0 ? (currentPage - 1) * itemsPerPage + 1 : 0} - {Math.min(currentPage * itemsPerPage, filteredQuarantineItems.length)} of {filteredQuarantineItems.length} filtered records
               {selectedFilter !== 'all' && ` (${allQuarantineItems.length} total)`}
             </span>
             <div className="flex gap-2 items-center">
               <span className="text-xs text-on-surface-variant mr-2">Page {currentPage} of {totalPages}</span>
               <button
                 onClick={() => setCurrentPage(p => Math.max(1, p - 1))}
                 disabled={currentPage === 1}
                 className="p-1 flex items-center justify-center border border-outline-variant rounded hover:bg-surface-container transition-colors disabled:opacity-50"
               >
                 <span className="material-symbols-outlined">chevron_left</span>
               </button>
               <button
                 onClick={() => setCurrentPage(p => Math.min(totalPages, p + 1))}
                 disabled={currentPage === totalPages}
                 className="p-1 flex items-center justify-center border border-outline-variant rounded hover:bg-surface-container transition-colors disabled:opacity-50"
               >
                 <span className="material-symbols-outlined">chevron_right</span>
               </button>
             </div>
           </div>
         </>
       )}
      </div>

      {/* AI Fixes Modal */}
      {showAIModal && (
        <div
          className="fixed inset-0 bg-black/50 backdrop-blur-sm flex items-center justify-center z-50 p-4"
          onClick={() => { setShowAIModal(false); setAiFixStage('idle'); setAiProgress(0); }}
        >
          <div className="bg-surface rounded-2xl shadow-2xl max-w-4xl w-full max-h-[90vh] overflow-auto" onClick={e => e.stopPropagation()}>
            {/* Modal Header */}
            <div className="p-6 border-b border-outline-variant bg-gradient-to-r from-purple-600 to-blue-600 text-white rounded-t-2xl">
              <div className="flex items-center justify-between">
                <div className="flex items-center gap-3">
                  <span className="material-symbols-outlined text-3xl">auto_awesome</span>
                  <div>
                    <h3 className="font-headline-md text-headline-md">AI-Powered Data Quality Remediation</h3>
                    <p className="text-sm opacity-90 mt-1">Automated identification and correction of data quality issues</p>
                  </div>
                </div>
                {aiFixStage === 'complete' && (
                  <button
                    onClick={() => setShowAIModal(false)}
                    className="p-2 hover:bg-white/20 rounded-full transition-colors"
                  >
                    <span className="material-symbols-outlined">close</span>
                  </button>
                )}
              </div>
            </div>

            {/* Modal Body */}
            <div className="p-8">
              {/* Progress Bar */}
              <div className="mb-6">
                <div className="flex justify-between items-center mb-2">
                  <span className="font-label-lg text-on-surface">Processing Progress</span>
                  <span className="font-mono-data text-primary font-bold">{Math.round(aiProgress)}%</span>
                </div>
                <div className="w-full h-3 bg-surface-container rounded-full overflow-hidden">
                  <div
                    className="h-full bg-gradient-to-r from-purple-600 to-blue-600 transition-all duration-300 ease-out"
                    style={{ width: `${aiProgress}%` }}
                  ></div>
                </div>
              </div>

              {/* AI Decision Log — terminal style, visible from 'identifying' stage onwards */}
              {explanations.length > 0 && (
                <div className="mb-6">
                  <h4 className="font-label-lg font-bold text-on-surface mb-2 flex items-center gap-2">
                    <span className="material-symbols-outlined text-lg text-purple-500">terminal</span>
                    AI Decision Log
                  </h4>
                  <div className="bg-gray-950 rounded-lg p-4 font-mono text-[12px] leading-relaxed max-h-44 overflow-y-auto border border-purple-900/40 shadow-inner">
                    <p className="text-purple-400 mb-1 select-none">$ voltstream-ai --mode=remediate --confidence=0.95</p>
                    {explanations.map((line, i) => {
                      const isHeader = line.includes('🔍') || line.includes('ENGINE');
                      const isComplete = line.includes('COMPLETE') || line.includes('✨') || line.includes('⚠️') || line.includes('────');
                      const isNull = line.includes('null') && !isHeader && !isComplete;
                      const isOutlier = line.includes('outlier') && !isHeader && !isComplete;
                      return (
                        <p key={i} className={`mb-0.5 ${
                          isHeader ? 'text-purple-400' :
                          isComplete ? 'text-emerald-400 font-bold' :
                          isNull ? 'text-amber-400' :
                          isOutlier ? 'text-red-400' :
                          'text-blue-300'
                        }`}>{line}</p>
                      );
                    })}
                    <div ref={explanationsEndRef} />
                  </div>
                </div>
              )}

              {/* ETL Processing Flow */}
              <div className="mb-8">
                <h4 className="font-headline-sm text-headline-sm text-primary mb-6">AI Processing Pipeline</h4>
                <div className="flex items-center justify-between gap-4">
                  {/* Stage 1: Analyzing */}
                  <div className="flex-1">
                    <div className={`relative rounded-xl p-6 transition-all ${aiFixStage === 'analyzing' ? 'bg-primary text-on-primary shadow-lg scale-105' : 'bg-surface-container text-on-surface-variant'}`}>
                      <div className="flex flex-col items-center text-center">
                        <span className="material-symbols-outlined text-4xl mb-2">search</span>
                        <h5 className="font-label-lg font-bold mb-1">Analyzing</h5>
                        <p className="text-xs opacity-80">Scanning datasets</p>
                        {aiFixStage === 'analyzing' && (
                          <div className="mt-2 flex gap-1">
                            <span className="w-2 h-2 bg-current rounded-full animate-pulse"></span>
                            <span className="w-2 h-2 bg-current rounded-full animate-pulse" style={{ animationDelay: '0.2s' }}></span>
                            <span className="w-2 h-2 bg-current rounded-full animate-pulse" style={{ animationDelay: '0.4s' }}></span>
                          </div>
                        )}
                        {['identifying', 'fixing', 'validating', 'complete'].includes(aiFixStage) && (
                          <span className="mt-2 text-emerald-600 font-bold text-xs">✓ DONE</span>
                        )}
                      </div>
                    </div>
                  </div>

                  <span className="material-symbols-outlined text-outline-variant">arrow_forward</span>

                  {/* Stage 2: Identifying */}
                  <div className="flex-1">
                    <div className={`relative rounded-xl p-6 transition-all ${aiFixStage === 'identifying' ? 'bg-primary text-on-primary shadow-lg scale-105' : 'bg-surface-container text-on-surface-variant'}`}>
                      <div className="flex flex-col items-center text-center">
                        <span className="material-symbols-outlined text-4xl mb-2">bug_report</span>
                        <h5 className="font-label-lg font-bold mb-1">Identifying</h5>
                        <p className="text-xs opacity-80">Detecting issues</p>
                        {aiFixStage === 'identifying' && (
                          <div className="mt-2 flex gap-1">
                            <span className="w-2 h-2 bg-current rounded-full animate-pulse"></span>
                            <span className="w-2 h-2 bg-current rounded-full animate-pulse" style={{ animationDelay: '0.2s' }}></span>
                            <span className="w-2 h-2 bg-current rounded-full animate-pulse" style={{ animationDelay: '0.4s' }}></span>
                          </div>
                        )}
                        {['fixing', 'validating', 'complete'].includes(aiFixStage) && (
                          <span className="mt-2 text-emerald-600 font-bold text-xs">✓ DONE</span>
                        )}
                      </div>
                    </div>
                  </div>

                  <span className="material-symbols-outlined text-outline-variant">arrow_forward</span>

                  {/* Stage 3: Fixing */}
                  <div className="flex-1">
                    <div className={`relative rounded-xl p-6 transition-all ${aiFixStage === 'fixing' ? 'bg-primary text-on-primary shadow-lg scale-105' : 'bg-surface-container text-on-surface-variant'}`}>
                      <div className="flex flex-col items-center text-center">
                        <span className="material-symbols-outlined text-4xl mb-2">build</span>
                        <h5 className="font-label-lg font-bold mb-1">Fixing</h5>
                        <p className="text-xs opacity-80">Applying corrections</p>
                        {aiFixStage === 'fixing' && (
                          <div className="mt-2 flex gap-1">
                            <span className="w-2 h-2 bg-current rounded-full animate-pulse"></span>
                            <span className="w-2 h-2 bg-current rounded-full animate-pulse" style={{ animationDelay: '0.2s' }}></span>
                            <span className="w-2 h-2 bg-current rounded-full animate-pulse" style={{ animationDelay: '0.4s' }}></span>
                          </div>
                        )}
                        {['validating', 'complete'].includes(aiFixStage) && (
                          <span className="mt-2 text-emerald-600 font-bold text-xs">✓ DONE</span>
                        )}
                      </div>
                    </div>
                  </div>

                  <span className="material-symbols-outlined text-outline-variant">arrow_forward</span>

                  {/* Stage 4: Validating */}
                  <div className="flex-1">
                    <div className={`relative rounded-xl p-6 transition-all ${aiFixStage === 'validating' ? 'bg-primary text-on-primary shadow-lg scale-105' : 'bg-surface-container text-on-surface-variant'}`}>
                      <div className="flex flex-col items-center text-center">
                        <span className="material-symbols-outlined text-4xl mb-2">verified</span>
                        <h5 className="font-label-lg font-bold mb-1">Validating</h5>
                        <p className="text-xs opacity-80">Quality checks</p>
                        {aiFixStage === 'validating' && (
                          <div className="mt-2 flex gap-1">
                            <span className="w-2 h-2 bg-current rounded-full animate-pulse"></span>
                            <span className="w-2 h-2 bg-current rounded-full animate-pulse" style={{ animationDelay: '0.2s' }}></span>
                            <span className="w-2 h-2 bg-current rounded-full animate-pulse" style={{ animationDelay: '0.4s' }}></span>
                          </div>
                        )}
                        {aiFixStage === 'complete' && (
                          <span className="mt-2 text-emerald-600 font-bold text-xs">✓ DONE</span>
                        )}
                      </div>
                    </div>
                  </div>

                  <span className="material-symbols-outlined text-outline-variant">arrow_forward</span>

                  {/* Stage 5: Complete */}
                  <div className="flex-1">
                    <div className={`relative rounded-xl p-6 transition-all ${aiFixStage === 'complete' ? 'bg-emerald-600 text-white shadow-lg scale-105' : 'bg-surface-container text-on-surface-variant'}`}>
                      <div className="flex flex-col items-center text-center">
                        <span className="material-symbols-outlined text-4xl mb-2">check_circle</span>
                        <h5 className="font-label-lg font-bold mb-1">Complete</h5>
                        <p className="text-xs opacity-80">Ready to deploy</p>
                        {aiFixStage === 'complete' && (
                          <span className="mt-2 font-bold text-xs">✓ SUCCESS</span>
                        )}
                      </div>
                    </div>
                  </div>
                </div>
              </div>

              {/* Results Summary */}
              {aiFixStage === 'complete' && (
                <div className="bg-emerald-50 border-2 border-emerald-200 rounded-xl p-6">
                  <div className="flex items-center gap-3 mb-4">
                    <span className="material-symbols-outlined text-3xl text-emerald-600">celebration</span>
                    <h4 className="font-headline-sm text-headline-sm text-emerald-900">AI Remediation Complete!</h4>
                  </div>
                  
                  <div className="grid grid-cols-3 gap-4 mb-6">
                    <div className="bg-white rounded-lg p-4 border border-emerald-200">
                      <div className="text-xs text-emerald-700 mb-1">Null Values Fixed</div>
                      <div className="font-display-md text-display-md text-emerald-900">{aiFixedCounts.nulls.toLocaleString()}</div>
                      <div className="text-xs text-emerald-600 mt-1">95% reduction</div>
                    </div>
                    <div className="bg-white rounded-lg p-4 border border-emerald-200">
                      <div className="text-xs text-emerald-700 mb-1">Schema Issues Fixed</div>
                      <div className="font-display-md text-display-md text-emerald-900">{aiFixedCounts.schema.toLocaleString()}</div>
                      <div className="text-xs text-emerald-600 mt-1">95% reduction</div>
                    </div>
                    <div className="bg-white rounded-lg p-4 border border-emerald-200">
                      <div className="text-xs text-emerald-700 mb-1">Outliers Fixed</div>
                      <div className="font-display-md text-display-md text-emerald-900">{aiFixedCounts.outliers.toLocaleString()}</div>
                      <div className="text-xs text-emerald-600 mt-1">95% reduction</div>
                    </div>
                  </div>

                  <div className="bg-white rounded-lg p-4 border border-emerald-200 mb-4">
                    <div className="flex justify-between items-center">
                      <div>
                        <div className="text-sm text-emerald-700 mb-1">Total Issues Resolved</div>
                        <div className="font-display-lg text-display-lg text-emerald-900">
                          {(aiFixedCounts.nulls + aiFixedCounts.schema + aiFixedCounts.outliers).toLocaleString()}
                        </div>
                      </div>
                      <div className="text-right">
                        <div className="text-sm text-emerald-700 mb-1">Cost Savings</div>
                        <div className="font-display-lg text-display-lg text-emerald-900">
                          ${(Math.ceil((aiFixedCounts.nulls / 60 + aiFixedCounts.schema / 20 + aiFixedCounts.outliers / 15) * 36)).toLocaleString()}
                        </div>
                        <div className="text-xs text-emerald-600">95% of manual cost</div>
                      </div>
                    </div>
                  </div>

                  <div className="flex gap-3">
                    <button
                      onClick={applyAIFixes}
                      className="flex-1 bg-emerald-600 text-white py-3 rounded-lg font-bold hover:bg-emerald-700 transition-colors"
                    >
                      Apply Changes
                    </button>
                    <button
                      onClick={() => setShowAIModal(false)}
                      className="px-6 bg-white text-emerald-700 py-3 rounded-lg font-bold border-2 border-emerald-200 hover:bg-emerald-50 transition-colors"
                    >
                      Review Details
                    </button>
                  </div>
                </div>
              )}

              {/* Processing Message */}
              {aiFixStage !== 'complete' && (
                <div className="text-center text-on-surface-variant">
                  <p className="text-sm">AI is analyzing and fixing data quality issues...</p>
                  <p className="text-xs mt-1 opacity-70">This process typically takes a few seconds</p>
                </div>
              )}
            </div>
          </div>
        </div>
      )}

      {/* Lineage Modal */}
      {showLineageModal && (
        <div
          className="fixed inset-0 bg-black/50 backdrop-blur-sm flex items-center justify-center z-50 p-4"
          onClick={() => setShowLineageModal(false)}
        >
          <div
            className="bg-white rounded-2xl shadow-2xl max-w-6xl w-full max-h-[90vh] overflow-hidden"
            onClick={(e) => e.stopPropagation()}
          >
            {/* Modal Header */}
            <div className="bg-gradient-to-r from-primary to-secondary p-6 text-white">
              <div className="flex justify-between items-start">
                <div>
                  <h3 className="font-headline-lg text-headline-lg mb-2">Data Lineage Analysis</h3>
                  <p className="text-sm opacity-90">
                    AI-powered visualization of data flow and failure point identification
                  </p>
                  {selectedRecord && (
                    <div className="mt-3 flex items-center gap-2 text-sm">
                      <span className="material-symbols-outlined text-base">badge</span>
                      <span className="font-mono-data">Record ID: {selectedRecord.id}</span>
                      <span className="mx-2">•</span>
                      <span>Source: {selectedRecord.source}</span>
                    </div>
                  )}
                </div>
                <button
                  onClick={() => setShowLineageModal(false)}
                  className="text-white hover:bg-white/20 rounded-full p-2 transition-colors"
                >
                  <span className="material-symbols-outlined">close</span>
                </button>
              </div>
            </div>

            {/* Modal Content */}
            <div className="p-8 overflow-y-auto max-h-[calc(90vh-180px)]">
              {lineageLoading ? (
                <div className="flex flex-col items-center justify-center py-16">
                  <div className="relative mb-8">
                    <div className="w-20 h-20 border-4 border-primary/20 border-t-primary rounded-full animate-spin"></div>
                    <span className="material-symbols-outlined absolute top-1/2 left-1/2 transform -translate-x-1/2 -translate-y-1/2 text-3xl text-primary">
                      account_tree
                    </span>
                  </div>
                  
                  <h4 className="font-headline-md text-headline-md text-primary mb-3">
                    Analyzing Data Lineage
                  </h4>
                  
                  <div className="max-w-md text-center space-y-2">
                    <p className="text-body-md text-on-surface">
                      Our AI is tracing the complete journey of your data record through the ETL pipeline...
                    </p>
                    <p className="text-body-sm text-on-surface-variant">
                      Identifying ingestion points, transformation stages, validation checkpoints, and pinpointing the exact failure location.
                    </p>
                  </div>

                  <div className="mt-8 flex items-center gap-2 text-sm text-on-surface-variant">
                    <span className="material-symbols-outlined text-base animate-pulse">schedule</span>
                    <span>This typically takes 2-4 seconds</span>
                  </div>

                  <div className="mt-6 flex gap-2">
                    <div className="w-2 h-2 bg-primary rounded-full animate-bounce" style={{ animationDelay: '0ms' }}></div>
                    <div className="w-2 h-2 bg-primary rounded-full animate-bounce" style={{ animationDelay: '150ms' }}></div>
                    <div className="w-2 h-2 bg-primary rounded-full animate-bounce" style={{ animationDelay: '300ms' }}></div>
                  </div>
                </div>
              ) : (
                <div>
                  <div className="mb-6 bg-primary/5 border border-primary/20 rounded-lg p-4">
                    <div className="flex items-start gap-3">
                      <span className="material-symbols-outlined text-primary text-2xl">info</span>
                      <div>
                        <h5 className="font-label-lg text-on-surface mb-1">Lineage Visualization Complete</h5>
                        <p className="text-body-sm text-on-surface-variant">
                          The diagram below shows the complete data flow from source to destination, highlighting where the record encountered issues during processing.
                        </p>
                      </div>
                    </div>
                  </div>

                  {/* SVG Lineage Diagram */}
                  <div className="bg-gray-50 rounded-xl p-6 border border-outline-variant overflow-x-auto">
                    <div dangerouslySetInnerHTML={{ __html: lineageSvg }} />
                  </div>
                </div>
              )}
            </div>

            {/* Modal Footer */}
            {!lineageLoading && (
              <div className="border-t border-outline-variant p-6 bg-surface-container-low flex justify-end gap-3">
                <button
                  onClick={() => setShowLineageModal(false)}
                  className="px-6 py-2 bg-white border border-outline-variant rounded-lg font-label-md hover:bg-surface-container transition-colors"
                >
                  Close
                </button>
                <button
                  onClick={() => {
                    // Create a blob from the SVG content
                    const blob = new Blob([lineageSvg], { type: 'image/svg+xml' });
                    const url = URL.createObjectURL(blob);
                    
                    // Create a temporary link and trigger download
                    const link = document.createElement('a');
                    link.href = url;
                    link.download = `lineage_${selectedRecord?.id || 'diagram'}_${new Date().getTime()}.svg`;
                    document.body.appendChild(link);
                    link.click();
                    document.body.removeChild(link);
                    
                    // Clean up the URL
                    URL.revokeObjectURL(url);
                  }}
                  className="px-6 py-2 bg-primary text-on-primary rounded-lg font-label-md hover:opacity-90 transition-opacity flex items-center gap-2"
                >
                  <span className="material-symbols-outlined text-sm">download</span>
                  Export Diagram
                </button>
              </div>
            )}
          </div>
        </div>
      )}
    </div>
  );
};

export default DataQualityLab;

// Made with Bob
