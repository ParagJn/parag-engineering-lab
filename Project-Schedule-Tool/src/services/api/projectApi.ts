import type { Project } from '../../models/Project';

export const projectApi = {
  getProject: async (id: string): Promise<Project> => {
    return {
      id,
      name: 'Mock Project',
      customer: 'Mock Customer',
      suggestedStartDate: new Date().toISOString().split('T')[0]
    };
  },
  saveProject: async (project: Project): Promise<void> => {
    console.log('Saved project: ', project);
  }
};
