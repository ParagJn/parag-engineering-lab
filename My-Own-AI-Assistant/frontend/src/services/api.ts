// API service for backend communication

import axios from 'axios';
import type {
  Session,
  SessionListItem,
  MessageRequest,
  ChatResponse,
  Attachment,
  UpdateSessionRequest,
  SvgImageResponse,
  SvgExportFormat,
} from '../types';

const API_BASE_URL = import.meta.env.VITE_API_URL || 'http://localhost:8000';

const api = axios.create({
  baseURL: `${API_BASE_URL}/api`,
  headers: {
    'Content-Type': 'application/json',
  },
});

/** Error thrown by `streamMessage` for non-2xx responses, shaped like an axios error
 * so existing `(err as any)?.response?.status` checks keep working unchanged. */
export class StreamRequestError extends Error {
  response: { status: number; data: { detail?: string } };

  constructor(status: number, detail?: string) {
    super(detail || `Request failed with status ${status}`);
    this.response = { status, data: { detail } };
  }
}

interface StreamMessageCallbacks {
  onChunk: (text: string) => void;
  onDone: (message: { id: string; role: string; content: string; created_at: string }) => void;
  onError: (error: unknown) => void;
}

export const apiService = {
  // Sessions
  async createSession(): Promise<{ session_id: string; created_at: string; updated_at: string; title: string }> {
    const response = await api.post('/sessions');
    return response.data;
  },

  async listSessions(): Promise<SessionListItem[]> {
    const response = await api.get('/sessions');
    return response.data;
  },

  async getSession(sessionId: string): Promise<Session> {
    const response = await api.get(`/sessions/${sessionId}`);
    return response.data;
  },

  async deleteSession(sessionId: string): Promise<void> {
    await api.delete(`/sessions/${sessionId}`);
  },

  async updateSession(sessionId: string, request: UpdateSessionRequest): Promise<void> {
    await api.patch(`/sessions/${sessionId}`, request);
  },

  async renameSession(sessionId: string, newTitle: string): Promise<void> {
    await api.patch(`/sessions/${sessionId}`, { title: newTitle });
  },

  // Messages
  async sendMessage(sessionId: string, request: MessageRequest): Promise<ChatResponse> {
    const response = await api.post(`/sessions/${sessionId}/messages`, request);
    return response.data;
  },

  /**
   * Send a message and stream the assistant's reply as it's generated.
   * Returns a handle with `cancel()` to abort the in-flight request.
   */
  streamMessage(
    sessionId: string,
    request: MessageRequest,
    { onChunk, onDone, onError }: StreamMessageCallbacks,
  ): { cancel: () => void } {
    const controller = new AbortController();

    (async () => {
      try {
        const response = await fetch(`${API_BASE_URL}/api/sessions/${sessionId}/messages/stream`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify(request),
          signal: controller.signal,
        });

        if (!response.ok) {
          let detail: string | undefined;
          try {
            detail = (await response.json())?.detail;
          } catch {
            // ignore — non-JSON error body
          }
          throw new StreamRequestError(response.status, detail);
        }

        const reader = response.body?.getReader();
        if (!reader) {
          throw new Error('Streaming is not supported by this browser.');
        }

        const decoder = new TextDecoder();
        let buffer = '';

        while (true) {
          const { done, value } = await reader.read();
          if (done) break;
          buffer += decoder.decode(value, { stream: true });

          let boundary = buffer.indexOf('\n\n');
          while (boundary !== -1) {
            const rawEvent = buffer.slice(0, boundary);
            buffer = buffer.slice(boundary + 2);

            let eventName = 'message';
            let data = '';
            for (const line of rawEvent.split('\n')) {
              if (line.startsWith('event:')) eventName = line.slice(6).trim();
              else if (line.startsWith('data:')) data += line.slice(5).trim();
            }

            if (data) {
              const parsed = JSON.parse(data);
              if (eventName === 'chunk') onChunk(parsed.text);
              else if (eventName === 'done') onDone(parsed.message);
              else if (eventName === 'error') throw new Error(parsed.detail || 'Streaming failed');
            }

            boundary = buffer.indexOf('\n\n');
          }
        }
      } catch (err) {
        if ((err as any)?.name === 'AbortError') return;
        onError(err);
      }
    })();

    return { cancel: () => controller.abort() };
  },

  // Attachments
  async uploadAttachment(sessionId: string, file: File): Promise<Attachment> {
    const formData = new FormData();
    formData.append('file', file);

    const response = await api.post(`/sessions/${sessionId}/attachments`, formData, {
      headers: {
        'Content-Type': 'multipart/form-data',
      },
    });
    return response.data;
  },

  async getAttachment(sessionId: string, attachmentId: string): Promise<Attachment> {
    const response = await api.get(`/sessions/${sessionId}/attachments/${attachmentId}`);
    return response.data;
  },

  // SVG images — pass baseSvgImageId to edit an existing image
  async generateSvgImage(sessionId: string, prompt: string, baseSvgImageId?: string): Promise<SvgImageResponse> {
    const response = await api.post(`/sessions/${sessionId}/svg-images`, {
      prompt,
      base_svg_image_id: baseSvgImageId ?? null,
    });
    return response.data;
  },

  /** Experimental: render the SVG (with its animations) to MP4/GIF. Can take several seconds. */
  async exportSvgImage(svgImageId: string, format: SvgExportFormat): Promise<Blob> {
    try {
      const response = await api.get(`/svg-images/${svgImageId}/export`, {
        params: { format },
        responseType: 'blob',
      });
      return response.data;
    } catch (err) {
      // With responseType 'blob', the JSON error body arrives as a Blob too
      const data = (err as any)?.response?.data;
      let detail: string | undefined;
      if (data instanceof Blob) {
        try {
          detail = JSON.parse(await data.text())?.detail;
        } catch {
          // ignore — non-JSON error body
        }
      }
      throw new Error(detail || `${format.toUpperCase()} export failed`);
    }
  },

  svgImageUrl(svgImageId: string, download = false): string {
    return `${API_BASE_URL}/api/svg-images/${svgImageId}${download ? '?download=true' : ''}`;
  },

  attachmentImageUrl(attachmentId: string): string {
    return `${API_BASE_URL}/api/attachments/${attachmentId}/image`;
  },
};
