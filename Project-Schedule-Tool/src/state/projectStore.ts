import { create } from 'zustand';
import type { Project } from '../models/Project';


interface ProjectState {
  project: Project;
  setProjectName: (name: string) => void;
  setCustomer: (customer: string) => void;
  setStartDate: (date: string) => void;
  setBackground: (background: string) => void;
  setAssumptions: (assumptions: string) => void;
  setOutOfScope: (outOfScope: string) => void;
  loadProject: (project: Project) => void;
  resetProject: () => void;
}

const defaultProject: Project = {
  id: 'default-project',
  name: 'New Project Schedule',
  customer: 'Acme Corp',
  suggestedStartDate: new Date().toISOString().split('T')[0] // today's date
};

export const useProjectStore = create<ProjectState>((set) => ({
  project: { ...defaultProject },

  setProjectName: (name) =>
    set((state) => ({
      project: { ...state.project, name }
    })),

  setCustomer: (customer) =>
    set((state) => ({
      project: { ...state.project, customer }
    })),

  setStartDate: (date) =>
    set((state) => ({
      project: { ...state.project, suggestedStartDate: date }
    })),

  setBackground: (background) =>
    set((state) => ({
      project: { ...state.project, background }
    })),

  setAssumptions: (assumptions) =>
    set((state) => ({
      project: { ...state.project, assumptions }
    })),

  setOutOfScope: (outOfScope) =>
    set((state) => ({
      project: { ...state.project, outOfScope }
    })),

  loadProject: (project) =>
    set(() => ({ project })),

  resetProject: () =>
    set(() => ({
      project: { ...defaultProject, id: crypto.randomUUID() }
    }))
}));

