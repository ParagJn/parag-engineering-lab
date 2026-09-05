import { create } from 'zustand';
import type { Task } from '../models/Task';
import type { Week } from '../models/Week';
import type { HolidayEntry } from '../models/Holiday';
import { calculateSchedule } from '../engines/SchedulingEngine';
import { useProjectStore } from './projectStore';

export interface HolidayInfo {
  name: string;
  region: 'vic' | 'india';
}

interface TaskState {
  tasks: Task[];
  weeks: Week[];
  minWeeksToShow: number;
  vicHolidays: HolidayEntry[];
  indiaHolidays: HolidayEntry[];
  vicHolidaysEnabled: boolean;
  indiaHolidaysEnabled: boolean;
  addTask: () => void;
  insertTaskAbove: (targetId: string) => void;
  insertTaskBelow: (targetId: string) => void;
  deleteTask: (id: string) => void;
  updateTask: (id: string, updates: Partial<Task>) => void;
  setTasks: (tasks: Task[]) => void;
  clearTasks: () => void;
  resetTasks: () => void;
  recalculate: (startDate?: string) => void;
  setMinWeeksToShow: (num: number) => void;
  setRegionHolidays: (region: 'vic' | 'india', holidays: HolidayEntry[]) => void;
  toggleHolidayRegion: (region: 'vic' | 'india') => void;
  getActiveHolidayMap: () => Record<string, HolidayInfo>;
  loadHolidayState: (state: {
    vicHolidays?: HolidayEntry[];
    indiaHolidays?: HolidayEntry[];
    vicHolidaysEnabled?: boolean;
    indiaHolidaysEnabled?: boolean;
  }) => void;
}

function createInitialTasks(): Task[] {
  return [
  {
    id: 'task-1',
    index: 1,
    activity: 'Task 1',
    estimatedHours: 40,
    estimatedDays: 5,
    estimatedWeeks: 1,
    fte: 1,
    durationMode: 'effort-driven',
    dependency: '',
    color: '#FFEB3B', // Yellow
    status: 'planned'
  },
  {
    id: 'task-2',
    index: 2,
    activity: 'Task 2',
    estimatedHours: 160,
    estimatedDays: 20,
    estimatedWeeks: 4,
    fte: 1,
    durationMode: 'effort-driven',
    dependency: '1',
    color: '#2196F3', // Blue
    status: 'planned'
  },
  {
    id: 'task-3',
    index: 3,
    activity: 'Task 3',
    estimatedHours: 60,
    estimatedDays: 7.5,
    estimatedWeeks: 1.5,
    fte: 1,
    durationMode: 'effort-driven',
    dependency: '1',
    color: '#4CAF50', // Green
    status: 'planned'
  },
  {
    id: 'task-4',
    index: 4,
    activity: 'Task 4',
    estimatedHours: 80,
    estimatedDays: 10,
    estimatedWeeks: 2,
    fte: 2,
    durationMode: 'effort-driven',
    dependency: '2',
    color: '#FF9800', // Orange
    status: 'planned'
  }
  ];
}

