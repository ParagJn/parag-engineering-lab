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

  // Group sessions by date
  const today = new Date();
  const yesterday = new Date(today);
  yesterday.setDate(yesterday.getDate() - 1);

  const groupedSessions = {
    today: [] as SessionListItem[],
    yesterday: [] as SessionListItem[],
    earlier: [] as SessionListItem[],
  };

  sessions.forEach((session) => {
    const sessionDate = new Date(session.updated_at);
    if (sessionDate.toDateString() === today.toDateString()) {
      groupedSessions.today.push(session);
    } else if (sessionDate.toDateString() === yesterday.toDateString()) {
      groupedSessions.yesterday.push(session);
    } else {
      groupedSessions.earlier.push(session);
    }
  });

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

    return (
      <div
        className={`group w-full px-4 py-3 rounded-xl mb-2 transition-all ${
          currentSessionId === session.session_id
            ? 'bg-blue-50 border-l-4 border-blue-600 shadow-sm'
            : 'hover:bg-gray-50 border-l-4 border-transparent'
        }`}
      >
        {isEditing ? (
          <div className="flex flex-col gap-2">
            <input
              type="text"
              value={editTitle}
              onChange={(e) => setEditTitle(e.target.value)}
              onKeyDown={(e) => {
                if (e.key === 'Enter') handleSaveEdit(session.session_id);
                if (e.key === 'Escape') handleCancelEdit();
              }}
              className="w-full px-2 py-1 text-sm border border-blue-500 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500"
              autoFocus
            />
            <div className="flex gap-2">
              <button
                onClick={() => handleSaveEdit(session.session_id)}
                className="flex-1 px-3 py-1 text-xs bg-blue-600 text-white rounded-lg hover:bg-blue-700"
              >
                Save
              </button>
              <button
                onClick={handleCancelEdit}
                className="flex-1 px-3 py-1 text-xs bg-gray-300 text-gray-700 rounded-lg hover:bg-gray-400"
              >
                Cancel
              </button>
            </div>
          </div>
        ) : (
          <div className="flex items-start justify-between gap-2">
            <button
              onClick={() => onSelectSession(session.session_id)}
              className="flex-1 text-left min-w-0"
            >
              <div className="truncate text-sm font-medium text-gray-800">{session.title}</div>
              <div className="text-xs text-gray-500 mt-1">
                {new Date(session.updated_at).toLocaleDateString()}
              </div>
            </button>
            <div className="flex gap-1 opacity-0 group-hover:opacity-100 transition-opacity">
              <button
                onClick={(e) => handleStartEdit(session, e)}
                className="p-1.5 hover:bg-blue-50 rounded-lg transition-all text-blue-600 hover:text-blue-700"
                title="Rename conversation"
              >
                <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
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
                className="p-1.5 hover:bg-red-50 rounded-lg transition-all text-red-500 hover:text-red-600"
                title="Delete conversation"
              >
                <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16" />
                </svg>
              </button>
            </div>
          </div>
        )}
      </div>
    );
  };

  return (
    <div className="w-80 bg-white border-r border-gray-200 flex flex-col h-screen">
      <div className="p-6 border-b border-gray-200">
        <h1 className="text-2xl font-bold mb-4 bg-gradient-to-r from-blue-600 to-purple-600 bg-clip-text text-transparent">
          AI Assistant
        </h1>
        <button
          onClick={onNewSession}
          className="w-full px-5 py-3 text-sm font-medium text-white bg-blue-600 hover:bg-blue-700 rounded-xl transition-all shadow-sm hover:shadow-md flex items-center justify-center gap-2"
        >
          <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 4v16m8-8H4" />
          </svg>
          New Conversation
        </button>
      </div>

      <div className="flex-1 overflow-y-auto p-4">
        {groupedSessions.today.length > 0 && (
          <div className="mb-6">
            <h3 className="text-xs font-semibold text-gray-500 mb-3 px-2 uppercase tracking-wide">Today</h3>
            {groupedSessions.today.map((session) => (
              <SessionItem key={session.session_id} session={session} />
            ))}
          </div>
        )}

        {groupedSessions.yesterday.length > 0 && (
          <div className="mb-6">
            <h3 className="text-xs font-semibold text-gray-500 mb-3 px-2 uppercase tracking-wide">Yesterday</h3>
            {groupedSessions.yesterday.map((session) => (
              <SessionItem key={session.session_id} session={session} />
            ))}
          </div>
        )}

        {groupedSessions.earlier.length > 0 && (
          <div className="mb-6">
            <h3 className="text-xs font-semibold text-gray-500 mb-3 px-2 uppercase tracking-wide">Earlier</h3>
            {groupedSessions.earlier.map((session) => (
              <SessionItem key={session.session_id} session={session} />
            ))}
          </div>
        )}
      </div>
    </div>
  );
};
