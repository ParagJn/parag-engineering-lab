// Message component for displaying chat messages

import React, { useState } from 'react';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import rehypeRaw from 'rehype-raw';
import rehypeSanitize, { defaultSchema } from 'rehype-sanitize';
import { Prism as SyntaxHighlighter } from 'react-syntax-highlighter';
import { vscDarkPlus } from 'react-syntax-highlighter/dist/esm/styles/prism';
import { apiService } from '../services/api';
import type { Message as MessageType, SvgEditTarget, SvgExportFormat } from '../types';

// Allow the model's "web-sourced" attribution span through sanitization,
// on top of the default (GitHub-style) allowed HTML.
const sanitizeSchema = {
  ...defaultSchema,
  attributes: {
    ...defaultSchema.attributes,
    span: [...(defaultSchema.attributes?.span || []), 'className'],
  },
};

const IMAGE_FILE_PATTERN = /\.(png|jpe?g|gif|webp)$/i;

interface MessageProps {
  message: MessageType;
  onEditSvg?: (target: SvgEditTarget) => void;
  isSvgEditTarget?: boolean;
  /** Files already pinned to the chat's project */
  pinnedAttachmentIds?: Set<string>;
  /** Set when the chat is in a project: offers to pin a sent file to it */
  onPinAttachment?: (attachmentId: string) => void;
  /** Briefly highlighted after jumping here from search */
  highlighted?: boolean;
}

