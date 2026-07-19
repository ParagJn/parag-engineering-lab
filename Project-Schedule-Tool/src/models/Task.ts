export interface Task {
  id: string;
  index: number; // 1-based index representing order in the table
  activity: string;
  estimatedHours: number;
  estimatedDays: number; // calculated: hours / 8
  estimatedWeeks: number; // calculated: days / 5
  fte: number; // default: 1
  dependency: string; // references task indexes, e.g. "1" or "2,3"
  manualStartDate?: string; // YYYY-MM-DD (optional override)
  calculatedStartDate?: string; // YYYY-MM-DD (calculated by engine)
  calculatedFinishDate?: string; // YYYY-MM-DD (calculated by engine)
  weekAssignments?: Record<string, number>; // friday YYYY-MM-DD string -> percentage allocation (0.0 to 1.0)
  color: string; // hex color for timeline bar
  status: 'planned' | 'active' | 'completed' | 'on-hold';
}
