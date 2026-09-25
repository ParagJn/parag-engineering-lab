// Composer component for message input

import React, { useState, useRef, useImperativeHandle, forwardRef } from 'react';
import type { ModelProvider, SvgEditTarget } from '../types';

const MAX_FILE_SIZE_BYTES = 5 * 1024 * 1024; // 5MB

interface ComposerProps {
  onSend: (content: string, files: File[]) => void;
  disabled: boolean;
  model: ModelProvider;
  onModelChange: (model: ModelProvider) => void;
  webSearchEnabled: boolean;
  onWebSearchToggle: (enabled: boolean) => void;
  /** SVG image mode — the prompt is drawn as an SVG instead of answered as chat. */
  svgMode: boolean;
  onSvgModeToggle: (enabled: boolean) => void;
  /** When set (and in SVG mode), the next prompt edits this image. */
  svgEditTarget: SvgEditTarget | null;
  onClearSvgEdit: () => void;
}

export interface ComposerHandle {
  /** Put text back into the input box (e.g. after a send ultimately failed). */
  restoreContent: (text: string) => void;
}

export const Composer = forwardRef<ComposerHandle, ComposerProps>(({
  onSend,
  disabled,
  model,
  onModelChange,
  webSearchEnabled,
  onWebSearchToggle,
  svgMode,
  onSvgModeToggle,
  svgEditTarget,
  onClearSvgEdit,
}, ref) => {
  const [content, setContent] = useState('');
  const [files, setFiles] = useState<File[]>([]);
  const fileInputRef = useRef<HTMLInputElement>(null);

  useImperativeHandle(ref, () => ({
    restoreContent: (text: string) => setContent(text),
  }));

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    if (content.trim() || files.length > 0) {
      onSend(content, files);
      setContent('');
      setFiles([]);
    }
  };

  const handleKeyDown = (e: React.KeyboardEvent<HTMLTextAreaElement>) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      handleSubmit(e);
    }
  };

  const handleFileChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    if (e.target.files) {
      const selectedFiles = Array.from(e.target.files);
      const typeValidFiles = selectedFiles.filter(file => {
        const ext = file.name.toLowerCase();
        return ext.endsWith('.txt') ||
               ext.endsWith('.md') ||
               ext.endsWith('.doc') ||
               ext.endsWith('.docx') ||
               ext.endsWith('.pdf');
      });

      if (typeValidFiles.length !== selectedFiles.length) {
        alert('Only text documents (.txt, .md, .pdf, .doc, .docx) are allowed');
      }

      const validFiles = typeValidFiles.filter(file => file.size <= MAX_FILE_SIZE_BYTES);
      const oversizedFiles = typeValidFiles.filter(file => file.size > MAX_FILE_SIZE_BYTES);

      if (oversizedFiles.length > 0) {
        alert(`These files exceed the 5MB limit and were not attached: ${oversizedFiles.map(f => f.name).join(', ')}`);
      }

      setFiles(validFiles);
    }
  };

  const removeFile = (index: number) => {
    setFiles(files.filter((_, i) => i !== index));
  };

  return (
    <div className="px-8 pb-6">
      <form onSubmit={handleSubmit} className="max-w-3xl mx-auto">
        <div className="border border-gray-200 rounded-2xl bg-white shadow-sm focus-within:border-gray-300 transition-colors">
          {files.length > 0 && (
            <div className="flex flex-wrap gap-2 px-4 pt-4">
              {files.map((file, index) => (
                <div key={index} className="flex items-center gap-2 bg-gray-100 px-3 py-1.5 rounded-lg text-xs text-gray-700">
                  <span className="truncate max-w-[160px]">{file.name}</span>
                  <button
                    type="button"
                    onClick={() => removeFile(index)}
                    className="text-gray-400 hover:text-gray-700 leading-none"
                  >
                    ×
                  </button>
                </div>
              ))}
            </div>
          )}

          {svgEditTarget && (
            <div className="flex px-4 pt-4">
              <div className="flex items-center gap-2 bg-gray-900 text-white px-3 py-1.5 rounded-lg text-xs">
                <span>Editing SVG v{svgEditTarget.version}</span>
                <button
                  type="button"
                  onClick={onClearSvgEdit}
                  title="Stop editing — next prompt creates a new image"
                  className="text-gray-300 hover:text-white leading-none"
                >
                  ×
                </button>
              </div>
            </div>
          )}

          <textarea
            value={content}
            onChange={(e) => setContent(e.target.value)}
            onKeyDown={handleKeyDown}
            placeholder={
              svgEditTarget ? `Describe the changes to make to v${svgEditTarget.version}...`
              : svgMode ? 'Describe the SVG image to generate...'
              : 'Message the assistant...'
            }
            disabled={disabled}
            className="w-full px-5 pt-4 pb-2 resize-none bg-transparent text-gray-900 placeholder-gray-400 leading-relaxed disabled:opacity-60"
            style={{ minHeight: '52px', maxHeight: '200px' }}
            rows={1}
          />

          <div className="flex items-center justify-between px-3 pb-3 pt-1">
            <div className="flex items-center gap-1.5">
              <input
                ref={fileInputRef}
                type="file"
                onChange={handleFileChange}
                className="hidden"
                multiple
                accept=".txt,.md,.pdf,.doc,.docx"
              />
              {!svgMode && (
              <button
                type="button"
                onClick={() => fileInputRef.current?.click()}
                disabled={disabled}
                className="p-2 rounded-full text-gray-500 hover:bg-gray-100 disabled:opacity-50 transition-colors"
                title="Attach document (.txt, .md, .pdf, .doc, .docx)"
              >
                <svg width="18" height="18" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 4v16m8-8H4" />
                </svg>
              </button>
              )}

              <select
                value={model}
                onChange={(e) => onModelChange(e.target.value as ModelProvider)}
                disabled={disabled}
                className="text-xs font-medium text-gray-600 bg-transparent border border-gray-200 rounded-full pl-3 pr-2 py-1.5 hover:bg-gray-50 disabled:opacity-50 cursor-pointer"
              >
                <option value="claude">Claude Opus 5.5</option>
                <option value="gemini">Gemini 3.7 Flash</option>
                <option value="openai">GPT-5.6 Sol</option>
              </select>

              {!svgMode && (
              <button
                type="button"
                onClick={() => onWebSearchToggle(!webSearchEnabled)}
                disabled={disabled}
                title="Let the assistant search the web when needed"
                className={`flex items-center gap-1.5 text-xs font-medium rounded-full pl-2.5 pr-3 py-1.5 border transition-colors disabled:opacity-50 ${
                  webSearchEnabled
                    ? 'bg-gray-900 text-white border-gray-900'
                    : 'text-gray-600 bg-transparent border-gray-200 hover:bg-gray-50'
                }`}
              >
                <svg width="14" height="14" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <circle cx="12" cy="12" r="9" strokeWidth={2} />
                  <path strokeLinecap="round" strokeWidth={2} d="M3 12h18M12 3c2.5 2.7 4 6 4 9s-1.5 6.3-4 9c-2.5-2.7-4-6-4-9s1.5-6.3 4-9z" />
                </svg>
                Web search
              </button>
              )}

              <button
                type="button"
                onClick={() => onSvgModeToggle(!svgMode)}
                disabled={disabled}
                title="Generate an SVG image from your prompt"
                className={`flex items-center gap-1.5 text-xs font-medium rounded-full pl-2.5 pr-3 py-1.5 border transition-colors disabled:opacity-50 ${
                  svgMode
                    ? 'bg-gray-900 text-white border-gray-900'
                    : 'text-gray-600 bg-transparent border-gray-200 hover:bg-gray-50'
                }`}
              >
                <svg width="14" height="14" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <rect x="3" y="3" width="18" height="18" rx="2" strokeWidth={2} />
                  <circle cx="8.5" cy="8.5" r="1.5" strokeWidth={2} />
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M21 15l-5-5L5 21" />
                </svg>
                SVG image
              </button>
            </div>

            <button
              type="submit"
              disabled={disabled || (!content.trim() && files.length === 0)}
              className="w-8 h-8 flex items-center justify-center rounded-full bg-gray-900 text-white disabled:bg-gray-200 disabled:text-gray-400 transition-colors"
            >
              <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2.5} d="M12 19V5m0 0l-6 6m6-6l6 6" />
              </svg>
            </button>
          </div>
        </div>

        <div className="mt-2 text-xs text-gray-400 text-center">
          {svgMode
            ? 'SVG mode: the selected model will draw your prompt as a downloadable SVG image'
            : 'Supports .txt, .md, .pdf, .doc, .docx attachments (max 5MB)'}
        </div>
      </form>
    </div>
  );
});

Composer.displayName = 'Composer';
