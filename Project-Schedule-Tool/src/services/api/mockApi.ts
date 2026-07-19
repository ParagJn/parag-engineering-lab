// Stub for mock API integration
export const mockApi = {
  get: async (url: string) => {
    console.log(`Mock GET call to: ${url}`);
    return { success: true };
  },
  post: async (url: string, data: any) => {
    console.log(`Mock POST call to: ${url}`, data);
    return { success: true };
  }
};
