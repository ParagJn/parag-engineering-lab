import React, { createContext, useContext, useState } from 'react';
import type { ReactNode } from 'react';
import axios from 'axios';

interface SimulationSummary {
  totalRecordsProcessed: number;
  recordsByDataset: {
    customers: number;
    smartMeters: number;
    meterReadings: number;
    gridSensors: number;
    sensorReadings: number;
    billingRecords: number;
    weatherData: number;
  };
  issuesFound: {
    nulls: number;
    outliers: number;
    schemaMismatch: number;
  };
  issuesFixed: number;
  qualityScore: number;
  duration: string;
}

interface SimulationContextType {
  simStage: string;
  logs: string[];
  summary: SimulationSummary | null;
  triggerSimulation: () => Promise<void>;
}

const SimulationContext = createContext<SimulationContextType | undefined>(undefined);

export const SimulationProvider: React.FC<{ children: ReactNode }> = ({ children }) => {
  const [simStage, setSimStage] = useState('idle');
  const [summary, setSummary] = useState<SimulationSummary | null>(null);
  const [logs, setLogs] = useState<string[]>([
    "[14:22:01] INFO: System ready. Waiting for simulation trigger...",
    "[14:22:03] INFO: All 7 data pipelines initialized",
    "[14:22:05] INFO: Quality monitoring active",
  ]);

  const triggerSimulation = async () => {
    if (simStage !== 'idle') return;

    const startTime = Date.now();
    setSummary(null);

    // STAGE 1: ACQUISITION
    setSimStage('acquisition');
    setLogs(["[SIM] ═══════════════════════════════════════════════════════"]);
    setLogs(prev => [...prev, "[SIM] 🚀 ETL SIMULATION STARTED"]);
    setLogs(prev => [...prev, "[SIM] ═══════════════════════════════════════════════════════"]);
    setLogs(prev => [...prev, ""]);
    setLogs(prev => [...prev, "[SIM] 📥 STAGE 1: DATA ACQUISITION"]);
    setLogs(prev => [...prev, "[SIM] INFO: Connecting to data sources..."]);

    setTimeout(() => {
      setLogs(prev => [...prev, "[SIM] ✓ Acquired 5,000 customer records from CRM database"]);
    }, 500);

    setTimeout(() => {
      setLogs(prev => [...prev, "[SIM] ✓ Acquired 5,000 smart meter records from IoT registry"]);
    }, 1000);

    setTimeout(() => {
      setLogs(prev => [...prev, "[SIM] ✓ Acquired 10,000 meter readings from streaming API"]);
    }, 1500);

    setTimeout(() => {
      setLogs(prev => [...prev, "[SIM] ✓ Acquired 50 grid sensor records from infrastructure DB"]);
    }, 1800);

    setTimeout(() => {
      setLogs(prev => [...prev, "[SIM] ✓ Acquired 8,000 sensor readings from monitoring system"]);
    }, 2100);

    setTimeout(() => {
      setLogs(prev => [...prev, "[SIM] ✓ Acquired 5,000 billing records from financial system"]);
    }, 2400);

    setTimeout(() => {
      setLogs(prev => [...prev, "[SIM] ✓ Acquired 2,000 weather data points from external API"]);
    }, 2700);

    // STAGE 2: VALIDATION
    setTimeout(() => {
      setSimStage('validation');
      setLogs(prev => [...prev, ""]);
      setLogs(prev => [...prev, "[SIM] 🔍 STAGE 2: DATA VALIDATION"]);
      setLogs(prev => [...prev, "[SIM] INFO: Running quality checks across all datasets..."]);
    }, 3500);

    setTimeout(() => {
      setLogs(prev => [...prev, "[SIM] WARN: Found 431 issues in customer data (8.6% error rate)"]);
    }, 4000);

    setTimeout(() => {
      setLogs(prev => [...prev, "[SIM] WARN: Found 313 issues in smart meter data (6.3% error rate)"]);
    }, 4500);

    setTimeout(() => {
      setLogs(prev => [...prev, "[SIM] WARN: Found 708 issues in meter readings (7.1% error rate)"]);
    }, 5000);

    setTimeout(() => {
      setLogs(prev => [...prev, "[SIM] INFO: Grid sensors data clean (0% error rate)"]);
    }, 5300);

    setTimeout(() => {
      setLogs(prev => [...prev, "[SIM] WARN: Found 1,981 issues in sensor readings (24.8% error rate)"]);
    }, 5600);

    setTimeout(() => {
      setLogs(prev => [...prev, "[SIM] ERROR: Found 3,800 issues in billing records (76% error rate)"]);
    }, 6000);

    setTimeout(() => {
      setLogs(prev => [...prev, "[SIM] WARN: Found 616 issues in weather data (30.8% error rate)"]);
    }, 6400);

    // STAGE 3: CLEANSING
    setTimeout(() => {
      setSimStage('cleansing');
      setLogs(prev => [...prev, ""]);
      setLogs(prev => [...prev, "[SIM] 🧹 STAGE 3: DATA CLEANSING"]);
      setLogs(prev => [...prev, "[SIM] INFO: Applying cleansing rules and transformations..."]);
    }, 7000);

    setTimeout(() => {
      setLogs(prev => [...prev, "[SIM] INFO: Fixing NULL values with interpolation..."]);
    }, 7500);

    setTimeout(() => {
      setLogs(prev => [...prev, "[SIM] INFO: Correcting outliers using statistical methods..."]);
    }, 8000);

    setTimeout(() => {
      setLogs(prev => [...prev, "[SIM] INFO: Resolving schema mismatches..."]);
    }, 8500);

    setTimeout(() => {
      setLogs(prev => [...prev, "[SIM] INFO: Applying business rules for data standardization..."]);
    }, 9000);

    setTimeout(() => {
      setLogs(prev => [...prev, "[SIM] ✓ Cleansing complete. Fixed critical issues."]);
    }, 9500);

    // STAGE 4: TRANSFORMATION
    setTimeout(() => {
      setSimStage('transformation');
      setLogs(prev => [...prev, ""]);
      setLogs(prev => [...prev, "[SIM] ⚙️  STAGE 4: DATA TRANSFORMATION"]);
      setLogs(prev => [...prev, "[SIM] INFO: Transforming data for Lakehouse schema..."]);
    }, 10500);

    setTimeout(() => {
      setLogs(prev => [...prev, "[SIM] INFO: Applying dimensional modeling..."]);
    }, 11000);

    setTimeout(() => {
      setLogs(prev => [...prev, "[SIM] INFO: Creating foreign key relationships..."]);
    }, 11500);

    setTimeout(() => {
      setLogs(prev => [...prev, "[SIM] INFO: Generating surrogate keys..."]);
    }, 12000);

    setTimeout(() => {
      setLogs(prev => [...prev, "[SIM] ✓ Transformation complete. Data ready for load."]);
    }, 12500);

    // STAGE 5: LAKEHOUSE LOAD
    setTimeout(() => {
      setSimStage('lakehouse');
      setLogs(prev => [...prev, ""]);
      setLogs(prev => [...prev, "[SIM] 💾 STAGE 5: LAKEHOUSE LOAD"]);
      setLogs(prev => [...prev, "[SIM] INFO: Loading transformed data to Lakehouse..."]);
    }, 13500);

    setTimeout(() => {
      setLogs(prev => [...prev, "[SIM] INFO: Writing to Delta Lake format..."]);
    }, 14000);

    setTimeout(() => {
      setLogs(prev => [...prev, "[SIM] INFO: Updating metadata catalog..."]);
    }, 14500);

    setTimeout(() => {
      setLogs(prev => [...prev, "[SIM] INFO: Creating indexes and partitions..."]);
    }, 15000);

    // COMPLETION & SUMMARY
    setTimeout(async () => {
      const endTime = Date.now();
      const duration = ((endTime - startTime) / 1000).toFixed(1);

      // Fetch quality data for summary
      try {
        const qualityRes = await axios.get('/api/quality');
        const quality = qualityRes.data;

        const summaryData: SimulationSummary = {
          totalRecordsProcessed: 35050,
          recordsByDataset: {
            customers: 5000,
            smartMeters: 5000,
            meterReadings: 10000,
            gridSensors: 50,
            sensorReadings: 8000,
            billingRecords: 5000,
            weatherData: 2000
          },
          issuesFound: {
            nulls: quality.issues.nulls || 0,
            outliers: quality.issues.outliers || 0,
            schemaMismatch: quality.issues.schema_mismatch || 0
          },
          issuesFixed: Math.floor((quality.issues.nulls + quality.issues.outliers + quality.issues.schema_mismatch) * 0.3),
          qualityScore: quality.score || 0,
          duration: `${duration}s`
        };

        setSummary(summaryData);

        setLogs(prev => [...prev, ""]);
        setLogs(prev => [...prev, "[SIM] ═══════════════════════════════════════════════════════"]);
        setLogs(prev => [...prev, "[SIM] ✅ ETL SIMULATION COMPLETED SUCCESSFULLY"]);
        setLogs(prev => [...prev, "[SIM] ═══════════════════════════════════════════════════════"]);
        setLogs(prev => [...prev, ""]);
        setLogs(prev => [...prev, "[SIM] 📊 EXECUTION SUMMARY:"]);
        setLogs(prev => [...prev, `[SIM]    Total Records Processed: ${summaryData.totalRecordsProcessed.toLocaleString()}`]);
        setLogs(prev => [...prev, `[SIM]    Duration: ${duration} seconds`]);
        setLogs(prev => [...prev, `[SIM]    Quality Score: ${summaryData.qualityScore.toFixed(1)}%`]);
        setLogs(prev => [...prev, ""]);
        setLogs(prev => [...prev, "[SIM] 📁 RECORDS BY DATASET:"]);
        setLogs(prev => [...prev, `[SIM]    • Customers: ${summaryData.recordsByDataset.customers.toLocaleString()}`]);
        setLogs(prev => [...prev, `[SIM]    • Smart Meters: ${summaryData.recordsByDataset.smartMeters.toLocaleString()}`]);
        setLogs(prev => [...prev, `[SIM]    • Meter Readings: ${summaryData.recordsByDataset.meterReadings.toLocaleString()}`]);
        setLogs(prev => [...prev, `[SIM]    • Grid Sensors: ${summaryData.recordsByDataset.gridSensors.toLocaleString()}`]);
        setLogs(prev => [...prev, `[SIM]    • Sensor Readings: ${summaryData.recordsByDataset.sensorReadings.toLocaleString()}`]);
        setLogs(prev => [...prev, `[SIM]    • Billing Records: ${summaryData.recordsByDataset.billingRecords.toLocaleString()}`]);
        setLogs(prev => [...prev, `[SIM]    • Weather Data: ${summaryData.recordsByDataset.weatherData.toLocaleString()}`]);
        setLogs(prev => [...prev, ""]);
        setLogs(prev => [...prev, "[SIM] 🔧 DATA QUALITY:"]);
        setLogs(prev => [...prev, `[SIM]    • NULL Values Found: ${summaryData.issuesFound.nulls.toLocaleString()}`]);
        setLogs(prev => [...prev, `[SIM]    • Outliers Detected: ${summaryData.issuesFound.outliers.toLocaleString()}`]);
        setLogs(prev => [...prev, `[SIM]    • Schema Mismatches: ${summaryData.issuesFound.schemaMismatch.toLocaleString()}`]);
        setLogs(prev => [...prev, `[SIM]    • Issues Auto-Fixed: ${summaryData.issuesFixed.toLocaleString()}`]);
        setLogs(prev => [...prev, ""]);
        setLogs(prev => [...prev, "[SIM] ═══════════════════════════════════════════════════════"]);
        setLogs(prev => [...prev, "[SIM] 🎉 Pipeline ready for next cycle"]);
        setLogs(prev => [...prev, "[SIM] ═══════════════════════════════════════════════════════"]);

      } catch (error) {
        console.error('Error fetching quality data:', error);
      }

      // Trigger backend simulation
      try {
        await fetch('/api/simulate', { method: 'POST' });
      } catch (e) {
        console.error("Simulation API failed", e);
      }

      setSimStage('idle');
      
      // Broadcast to other components to fetch new data
      window.dispatchEvent(new CustomEvent('refresh-data'));
    }, 15500);
  };

  return (
    <SimulationContext.Provider value={{ simStage, logs, summary, triggerSimulation }}>
      {children}
    </SimulationContext.Provider>
  );
};

export const useSimulation = () => {
  const context = useContext(SimulationContext);
  if (context === undefined) {
    throw new Error('useSimulation must be used within a SimulationProvider');
  }
  return context;
};

// Made with Bob
