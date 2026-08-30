/**
 * API service for Statement of Work (SoW) generation
 */

const API_BASE_URL = 'http://localhost:8000';

export interface SoWGenerationRequest {
  project_name: string;
  customer: string;
  background?: string;
  assumptions?: string;
  out_of_scope?: string;
  maw_deliverables?: string;
}

export interface SoWGenerationResponse {
  success: boolean;
  sow_content?: string;
  needs_more_info?: boolean;
  questions?: string[];
  error?: string;
  timestamp: string;
}

export const sowApi = {
  /**
   * Generate a Statement of Work document using AI
   */
  generateSoW: async (request: SoWGenerationRequest): Promise<SoWGenerationResponse> => {
    try {
      const response = await fetch(`${API_BASE_URL}/generate/sow`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify(request),
      });

      if (!response.ok) {
        throw new Error(`API request failed: ${response.statusText}`);
      }

      const data = await response.json();
      return data;
    } catch (error) {
      console.error('SoW generation error:', error);
      throw error;
    }
  },
};
