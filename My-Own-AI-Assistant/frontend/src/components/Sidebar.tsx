// Sidebar component for session management

import React, { useState } from 'react';
import type { SessionListItem } from '../types';

interface SidebarProps {
  sessions: SessionListItem[];
  currentSessionId: string | null;
  onSelectSession: (sessionId: string) => void;
  onNewSession: () => void;
  onDeleteSession: (sessionId: string) => void;
  onRenameSession: (sessionId: string, newTitle: string) => void;
}

export const Sidebar: React.FC<SidebarProps> = ({
  sessions,
  currentSessionId,
  onSelectSession,
  onNewSession,
  onDeleteSession,
  onRenameSession,
}) => {
  const [editingSessionId, setEditingSessionId] = useState<string | null>(null);
  const [editTitle, setEditTitle] = useState('');
  const [sessionsExpanded, setSessionsExpanded] = useState(true);

  const handleStartEdit = (session: SessionListItem, e: React.MouseEvent) => {
    e.stopPropagation();
    setEditingSessionId(session.session_id);
    setEditTitle(session.title);
  };

  const handleSaveEdit = (sessionId: string) => {
    if (editTitle.trim()) {
      onRenameSession(sessionId, editTitle.trim());
    }
    setEditingSessionId(null);
    setEditTitle('');
  };

  const handleCancelEdit = () => {
    setEditingSessionId(null);
    setEditTitle('');
  };

  const SessionItem: React.FC<{ session: SessionListItem }> = ({ session }) => {
    const isEditing = editingSessionId === session.session_id;
    const isActive = currentSessionId === session.session_id;

    if (isEditing) {
      return (
        <div className="px-3 py-2">
          <input
            type="text"
            value={editTitle}
            onChange={(e) => setEditTitle(e.target.value)}
            onKeyDown={(e) => {
              if (e.key === 'Enter') handleSaveEdit(session.session_id);
              if (e.key === 'Escape') handleCancelEdit();
            }}
            className="w-full px-2 py-1.5 text-sm border border-gray-300 rounded-md bg-white focus:outline-none focus:ring-1 focus:ring-gray-400"
            autoFocus
          />
          <div className="flex gap-2 mt-1.5">
            <button
              onClick={() => handleSaveEdit(session.session_id)}
              className="flex-1 px-2 py-1 text-xs text-white bg-gray-900 rounded-md hover:bg-gray-700"
            >
              Save
            </button>
            <button
              onClick={handleCancelEdit}
              className="flex-1 px-2 py-1 text-xs text-gray-600 bg-white border border-gray-200 rounded-md hover:bg-gray-50"
            >
              Cancel
            </button>
          </div>
        </div>
      );
    }

    return (
      <div
        className={`group flex items-center gap-1 rounded-md pr-1 ${
          isActive ? 'bg-gray-200/70' : 'hover:bg-gray-100'
        }`}
      >
        <button
          onClick={() => onSelectSession(session.session_id)}
          className="flex-1 text-left px-3 py-2 min-w-0"
        >
          <div className="truncate text-[13.5px] text-gray-800">{session.title}</div>
        </button>
        <div className="flex gap-0.5 opacity-0 group-hover:opacity-100 transition-opacity">
          <button
            onClick={(e) => handleStartEdit(session, e)}
            className="p-1.5 rounded-md hover:bg-gray-200 text-gray-500 hover:text-gray-800"
            title="Rename"
          >
            <svg className="w-3.5 h-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M11 5H6a2 2 0 00-2 2v11a2 2 0 002 2h11a2 2 0 002-2v-5m-1.414-9.414a2 2 0 112.828 2.828L11.828 15H9v-2.828l8.586-8.586z" />
            </svg>
          </button>
          <button
            onClick={(e) => {
              e.stopPropagation();
              if (window.confirm('Delete this conversation?')) {
                onDeleteSession(session.session_id);
              }
            }}
            className="p-1.5 rounded-md hover:bg-gray-200 text-gray-500 hover:text-gray-800"
            title="Delete"
          >
            <svg className="w-3.5 h-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16" />
            </svg>
          </button>
        </div>
      </div>
    );
  };

  return (
    <div className="w-72 bg-gray-50 border-r border-gray-200 flex flex-col h-screen">
      <div className="p-4">
        <button
          onClick={onNewSession}
          className="w-full flex items-center justify-center gap-2 px-3 py-2 text-sm text-gray-700 bg-white border border-gray-200 rounded-lg hover:bg-gray-100 transition-colors"
        >
          <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 4v16m8-8H4" />
          </svg>
          New chat
        </button>
      </div>

      <div className="flex-1 overflow-y-auto px-2 pb-4">
        <button
          onClick={() => setSessionsExpanded((v) => !v)}
          className="w-full flex items-center justify-between px-3 py-2 text-xs font-medium text-gray-400 uppercase tracking-wide hover:text-gray-600"
        >
          Sessions
          <svg
            className={`w-3.5 h-3.5 transition-transform ${sessionsExpanded ? '' : '-rotate-90'}`}
            fill="none"
            stroke="currentColor"
            viewBox="0 0 24 24"
          >
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 9l-7 7-7-7" />
          </svg>
        </button>

        {sessionsExpanded && (
          <div className="space-y-0.5 mt-1">
            {sessions.map((session) => (
              <SessionItem key={session.session_id} session={session} />
            ))}
            {sessions.length === 0 && (
              <div className="px-3 py-2 text-sm text-gray-400">No conversations yet</div>
            )}
          </div>
        )}
      </div>
    </div>
  );
};
