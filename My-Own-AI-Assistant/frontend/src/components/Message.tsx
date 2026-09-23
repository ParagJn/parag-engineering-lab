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
    <div className="max-w-3xl mx-auto px-8 mb-8 animate-fadeIn">
      <div className={`text-xs font-medium text-gray-400 mb-1.5 ${isUser ? 'text-right' : ''}`}>
        {isUser ? 'You' : 'Assistant'}
      </div>
      {isUser ? (
        <div className="flex justify-end">
          <div className="max-w-[85%] bg-gray-100 rounded-2xl px-4 py-2.5 whitespace-pre-wrap text-gray-900 leading-relaxed">
            {message.content}
          </div>
        </div>
      ) : (
        <div className="markdown">
          <ReactMarkdown
            remarkPlugins={[remarkGfm]}
            components={{
              code({ node, inline, className, children, ...props }: any) {
                const match = /language-(\w+)/.exec(className || '');
                return !inline && match ? (
                  <div className="relative my-4 group">
                    <div className="absolute top-2.5 right-2.5 flex gap-2 z-10">
                      <span className="text-xs px-2.5 py-1 bg-gray-800 text-gray-300 rounded-md font-mono">
                        {match[1]}
                      </span>
                      <button
                        onClick={() => {
                          navigator.clipboard.writeText(String(children));
                        }}
                        className="px-2.5 py-1 text-xs font-medium rounded-md bg-gray-800 hover:bg-gray-700 text-white transition-colors flex items-center gap-1"
                      >
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
                        borderRadius: '10px',
                        padding: '20px',
                        fontSize: '13.5px',
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
  );
};
