import type { Project } from '../../models/Project';
import type { Task } from '../../models/Task';

export const exportApi = {
  exportToBackend: async (project: Project, tasks: Task[]): Promise<void> => {
    console.log('Sending project export data to backend API...', { project, tasks });
  }
};
