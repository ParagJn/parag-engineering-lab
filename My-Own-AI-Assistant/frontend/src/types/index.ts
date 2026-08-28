// Type definitions

export interface Message {
  id: string;
  role: 'system' | 'user' | 'assistant';
  content: string;
  created_at: string;
  attachments: MessageAttachment[];
}

export interface MessageAttachment {
  attachment_id: string;
  filename: string;
}

export interface Session {
  session_id: string;
  created_at: string;
  updated_at: string;
  title: string;
  messages: Message[];
  attachment_ids: string[];
}

export interface SessionListItem {
  session_id: string;
  title: string;
  created_at: string;
  updated_at: string;
}

export interface Attachment {
  attachment_id: string;
  filename: string;
  mime_type: string;
  size_bytes: number;
  status: 'uploaded' | 'processing' | 'ready' | 'failed';
  markdown_available: boolean;
}

export interface MessageRequest {
  content: string;
  attachment_ids?: string[];
}

export interface ChatResponse {
  session_id: string;
  message: Message;
}
