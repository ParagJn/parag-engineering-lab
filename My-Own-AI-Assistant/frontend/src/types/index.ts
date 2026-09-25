// Type definitions

export interface Message {
  id: string;
  role: 'system' | 'user' | 'assistant';
  content: string;
  created_at: string;
  attachments: MessageAttachment[];
  svg_image_id?: string | null;
  svg_parent_id?: string | null;
  svg_version?: number | null;
}

/** The SVG image the next SVG prompt will edit. */
export interface SvgEditTarget {
  svgImageId: string;
  version: number;
}

export interface MessageAttachment {
  attachment_id: string;
  filename: string;
}

export type ModelProvider = 'claude' | 'gemini' | 'openai';

export interface Session {
  session_id: string;
  created_at: string;
  updated_at: string;
  title: string;
  model: ModelProvider;
  web_search_enabled: boolean;
  messages: Message[];
  attachment_ids: string[];
}

export interface SessionListItem {
  session_id: string;
  title: string;
  created_at: string;
  updated_at: string;
  model: ModelProvider;
  web_search_enabled: boolean;
}

export interface UpdateSessionRequest {
  title?: string;
  model?: ModelProvider;
  web_search_enabled?: boolean;
}

export interface Attachment {
  attachment_id: string;
  filename: string;
  mime_type: string;
  size_bytes: number;
  status: 'uploaded' | 'processing' | 'ready' | 'failed';
  markdown_available: boolean;
  image_count: number;
}

export interface MessageRequest {
  content: string;
  attachment_ids?: string[];
}

export interface SvgImageResponse {
  session_id: string;
  svg_image_id: string;
  message: Message;
}

export interface ChatResponse {
  session_id: string;
  message: Message;
}
