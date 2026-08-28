// Message component for displaying chat messages

import React from 'react';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import { Prism as SyntaxHighlighter } from 'react-syntax-highlighter';
import { vscDarkPlus } from 'react-syntax-highlighter/dist/esm/styles/prism';
import type { Message as MessageType } from '../types';

interface MessageProps {
  message: MessageType;
}

export const Message: React.FC<MessageProps> = ({ message }) => {
  const isUser = message.role === 'user';

  return (
    <div className={`flex ${isUser ? 'justify-end' : 'justify-start'} mb-6 px-8 animate-fadeIn`}>
      <div className={`max-w-4xl ${isUser ? 'w-auto' : 'w-full'}`}>
        <div className={`flex items-center gap-2 mb-2 ${isUser ? 'justify-end' : 'justify-start'}`}>
          <div className={`w-8 h-8 rounded-full flex items-center justify-center text-sm font-medium ${
            isUser ? 'bg-blue-600 text-white' : 'bg-purple-600 text-white'
          }`}>
            {isUser ? 'You' : 'AI'}
          </div>
          <div className={`text-xs font-medium ${isUser ? 'text-blue-600' : 'text-purple-600'}`}>
            {isUser ? 'You' : 'AI Assistant'}
          </div>
        </div>
        <div className={`rounded-2xl p-6 shadow-sm ${
          isUser 
            ? 'bg-blue-50 border border-blue-100' 
            : 'bg-white border border-gray-200'
        }`}>
        {isUser ? (
          <div className="whitespace-pre-wrap text-gray-900 leading-relaxed">{message.content}</div>
        ) : (
          <div className="markdown">
            <ReactMarkdown
              remarkPlugins={[remarkGfm]}
              components={{
                code({ node, inline, className, children, ...props }: any) {
                  const match = /language-(\w+)/.exec(className || '');
                  return !inline && match ? (
                    <div className="relative my-4 group">
                      <div className="absolute top-3 right-3 flex gap-2 z-10">
                        <span className="text-xs px-3 py-1.5 bg-gray-700 text-gray-300 rounded-lg font-mono">
                          {match[1]}
                        </span>
                        <button
                          onClick={() => {
                            navigator.clipboard.writeText(String(children));
                          }}
                          className="px-3 py-1.5 text-xs font-medium rounded-lg bg-gray-700 hover:bg-gray-600 text-white transition-all flex items-center gap-1"
                        >
                          <svg className="w-3.5 h-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M8 16H6a2 2 0 01-2-2V6a2 2 0 012-2h8a2 2 0 012 2v2m-6 12h8a2 2 0 002-2v-8a2 2 0 00-2-2h-8a2 2 0 00-2 2v8a2 2 0 002 2z" />
                          </svg>
                          Copy
                        </button>
                      </div>
                      <SyntaxHighlighter
                        {...props}
                        style={vscDarkPlus}
                        language={match[1]}
                        PreTag="div"
                        customStyle={{
                          margin: 0,
                          borderRadius: '12px',
                          padding: '24px',
                          fontSize: '14px',
                        }}
                      >
                        {String(children).replace(/\n$/, '')}
                      </SyntaxHighlighter>
                    </div>
                  ) : (
                    <code {...props} className={className}>
                      {children}
                    </code>
                  );
                },
              }}
            >
              {message.content}
            </ReactMarkdown>
          </div>
        )}
        </div>
      </div>
    </div>
  );
};
