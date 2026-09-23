// ChatWindow component for displaying messages

import React, { useRef, useEffect } from 'react';
import { Message } from './Message';
import { Composer } from './Composer';
import type { Message as MessageType, ModelProvider } from '../types';

interface ChatWindowProps {
  messages: MessageType[];
  onSendMessage: (content: string, files: File[]) => void;
  isLoading: boolean;
  model: ModelProvider;
  onModelChange: (model: ModelProvider) => void;
}

export const ChatWindow: React.FC<ChatWindowProps> = ({
  messages,
  onSendMessage,
  isLoading,
  model,
  onModelChange,
}) => {
  const messagesEndRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages]);

  return (
    <div className="flex-1 flex flex-col h-screen bg-white">
      {messages.length === 0 && !isLoading ? (
        <div className="flex-1 flex flex-col items-center justify-center px-8 pb-24">
          <div className="w-full max-w-3xl">
            <h1 className="text-4xl font-normal text-gray-900 mb-8 text-center">
              What do you want to know?
            </h1>
            <Composer onSend={onSendMessage} disabled={isLoading} model={model} onModelChange={onModelChange} />
          </div>
        </div>
      ) : (
        <>
          <div className="flex-1 overflow-y-auto py-8">
            {messages.map((message) => (
              <Message key={message.id} message={message} />
            ))}
            {isLoading && (
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
          <Composer onSend={onSendMessage} disabled={isLoading} model={model} onModelChange={onModelChange} />
        </>
      )}
    </div>
  );
};
