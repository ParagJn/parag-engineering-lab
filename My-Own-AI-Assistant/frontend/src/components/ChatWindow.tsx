// ChatWindow component for displaying messages

import { useRef, useEffect, forwardRef } from 'react';
import { Message } from './Message';
import { Composer, type ComposerHandle } from './Composer';
import { RateLimitTimer, type RateLimitInfo } from './RateLimitTimer';
import type { Message as MessageType, ModelProvider, SvgEditTarget } from '../types';

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

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages, streamingText]);

  return (
    <div className="flex-1 flex flex-col h-screen bg-white">
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
