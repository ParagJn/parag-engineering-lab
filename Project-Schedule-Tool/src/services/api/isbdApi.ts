/**
 * API service for ISBD slide deck generation
 */
import { saveAs } from 'file-saver';

const API_BASE_URL = 'http://localhost:8000';

export interface ISBDGenerationRequest {
  project_name: string;
  customer: string;
  sow_content: string;
}

export const isbdApi = {
  /**
   * Generate the ISBD PowerPoint deck and save it to the user's downloads
   */
  generateISBD: async (request: ISBDGenerationRequest): Promise<void> => {
    const response = await fetch(`${API_BASE_URL}/generate/isbd`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify(request),
    });

    if (!response.ok) {
      let detail = response.statusText;
      try {
        const errorBody = await response.json();
        detail = errorBody.detail || detail;
      } catch {
        // response body wasn't JSON - fall back to statusText
      }
      throw new Error(`ISBD generation failed: ${detail}`);
    }

    const blob = await response.blob();
    const filename = `${request.project_name.replace(/\s+/g, '_')}_ISBD.pptx`;
    saveAs(blob, filename);
  },
};
