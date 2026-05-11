import React, { createContext, useContext, useState } from 'react';
import type { ReactNode } from 'react';

interface SimulationContextType {
  simStage: string;
  logs: string[];
  triggerSimulation: () => Promise<void>;
}

const SimulationContext = createContext<SimulationContextType | undefined>(undefined);

export const SimulationProvider: React.FC<{ children: ReactNode }> = ({ children }) => {
  const [simStage, setSimStage] = useState('idle');
  const [logs, setLogs] = useState<string[]>([
    "[14:22:01] INFO: Initializing cleansing sequence for bucket_882",
    "[14:22:03] WARN: Duplicate entries detected in set 04 (auto-merged)",
    "[14:22:05] INFO: Applying schema transformation ruleset v2.4.1",
    "SUCCESS: Batch 091 verified and ready for Lakehouse export"
  ]);

  const triggerSimulation = async () => {
    if (simStage !== 'idle') return;

    // Trigger backend simulation
    try {
      await fetch('http://localhost:8000/api/simulate', { method: 'POST' });
    } catch (e) {
      console.error("Simulation API failed", e);
    }

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
      // Broadcast to other components to fetch new data
      window.dispatchEvent(new CustomEvent('refresh-data'));
    }, 15000);
  };

  return (
    <SimulationContext.Provider value={{ simStage, logs, triggerSimulation }}>
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
