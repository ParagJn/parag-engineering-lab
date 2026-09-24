// Message component for displaying chat messages

import React from 'react';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import rehypeRaw from 'rehype-raw';
import rehypeSanitize, { defaultSchema } from 'rehype-sanitize';
import { Prism as SyntaxHighlighter } from 'react-syntax-highlighter';
import { vscDarkPlus } from 'react-syntax-highlighter/dist/esm/styles/prism';
import type { Message as MessageType } from '../types';

// Allow the model's "web-sourced" attribution span through sanitization,
// on top of the default (GitHub-style) allowed HTML.
const sanitizeSchema = {
  ...defaultSchema,
  attributes: {
    ...defaultSchema.attributes,
    span: [...(defaultSchema.attributes?.span || []), 'className'],
  },
};

interface MessageProps {
  message: MessageType;
}

export const Message: React.FC<MessageProps> = ({ message }) => {
  const isUser = message.role === 'user';

  const handleDownload = () => {
    const blob = new Blob([message.content], { type: 'text/markdown' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `response-${message.id}.md`;
    a.click();
    URL.revokeObjectURL(url);
  };

  return (
    <div className="max-w-3xl mx-auto px-8 mb-8 animate-fadeIn">
      <div className={`flex items-center gap-2 text-xs font-medium text-gray-400 mb-1.5 ${isUser ? 'justify-end' : ''}`}>
        <span>{isUser ? 'You' : 'Assistant'}</span>
        {!isUser && message.content && (
          <button
            type="button"
            onClick={handleDownload}
            title="Download as Markdown"
            className="text-gray-400 hover:text-gray-700 transition-colors"
          >
            <svg width="12" height="12" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 4v12m0 0l-4-4m4 4l4-4M4 20h16" />
            </svg>
          </button>
        )}
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
            rehypePlugins={[rehypeRaw, [rehypeSanitize, sanitizeSchema]]}
            components={{
              a({ href, children, ...props }: any) {
                return (
                  <a href={href} target="_blank" rel="noopener noreferrer" {...props}>
                    {children}
                  </a>
                );
              },
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
