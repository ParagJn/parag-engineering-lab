import { create } from 'zustand';
import type { Task } from '../models/Task';
import type { Week } from '../models/Week';
import { calculateSchedule } from '../engines/SchedulingEngine';
import { useProjectStore } from './projectStore';


interface TaskState {
  tasks: Task[];
  weeks: Week[];
  minWeeksToShow: number;
  addTask: () => void;
  deleteTask: (id: string) => void;
  updateTask: (id: string, updates: Partial<Task>) => void;
  setTasks: (tasks: Task[]) => void;
  clearTasks: () => void;
  recalculate: (startDate?: string) => void;
  setMinWeeksToShow: (num: number) => void;
}

const initialTasks: Task[] = [
  {
    id: 'task-1',
    index: 1,
    activity: 'Task 1',
    estimatedHours: 40,
    estimatedDays: 5,
    estimatedWeeks: 1,
    fte: 1,
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
    dependency: '2',
    color: '#FF9800', // Orange
    status: 'planned'
  }
];

export const useTaskStore = create<TaskState>((set, get) => ({
  tasks: [],
  weeks: [],
  minWeeksToShow: 52, // Default to 52 weeks (1 year) for a spacious planning timeline

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
      dependency: '',
      color: '#9C27B0', // Purple default
      status: 'planned'
    };

    const updatedTasks = [...currentTasks, newTask];
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

  recalculate: (startDate) => {
    // We fetch start date from projectStore if not supplied
    const suggestedStartDateStr = startDate || useProjectStore.getState().project.suggestedStartDate || new Date().toISOString().split('T')[0];

    const { tasks, weeks } = calculateSchedule(get().tasks, suggestedStartDateStr, get().minWeeksToShow || 52);
    set({ tasks, weeks });
  },

  setMinWeeksToShow: (num) => {
    set({ minWeeksToShow: Math.max(1, num) });
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
  useTaskStore.setState({ tasks: initialTasks });
  useTaskStore.getState().recalculate();
}, 0);

