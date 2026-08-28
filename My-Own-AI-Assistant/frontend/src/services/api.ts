// API service for backend communication

import axios from 'axios';
import type {
  Session,
  SessionListItem,
  MessageRequest,
  ChatResponse,
  Attachment,
} from '../types';

const API_BASE_URL = import.meta.env.VITE_API_URL || 'http://localhost:8000';

const api = axios.create({
  baseURL: `${API_BASE_URL}/api`,
  headers: {
    'Content-Type': 'application/json',
  },
});

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

  async renameSession(sessionId: string, newTitle: string): Promise<void> {
    await api.patch(`/sessions/${sessionId}`, { title: newTitle });
  },

  // Messages
  async sendMessage(sessionId: string, request: MessageRequest): Promise<ChatResponse> {
    const response = await api.post(`/sessions/${sessionId}/messages`, request);
    return response.data;
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
};
