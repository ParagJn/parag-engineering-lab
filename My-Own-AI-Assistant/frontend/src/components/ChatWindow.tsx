// ChatWindow component for displaying messages

import { useRef, useEffect, forwardRef } from 'react';
import { Message } from './Message';
import { Composer, type ComposerHandle } from './Composer';
import { RateLimitTimer, type RateLimitInfo } from './RateLimitTimer';
import type { Message as MessageType, ModelProvider, ProjectDetail, SvgEditTarget } from '../types';

interface ChatWindowProps {
  messages: MessageType[];
  onSendMessage: (content: string, files: File[]) => void;
  isLoading: boolean;
  model: ModelProvider;
  onModelChange: (model: ModelProvider) => void;
  webSearchEnabled: boolean;
  onWebSearchToggle: (enabled: boolean) => void;
  rateLimitInfo: RateLimitInfo | null;
  onCancelRateLimitWait: () => void;
  streamingText: string | null;
  svgMode: boolean;
  onSvgModeToggle: (enabled: boolean) => void;
  svgEditTarget: SvgEditTarget | null;
  onEditSvg: (target: SvgEditTarget) => void;
  onClearSvgEdit: () => void;
  /** The project this chat belongs to, if any */
  project?: ProjectDetail | null;
  onOpenProject?: () => void;
  onPinAttachment?: (attachmentId: string) => void;
  /** Message to scroll to and highlight (from search) */
  focusMessageId?: string | null;
  onFocusHandled?: () => void;
}

export const ChatWindow = forwardRef<ComposerHandle, ChatWindowProps>(({
  messages,
  onSendMessage,
  isLoading,
  model,
  onModelChange,
  webSearchEnabled,
  onWebSearchToggle,
  rateLimitInfo,
  onCancelRateLimitWait,
  streamingText,
  svgMode,
  onSvgModeToggle,
  svgEditTarget,
  onEditSvg,
  onClearSvgEdit,
  project = null,
  onOpenProject,
  onPinAttachment,
  focusMessageId = null,
  onFocusHandled,
}, ref) => {
  const messagesEndRef = useRef<HTMLDivElement>(null);

  const displayMessages = streamingText !== null
    ? [
        ...messages,
        {
          id: 'streaming',
          role: 'assistant' as const,
          content: streamingText,
          created_at: new Date().toISOString(),
          attachments: [],
        },
      ]
    : messages;

  // Follow new messages, unless we're showing a message opened from search
  useEffect(() => {
    if (focusMessageId) return;
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages, streamingText]);

  // Scroll to a message opened from search and highlight it briefly
  useEffect(() => {
    if (!focusMessageId) return;
    const target = document.getElementById(`msg-${focusMessageId}`);
    if (!target) {
      // Not in this chat (e.g. it was removed): show the latest message instead
      messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
      onFocusHandled?.();
      return;
    }
    target.scrollIntoView({ behavior: 'smooth', block: 'center' });
    const timer = window.setTimeout(() => onFocusHandled?.(), 2500);
    return () => window.clearTimeout(timer);
  }, [focusMessageId, messages]);

  const pinnedIds = new Set(project?.documents.map((d) => d.attachment_id) ?? []);
  const approxTokens = (tokens: number) =>
    tokens >= 1000 ? `${(tokens / 1000).toFixed(tokens >= 10000 ? 0 : 1)}k` : String(tokens);

  return (
    <div className="flex-1 flex flex-col h-screen bg-white">
      {project && (
        <div className="flex items-center gap-2 px-6 py-2 border-b border-gray-100 text-sm">
          <button
            onClick={onOpenProject}
            className="flex items-center gap-1.5 px-2.5 py-1 rounded-full bg-gray-100 text-gray-800 hover:bg-gray-200 transition-colors min-w-0"
            title="Project settings and documents"
          >
            <svg className="w-3.5 h-3.5 shrink-0" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M3 7a2 2 0 012-2h4l2 2h8a2 2 0 012 2v8a2 2 0 01-2 2H5a2 2 0 01-2-2V7z" />
            </svg>
            <span className="truncate font-medium">{project.name}</span>
          </button>
          <span className="text-xs text-gray-400 truncate">
            {project.document_count > 0
              ? `${project.document_count} doc${project.document_count === 1 ? '' : 's'} in context (~${approxTokens(project.context_tokens)} tokens)`
              : 'No project documents'}
            {project.instructions ? ' · custom instructions' : ''}
          </span>
        </div>
      )}
      {displayMessages.length === 0 && !isLoading ? (
        <div className="flex-1 flex flex-col items-center justify-center px-8 pb-24">
          <div className="w-full max-w-3xl">
            <h1 className="text-4xl font-normal text-gray-900 mb-8 text-center">
              What do you want to know?
            </h1>
            {rateLimitInfo && (
              <div className="mb-4">
                <RateLimitTimer info={rateLimitInfo} onCancel={onCancelRateLimitWait} />
              </div>
            )}
            <Composer
              ref={ref}
              onSend={onSendMessage}
              disabled={isLoading}
              model={model}
              onModelChange={onModelChange}
              webSearchEnabled={webSearchEnabled}
              onWebSearchToggle={onWebSearchToggle}
              svgMode={svgMode}
              onSvgModeToggle={onSvgModeToggle}
              svgEditTarget={svgEditTarget}
              onClearSvgEdit={onClearSvgEdit}
            />
          </div>
        </div>
      ) : (
        <>
          <div className="flex-1 overflow-y-auto py-8">
            {displayMessages.map((message) => (
              <Message
                key={message.id}
                message={message}
                onEditSvg={isLoading ? undefined : onEditSvg}
                isSvgEditTarget={!!message.svg_image_id && message.svg_image_id === svgEditTarget?.svgImageId}
                pinnedAttachmentIds={pinnedIds}
                highlighted={message.id === focusMessageId}
                onPinAttachment={project && !isLoading ? onPinAttachment : undefined}
              />
            ))}
            {isLoading && !rateLimitInfo && streamingText === null && (
              <div className="max-w-3xl mx-auto px-8">
                <div className="text-xs font-medium text-gray-400 mb-1.5">Assistant</div>
                <div className="flex gap-1.5 py-1">
                  <div className="w-1.5 h-1.5 bg-gray-400 rounded-full animate-bounce"></div>
                  <div className="w-1.5 h-1.5 bg-gray-400 rounded-full animate-bounce" style={{ animationDelay: '0.1s' }}></div>
                  <div className="w-1.5 h-1.5 bg-gray-400 rounded-full animate-bounce" style={{ animationDelay: '0.2s' }}></div>
                </div>
              </div>
            )}
            <div ref={messagesEndRef} />
          </div>
          {rateLimitInfo && (
            <div className="max-w-3xl mx-auto px-8 w-full mb-3">
              <RateLimitTimer info={rateLimitInfo} onCancel={onCancelRateLimitWait} />
            </div>
          )}
          <Composer
            ref={ref}
            onSend={onSendMessage}
            disabled={isLoading}
            model={model}
            onModelChange={onModelChange}
            webSearchEnabled={webSearchEnabled}
            onWebSearchToggle={onWebSearchToggle}
            svgMode={svgMode}
            onSvgModeToggle={onSvgModeToggle}
            svgEditTarget={svgEditTarget}
            onClearSvgEdit={onClearSvgEdit}
          />
        </>
      )}
    </div>
  );
});

ChatWindow.displayName = 'ChatWindow';
