import type { Project } from '../../models/Project';
import type { Task } from '../../models/Task';
import type { HolidayEntry } from '../../models/Holiday';

export interface SavedPlanHolidayState {
  vicHolidays?: HolidayEntry[];
  indiaHolidays?: HolidayEntry[];
  vicHolidaysEnabled?: boolean;
  indiaHolidaysEnabled?: boolean;
}

export interface SavedPlan extends SavedPlanHolidayState {
  project: Project;
  tasks: Task[];
  lastSaved: string;
}

export const storage = {
  savePlan: (project: Project, tasks: Task[], holidayState?: SavedPlanHolidayState): void => {
    const plansKey = 'antigravity_plans';
    const currentPlansJson = localStorage.getItem(plansKey);
    let plansList: any[] = [];

    if (currentPlansJson) {
      try {
        plansList = JSON.parse(currentPlansJson);
      } catch {
        plansList = [];
      }
    }

    // Remove existing with same project ID
    plansList = plansList.filter(p => p.id !== project.id);

    // Add new
    plansList.push({
      id: project.id,
      name: project.name,
      customer: project.customer,
      lastSaved: new Date().toISOString()
    });

    localStorage.setItem(plansKey, JSON.stringify(plansList));
    localStorage.setItem(`antigravity_plan_${project.id}`, JSON.stringify({ project, tasks, ...holidayState }));
  },

  getPlans: (): any[] => {
    const plansKey = 'antigravity_plans';
    const json = localStorage.getItem(plansKey);
    if (!json) return [];
    try {
      return JSON.parse(json);
    } catch {
      return [];
    }
  },

  loadPlan: (id: string): SavedPlan | null => {
    const json = localStorage.getItem(`antigravity_plan_${id}`);
    if (!json) return null;
    try {
      return JSON.parse(json);
    } catch {
      return null;
    }
  },

  deletePlan: (id: string): void => {
    const plansKey = 'antigravity_plans';
    const currentPlansJson = localStorage.getItem(plansKey);
    if (currentPlansJson) {
      try {
        let plansList = JSON.parse(currentPlansJson);
        plansList = plansList.filter((p: any) => p.id !== id);
        localStorage.setItem(plansKey, JSON.stringify(plansList));
      } catch {}
    }
    localStorage.removeItem(`antigravity_plan_${id}`);
  }
};