export const useTaskStore = create<TaskState>((set, get) => ({
  tasks: [],
  weeks: [],
  minWeeksToShow: 52, // Default to 52 weeks (1 year) for a spacious planning timeline
  vicHolidays: [],
  indiaHolidays: [],
  vicHolidaysEnabled: false,
  indiaHolidaysEnabled: false,

  addTask: () => {
    const currentTasks = get().tasks;
    const nextIndex = currentTasks.length + 1;
    const newTask: Task = {
      id: crypto.randomUUID(),
      index: nextIndex,
      activity: `Task ${nextIndex}`,
      estimatedHours: 40,
      estimatedDays: 5,
      estimatedWeeks: 1,
      fte: 1,
      durationMode: 'effort-driven',
      dependency: '',
      color: '#9C27B0', // Purple default
      status: 'planned'
    };

    const updatedTasks = [...currentTasks, newTask];
    set({ tasks: updatedTasks });
    get().recalculate();
  },

  insertTaskAbove: (targetId: string) => {
    const currentTasks = get().tasks;
    const targetIndex = currentTasks.findIndex((t) => t.id === targetId);
    
    if (targetIndex === -1) return;
    
    const newTask: Task = {
      id: crypto.randomUUID(),
      index: targetIndex + 1, // Will be renumbered below
      activity: `New Task`,
      estimatedHours: 40,
      estimatedDays: 5,
      estimatedWeeks: 1,
      fte: 1,
      durationMode: 'effort-driven',
      dependency: '',
      color: '#9C27B0', // Purple default
      status: 'planned'
    };

    // Insert the new task before the target
    const updatedTasks = [
      ...currentTasks.slice(0, targetIndex),
      newTask,
      ...currentTasks.slice(targetIndex)
    ];

    // Re-adjust all indexes
    updatedTasks.forEach((t, i) => {
      t.index = i + 1;
    });

    set({ tasks: updatedTasks });
    get().recalculate();
  },

  insertTaskBelow: (targetId: string) => {
    const currentTasks = get().tasks;
    const targetIndex = currentTasks.findIndex((t) => t.id === targetId);
    
    if (targetIndex === -1) return;
    
    const newTask: Task = {
      id: crypto.randomUUID(),
      index: targetIndex + 2, // Will be renumbered below
      activity: `New Task`,
      estimatedHours: 40,
      estimatedDays: 5,
      estimatedWeeks: 1,
      fte: 1,
      durationMode: 'effort-driven',
      dependency: '',
      color: '#9C27B0', // Purple default
      status: 'planned'
    };

    // Insert the new task after the target
    const updatedTasks = [
      ...currentTasks.slice(0, targetIndex + 1),
      newTask,
      ...currentTasks.slice(targetIndex + 1)
    ];

    // Re-adjust all indexes
    updatedTasks.forEach((t, i) => {
      t.index = i + 1;
    });

    set({ tasks: updatedTasks });
    get().recalculate();
  },

  deleteTask: (id) => {
    const updatedTasks = get().tasks.filter((t) => t.id !== id);
    // Re-adjust indexes
    updatedTasks.forEach((t, i) => {
      t.index = i + 1;
    });
    set({ tasks: updatedTasks });
    get().recalculate();
  },

  updateTask: (id, updates) => {
    const updatedTasks = get().tasks.map((t) => {
      if (t.id === id) {
        // Ensure values are numbers or correct formats
        const updated = { ...t, ...updates };
        if (updates.estimatedHours !== undefined) {
          updated.estimatedHours = Math.max(0, Number(updates.estimatedHours) || 0);
        }
        if (updates.fte !== undefined) {
          updated.fte = Math.max(0.1, Number(updates.fte) || 1.0);
        }
        return updated;
      }
      return t;
    });
    set({ tasks: updatedTasks });
    get().recalculate();
  },

  setTasks: (tasks) => {
    set({ tasks });
    get().recalculate();
  },

  clearTasks: () => {
    set({ tasks: [], weeks: [] });
  },

  resetTasks: () => {
    set({
      tasks: createInitialTasks(),
      vicHolidaysEnabled: false,
      indiaHolidaysEnabled: false
    });
    get().recalculate();
  },

  recalculate: (startDate) => {
    // We fetch start date from projectStore if not supplied
    const suggestedStartDateStr = startDate || useProjectStore.getState().project.suggestedStartDate || new Date().toISOString().split('T')[0];

    const holidayMap = get().getActiveHolidayMap();
    const holidayDates = new Set(Object.keys(holidayMap));
    const holidayNames: Record<string, string> = Object.fromEntries(
      Object.entries(holidayMap).map(([date, info]) => [date, info.name])
    );

    const { tasks, weeks } = calculateSchedule(get().tasks, suggestedStartDateStr, get().minWeeksToShow || 52, holidayDates, holidayNames);
    set({ tasks, weeks });
  },

  setMinWeeksToShow: (num) => {
    set({ minWeeksToShow: Math.max(1, num) });
    get().recalculate();
  },

  setRegionHolidays: (region, holidays) => {
    if (region === 'vic') {
      set({ vicHolidays: holidays });
    } else {
      set({ indiaHolidays: holidays });
    }
  },

  toggleHolidayRegion: (region) => {
    if (region === 'vic') {
      set({ vicHolidaysEnabled: !get().vicHolidaysEnabled });
    } else {
      set({ indiaHolidaysEnabled: !get().indiaHolidaysEnabled });
    }
    get().recalculate();
  },

  getActiveHolidayMap: () => {
    const map: Record<string, HolidayInfo> = {};
    if (get().vicHolidaysEnabled) {
      get().vicHolidays.forEach(h => { map[h.date] = { name: h.name, region: 'vic' }; });
    }
    if (get().indiaHolidaysEnabled) {
      get().indiaHolidays.forEach(h => { map[h.date] = { name: h.name, region: 'india' }; });
    }
    return map;
  },

  loadHolidayState: (state) => {
    set({
      vicHolidays: state.vicHolidays || [],
      indiaHolidays: state.indiaHolidays || [],
      vicHolidaysEnabled: state.vicHolidaysEnabled || false,
      indiaHolidaysEnabled: state.indiaHolidaysEnabled || false
    });
    get().recalculate();
  }
}));

// Subscribe to project store changes in taskStore to trigger recalculation
let lastStartDate = useProjectStore.getState().project.suggestedStartDate;
useProjectStore.subscribe((state) => {
  const newStartDate = state.project.suggestedStartDate;
  if (newStartDate !== lastStartDate) {
    lastStartDate = newStartDate;
    useTaskStore.getState().recalculate(newStartDate);
  }
});

// Run initial calculation to generate weeks list and update default tasks
setTimeout(() => {
  useTaskStore.setState({ tasks: createInitialTasks() });
  useTaskStore.getState().recalculate();
}, 0);