export const Message: React.FC<MessageProps> = ({
  message,
  onEditSvg,
  isSvgEditTarget = false,
  pinnedAttachmentIds,
  onPinAttachment,
  highlighted = false,
}) => {
  const isUser = message.role === 'user';
  const svgImageId = message.svg_image_id;
  const isImage = (att: { filename: string; mime_type?: string | null }) =>
    IMAGE_FILE_PATTERN.test(att.filename) || !!att.mime_type?.startsWith('image/');
  const sentImages = (message.attachments || []).filter(isImage);
  const sentFiles = (message.attachments || []).filter((att) => !isImage(att));
  const [exporting, setExporting] = useState<SvgExportFormat | null>(null);
  const [exportError, setExportError] = useState<string | null>(null);

  const handleExport = async (format: SvgExportFormat) => {
    if (!svgImageId) return;
    setExporting(format);
    setExportError(null);
    try {
      const blob = await apiService.exportSvgImage(svgImageId, format);
      const url = URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = `${svgImageId}.${format}`;
      a.click();
      URL.revokeObjectURL(url);
    } catch (err) {
      setExportError(err instanceof Error ? err.message : 'Export failed');
    } finally {
      setExporting(null);
    }
  };

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
    <div
      id={`msg-${message.id}`}
      className={`max-w-3xl mx-auto px-8 mb-8 animate-fadeIn scroll-mt-6 rounded-xl transition-colors duration-700 ${
        highlighted ? 'bg-yellow-50 ring-1 ring-yellow-200 py-3' : ''
      }`}
    >
      <div className={`flex items-center gap-2 text-xs font-medium text-gray-400 mb-1.5 ${isUser ? 'justify-end' : ''}`}>
        <span>{isUser ? 'You' : 'Assistant'}</span>
        {!isUser && message.content && !svgImageId && (
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
      {svgImageId ? (
        <div className={`border rounded-2xl overflow-hidden ${isSvgEditTarget ? 'border-gray-900' : 'border-gray-200'}`}>
          {/* Rendered via <img> so any markup in the SVG can't run scripts */}
          <div className="bg-gray-50 p-4 flex justify-center">
            <img
              src={apiService.svgImageUrl(svgImageId)}
              alt={message.content}
              className="max-w-full max-h-[480px] object-contain"
            />
          </div>
          <div className="flex items-center justify-between px-4 py-2.5 border-t border-gray-200 bg-white">
            <span className="text-xs text-gray-500 truncate mr-3">
              v{message.svg_version ?? 1} · {svgImageId}.svg
            </span>
            <div className="flex items-center gap-2 shrink-0">
              {onEditSvg && (
                <button
                  type="button"
                  onClick={() => onEditSvg({ svgImageId, version: message.svg_version ?? 1 })}
                  disabled={isSvgEditTarget}
                  title="Refine this image with more prompts"
                  className="flex items-center gap-1.5 text-xs font-medium text-gray-700 border border-gray-200 hover:bg-gray-50 disabled:opacity-50 rounded-full px-3 py-1.5 transition-colors"
                >
                  <svg width="12" height="12" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15.2 5.2l3.6 3.6M4 20l4.5-1 10.3-10.3a2.5 2.5 0 00-3.6-3.6L4.9 15.4 4 20z" />
                  </svg>
                  {isSvgEditTarget ? 'Editing' : 'Edit'}
                </button>
              )}
              {(['mp4', 'gif'] as const).map((format) => (
                <button
                  key={format}
                  type="button"
                  onClick={() => handleExport(format)}
                  disabled={exporting !== null}
                  title={`Experimental: render the image (with any animations) as ${format.toUpperCase()}`}
                  className="flex items-center gap-1.5 text-xs font-medium text-gray-700 border border-gray-200 hover:bg-gray-50 disabled:opacity-50 rounded-full px-3 py-1.5 transition-colors"
                >
                  <svg width="12" height="12" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 4v12m0 0l-4-4m4 4l4-4M4 20h16" />
                  </svg>
                  {exporting === format ? 'Rendering…' : format.toUpperCase()}
                </button>
              ))}
              <a
                href={apiService.svgImageUrl(svgImageId, true)}
                className="flex items-center gap-1.5 text-xs font-medium text-white bg-gray-900 hover:bg-gray-700 rounded-full px-3 py-1.5 transition-colors shrink-0"
              >
                <svg width="12" height="12" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 4v12m0 0l-4-4m4 4l4-4M4 20h16" />
                </svg>
                Download SVG
              </a>
            </div>
          </div>
          {exportError && (
            <div className="px-4 py-2 border-t border-red-100 bg-red-50 text-xs text-red-700">
              {exportError}
            </div>
          )}
        </div>
      ) : isUser ? (
        <div className="flex flex-col items-end gap-2">
          {sentImages.length > 0 && (
            <div className="flex flex-wrap justify-end gap-2 max-w-[85%]">
              {sentImages.map((att) => (
                <a
                  key={att.attachment_id}
                  href={apiService.attachmentImageUrl(att.attachment_id)}
                  target="_blank"
                  rel="noopener noreferrer"
                  title={att.filename}
                >
                  <img
                    src={apiService.attachmentImageUrl(att.attachment_id)}
                    alt={att.filename}
                    className="h-32 max-w-[240px] object-cover rounded-xl border border-gray-200 hover:opacity-90 transition-opacity"
                  />
                </a>
              ))}
            </div>
          )}
          {sentFiles.length > 0 && (
            <div className="flex flex-wrap justify-end gap-2 max-w-[85%]">
              {sentFiles.map((att) => {
                const pinned = pinnedAttachmentIds?.has(att.attachment_id);
                return (
                  <div
                    key={att.attachment_id}
                    className="flex items-center gap-1.5 pl-2.5 pr-1.5 py-1 text-xs text-gray-700 border border-gray-200 rounded-lg bg-white"
                  >
                    <svg className="w-3.5 h-3.5 text-gray-400 shrink-0" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" />
                    </svg>
                    <span className="truncate max-w-[200px]" title={att.filename}>{att.filename}</span>
                    {pinned ? (
                      <span className="px-1.5 text-[11px] text-gray-400" title="This file is in the project's documents">
                        In project
                      </span>
                    ) : onPinAttachment ? (
                      <button
                        type="button"
                        onClick={() => onPinAttachment(att.attachment_id)}
                        className="px-1.5 py-0.5 text-[11px] font-medium text-gray-600 rounded hover:bg-gray-100 hover:text-gray-900"
                        title="Add to the project's documents, so every chat in the project can use it"
                      >
                        Pin to project
                      </button>
                    ) : null}
                  </div>
                );
              })}
            </div>
          )}
          {message.content && (
            <div className="max-w-[85%] bg-gray-100 rounded-2xl px-4 py-2.5 whitespace-pre-wrap text-gray-900 leading-relaxed">
              {message.content}
            </div>
          )}
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
