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

/** Experimental animated export formats for an SVG image. */
export type SvgExportFormat = 'mp4' | 'gif';

/** The SVG image the next SVG prompt will edit. */
export interface SvgEditTarget {
  svgImageId: string;
  version: number;
}

export interface MessageAttachment {
  attachment_id: string;
  filename: string;
  mime_type?: string | null;
}

export type ModelProvider = 'claude' | 'gemini' | 'openai';

export interface Session {
  session_id: string;
  created_at: string;
  updated_at: string;
  title: string;
  model: ModelProvider;
  web_search_enabled: boolean;
  project_id?: string | null;
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
  project_id?: string | null;
}

export interface UpdateSessionRequest {
  title?: string;
  model?: ModelProvider;
  web_search_enabled?: boolean;
  /** null takes the chat out of its project */
  project_id?: string | null;
}

export interface ProjectSummary {
  project_id: string;
  name: string;
  description: string;
  instructions: string;
  created_at: string;
  updated_at: string;
  session_count: number;
  document_count: number;
  /** Estimated tokens the pinned documents add to every message */
  context_tokens: number;
}

export interface ProjectDocument {
  attachment_id: string;
  filename: string;
  mime_type: string;
  size_bytes: number;
  status: Attachment['status'];
  tokens: number;
  created_at: string;
}

export interface ProjectDetail extends ProjectSummary {
  documents: ProjectDocument[];
  context_budget_tokens: number;
}

export interface ProjectUpdateRequest {
  name?: string;
  description?: string;
  instructions?: string;
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

export interface SearchSnippetPart {
  text: string;
  match: boolean;
}

export interface SearchMessageHit {
  message_id: string;
  session_id: string;
  session_title: string;
  project_id: string | null;
  role: 'system' | 'user' | 'assistant';
  created_at: string;
  snippet: SearchSnippetPart[];
}

export interface SearchSessionHit {
  session_id: string;
  title: string;
  project_id: string | null;
  updated_at: string;
}

export interface SearchResponse {
  query: string;
  sessions: SearchSessionHit[];
  messages: SearchMessageHit[];
}
