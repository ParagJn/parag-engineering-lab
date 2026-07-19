import type { Task } from '../../models/Task';

export const planningApi = {
  getTasks: async (projectId: string): Promise<Task[]> => {
    console.log('Fetching tasks for project: ', projectId);
    return [];
  },
  saveTasks: async (projectId: string, tasks: Task[]): Promise<void> => {
    console.log('Saved tasks for project: ', projectId, tasks);
  }
};
