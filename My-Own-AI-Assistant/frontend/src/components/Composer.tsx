// Composer component for message input

import React, { useState, useRef } from 'react';

interface ComposerProps {
  onSend: (content: string, files: File[]) => void;
  disabled: boolean;
}

export const Composer: React.FC<ComposerProps> = ({ onSend, disabled }) => {
  const [content, setContent] = useState('');
  const [files, setFiles] = useState<File[]>([]);
  const fileInputRef = useRef<HTMLInputElement>(null);

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
      // Filter only allowed document types
      const validFiles = selectedFiles.filter(file => {
        const ext = file.name.toLowerCase();
        return ext.endsWith('.txt') || 
               ext.endsWith('.md') || 
               ext.endsWith('.doc') || 
               ext.endsWith('.docx') || 
               ext.endsWith('.pdf');
      });
      
      if (validFiles.length !== selectedFiles.length) {
        alert('Only text documents (.txt, .md, .pdf, .doc, .docx) are allowed');
      }
      
      setFiles(validFiles);
    }
  };

  const removeFile = (index: number) => {
    setFiles(files.filter((_, i) => i !== index));
  };

  const getFileIcon = (filename: string) => {
    const ext = filename.toLowerCase();
    if (ext.endsWith('.pdf')) return '📄';
    if (ext.endsWith('.doc') || ext.endsWith('.docx')) return '📝';
    if (ext.endsWith('.txt')) return '📃';
    if (ext.endsWith('.md')) return '📋';
    return '📎';
  };

  return (
    <form onSubmit={handleSubmit} className="border-t border-gray-200 px-8 py-6 bg-white">
      {files.length > 0 && (
        <div className="mb-4 flex flex-wrap gap-2">
          {files.map((file, index) => (
            <div key={index} className="flex items-center gap-2 bg-blue-50 border border-blue-200 px-4 py-2 rounded-xl text-sm">
              <span className="text-xl">{getFileIcon(file.name)}</span>
              <span className="text-gray-700 font-medium">{file.name}</span>
              <button
                type="button"
                onClick={() => removeFile(index)}
                className="ml-2 text-red-500 hover:text-red-700 font-bold text-xl leading-none"
              >
                ×
              </button>
            </div>
          ))}
        </div>
      )}
      
      <div className="flex gap-3 items-end">
        <input
          ref={fileInputRef}
          type="file"
          onChange={handleFileChange}
          className="hidden"
          multiple
          accept=".txt,.md,.pdf,.doc,.docx"
        />
        
        <button
          type="button"
          onClick={() => fileInputRef.current?.click()}
          disabled={disabled}
          className="p-3.5 bg-gray-100 hover:bg-gray-200 rounded-xl transition-all disabled:opacity-50 disabled:cursor-not-allowed"
          title="Attach document (.txt, .md, .pdf, .doc, .docx)"
        >
          <svg className="w-6 h-6 text-gray-600" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15.172 7l-6.586 6.586a2 2 0 102.828 2.828l6.414-6.586a4 4 0 00-5.656-5.656l-6.415 6.585a6 6 0 108.486 8.486L20.5 13" />
          </svg>
        </button>
        
        <div className="flex-1 border border-gray-300 rounded-2xl overflow-hidden bg-white hover:border-gray-400 focus-within:border-blue-500 focus-within:ring-2 focus-within:ring-blue-200 transition-all">
          <textarea
            value={content}
            onChange={(e) => setContent(e.target.value)}
            onKeyDown={handleKeyDown}
            placeholder="Type your message... (Shift+Enter for new line)"
            disabled={disabled}
            className="w-full px-6 py-4 resize-none focus:outline-none text-gray-900 leading-relaxed"
            style={{ minHeight: '60px', maxHeight: '200px' }}
            rows={1}
          />
        </div>
        
        <button
          type="submit"
          disabled={disabled || (!content.trim() && files.length === 0)}
          className="px-8 py-4 rounded-2xl font-medium transition-all disabled:opacity-50 disabled:cursor-not-allowed shadow-sm hover:shadow-md disabled:shadow-none"
          style={{
            background: disabled || (!content.trim() && files.length === 0) 
              ? '#e5e7eb' 
              : 'linear-gradient(135deg, #2563eb, #8b5cf6)',
            color: 'white'
          }}
        >
          <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 19l9 2-9-18-9 18 9-2zm0 0v-8" />
          </svg>
        </button>
      </div>
      
      <div className="mt-3 text-xs text-gray-500 text-center">
        Supported formats: Text (.txt, .md), PDF, Word (.doc, .docx)
      </div>
    </form>
  );
};
