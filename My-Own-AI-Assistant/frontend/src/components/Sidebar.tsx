// Sidebar component for session management

import React, { useEffect, useRef, useState } from 'react';
import type { ProjectSummary, SessionListItem } from '../types';
import { SearchResults } from './SearchResults';

const DEFAULT_WIDTH = 288;
const MIN_WIDTH = 220;
const MAX_WIDTH = 600;
const WIDTH_STORAGE_KEY = 'sidebarWidth';

const clampWidth = (width: number) =>
  Math.round(Math.min(Math.min(MAX_WIDTH, window.innerWidth * 0.6), Math.max(MIN_WIDTH, width)));

const loadWidth = () => {
  try {
    const saved = Number(localStorage.getItem(WIDTH_STORAGE_KEY));
    return saved ? clampWidth(saved) : DEFAULT_WIDTH;
  } catch {
    return DEFAULT_WIDTH;
  }
};

const saveWidth = (width: number) => {
  try {
    localStorage.setItem(WIDTH_STORAGE_KEY, String(width));
  } catch {
    // ignore: the width just won't be remembered
  }
};

interface SidebarProps {
  sessions: SessionListItem[];
  projects: ProjectSummary[];
  currentSessionId: string | null;
  onSelectSession: (sessionId: string) => void;
  onNewSession: (projectId?: string | null) => void;
  onDeleteSession: (sessionId: string) => void;
  onRenameSession: (sessionId: string, newTitle: string) => void;
  onNewProject: () => void;
  onOpenProjectSettings: (projectId: string) => void;
  onMoveSession: (sessionId: string, projectId: string | null) => void;
  /** Open a chat from search; messageId scrolls to that message */
  onOpenSearchResult: (sessionId: string, messageId?: string) => void;
}

const SectionHeader: React.FC<{ label: string; expanded: boolean; onToggle: () => void; action?: React.ReactNode }> = ({
  label,
  expanded,
  onToggle,
  action,
}) => (
  <div className="flex items-center justify-between pr-1">
    <button
      onClick={onToggle}
      className="flex-1 flex items-center gap-1.5 px-3 py-2 text-xs font-medium text-gray-400 uppercase tracking-wide hover:text-gray-600"
    >
      <svg
        className={`w-3.5 h-3.5 transition-transform ${expanded ? '' : '-rotate-90'}`}
        fill="none"
        stroke="currentColor"
        viewBox="0 0 24 24"
      >
        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 9l-7 7-7-7" />
      </svg>
      {label}
    </button>
    {action}
  </div>
);

export const Sidebar: React.FC<SidebarProps> = ({
  sessions,
  projects,
  currentSessionId,
  onSelectSession,
  onNewSession,
  onDeleteSession,
  onRenameSession,
  onNewProject,
  onOpenProjectSettings,
  onMoveSession,
  onOpenSearchResult,
}) => {
  const [editingSessionId, setEditingSessionId] = useState<string | null>(null);
  const [editTitle, setEditTitle] = useState('');
  const [sessionsExpanded, setSessionsExpanded] = useState(true);
  const [projectsExpanded, setProjectsExpanded] = useState(true);
  const [expandedProjectIds, setExpandedProjectIds] = useState<Set<string>>(new Set());
  const [movingSessionId, setMovingSessionId] = useState<string | null>(null);
  const [searchQuery, setSearchQuery] = useState('');
  const [width, setWidth] = useState(loadWidth);
  const [resizing, setResizing] = useState(false);
  const widthRef = useRef(width);
  widthRef.current = width;

  // Drag the right edge to resize; the width is remembered in this browser
  const startResize = (e: React.PointerEvent) => {
    e.preventDefault();
    const startX = e.clientX;
    const startWidth = widthRef.current;
    setResizing(true);
    document.body.style.cursor = 'col-resize';
    document.body.style.userSelect = 'none';

    const onMove = (event: PointerEvent) => setWidth(clampWidth(startWidth + event.clientX - startX));
    const onUp = () => {
      window.removeEventListener('pointermove', onMove);
      window.removeEventListener('pointerup', onUp);
      document.body.style.cursor = '';
      document.body.style.userSelect = '';
      setResizing(false);
      saveWidth(widthRef.current);
    };
    window.addEventListener('pointermove', onMove);
    window.addEventListener('pointerup', onUp);
  };

  const resetWidth = () => {
    setWidth(DEFAULT_WIDTH);
    saveWidth(DEFAULT_WIDTH);
  };
  const isSearching = searchQuery.trim().length > 0;

  const projectIds = new Set(projects.map((p) => p.project_id));
  // A chat whose project no longer exists is shown under Chats
  const looseSessions = sessions.filter((s) => !s.project_id || !projectIds.has(s.project_id));

  // Open the project that holds the current chat
  const currentProjectId = sessions.find((s) => s.session_id === currentSessionId)?.project_id;
  useEffect(() => {
    if (currentProjectId) {
      setExpandedProjectIds((prev) => (prev.has(currentProjectId) ? prev : new Set(prev).add(currentProjectId)));
    }
  }, [currentProjectId]);

  const toggleProject = (projectId: string) => {
    setExpandedProjectIds((prev) => {
      const next = new Set(prev);
      if (next.has(projectId)) next.delete(projectId);
      else next.add(projectId);
      return next;
    });
  };

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
    const isMoving = movingSessionId === session.session_id;

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
        <div
          className={`relative flex gap-0.5 transition-opacity ${
            isMoving ? 'opacity-100' : 'opacity-0 group-hover:opacity-100'
          }`}
        >
          <button
            onClick={(e) => {
              e.stopPropagation();
              setMovingSessionId(isMoving ? null : session.session_id);
            }}
            className="p-1.5 rounded-md hover:bg-gray-200 text-gray-500 hover:text-gray-800"
            title="Move to project"
          >
            <svg className="w-3.5 h-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M3 7a2 2 0 012-2h4l2 2h8a2 2 0 012 2v8a2 2 0 01-2 2H5a2 2 0 01-2-2V7z" />
            </svg>
          </button>
          {isMoving && (
            <>
              <div className="fixed inset-0 z-10" onClick={() => setMovingSessionId(null)} />
              <div className="absolute right-0 top-8 z-20 w-52 py-1 bg-white border border-gray-200 rounded-lg shadow-lg">
                <div className="px-3 py-1.5 text-xs text-gray-400">Move to</div>
                {projects.map((project) => (
                  <button
                    key={project.project_id}
                    onClick={() => {
                      setMovingSessionId(null);
                      onMoveSession(session.session_id, project.project_id);
                    }}
                    disabled={project.project_id === session.project_id}
                    className="w-full text-left px-3 py-1.5 text-sm text-gray-700 hover:bg-gray-100 disabled:text-gray-300 disabled:hover:bg-transparent truncate"
                  >
                    {project.name}
                  </button>
                ))}
                {projects.length === 0 && (
                  <div className="px-3 py-1.5 text-sm text-gray-400">No projects yet</div>
                )}
                {session.project_id && (
                  <button
                    onClick={() => {
                      setMovingSessionId(null);
                      onMoveSession(session.session_id, null);
                    }}
                    className="w-full text-left px-3 py-1.5 text-sm text-gray-700 hover:bg-gray-100 border-t border-gray-100"
                  >
                    Remove from project
                  </button>
                )}
              </div>
            </>
          )}
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
    <div
      className="relative shrink-0 bg-gray-50 border-r border-gray-200 flex flex-col h-screen"
      style={{ width }}
    >
      <div
        onPointerDown={startResize}
        onDoubleClick={resetWidth}
        className={`absolute top-0 -right-1 z-30 h-full w-2 cursor-col-resize transition-colors ${
          resizing ? 'bg-gray-300' : 'hover:bg-gray-200'
        }`}
        title="Drag to resize, double-click to reset"
      />
      <div className="p-4">
        <button
          onClick={() => onNewSession()}
          className="w-full flex items-center justify-center gap-2 px-3 py-2 text-sm text-gray-700 bg-white border border-gray-200 rounded-lg hover:bg-gray-100 transition-colors"
        >
          <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 4v16m8-8H4" />
          </svg>
          New chat
        </button>
        <div className="relative mt-3">
          <svg
            className="absolute left-2.5 top-1/2 -translate-y-1/2 w-3.5 h-3.5 text-gray-400"
            fill="none"
            stroke="currentColor"
            viewBox="0 0 24 24"
          >
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M21 21l-4.35-4.35M17 11a6 6 0 11-12 0 6 6 0 0112 0z" />
          </svg>
          <input
            type="text"
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            onKeyDown={(e) => {
              if (e.key === 'Escape') setSearchQuery('');
            }}
            placeholder="Search chats"
            className="w-full pl-8 pr-7 py-1.5 text-sm bg-white border border-gray-200 rounded-lg focus:outline-none focus:ring-1 focus:ring-gray-400"
          />
          {isSearching && (
            <button
              onClick={() => setSearchQuery('')}
              className="absolute right-1.5 top-1/2 -translate-y-1/2 p-1 rounded text-gray-400 hover:text-gray-700"
              title="Clear search"
            >
              <svg className="w-3 h-3" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
              </svg>
            </button>
          )}
        </div>
      </div>

      <div className="flex-1 overflow-y-auto px-2 pb-4">
        {isSearching ? (
          <SearchResults query={searchQuery} projects={projects} onOpen={onOpenSearchResult} />
        ) : (
        <>
        <SectionHeader
          label="Projects"
          expanded={projectsExpanded}
          onToggle={() => setProjectsExpanded((v) => !v)}
          action={
            <button
              onClick={onNewProject}
              className="p-1.5 rounded-md text-gray-400 hover:text-gray-800 hover:bg-gray-200"
              title="New project"
            >
              <svg className="w-3.5 h-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 4v16m8-8H4" />
              </svg>
            </button>
          }
        />

        {projectsExpanded && (
          <div className="space-y-0.5 mt-1 mb-3">
            {projects.map((project) => {
              const expanded = expandedProjectIds.has(project.project_id);
              const projectSessions = sessions.filter((s) => s.project_id === project.project_id);
              return (
                <div key={project.project_id}>
                  <div className="group flex items-center gap-1 rounded-md pr-1 hover:bg-gray-100">
                    <button
                      onClick={() => toggleProject(project.project_id)}
                      className="flex-1 flex items-center gap-2 text-left px-3 py-2 min-w-0"
                      title={project.description || project.name}
                    >
                      <svg className="w-4 h-4 text-gray-500 shrink-0" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                        <path
                          strokeLinecap="round"
                          strokeLinejoin="round"
                          strokeWidth={2}
                          d={
                            expanded
                              ? 'M5 19a2 2 0 01-2-2V7a2 2 0 012-2h4l2 2h4a2 2 0 012 2v1M5 19h14a2 2 0 002-2v-5a2 2 0 00-2-2H9a2 2 0 00-2 2v5a2 2 0 01-2 2z'
                              : 'M3 7a2 2 0 012-2h4l2 2h8a2 2 0 012 2v8a2 2 0 01-2 2H5a2 2 0 01-2-2V7z'
                          }
                        />
                      </svg>
                      <span className="truncate text-[13.5px] font-medium text-gray-800">{project.name}</span>
                      {project.document_count > 0 && (
                        <span className="shrink-0 text-[11px] text-gray-400">{project.document_count} docs</span>
                      )}
                    </button>
                    <div className="flex gap-0.5 opacity-0 group-hover:opacity-100 transition-opacity">
                      <button
                        onClick={() => {
                          setExpandedProjectIds((prev) => new Set(prev).add(project.project_id));
                          onNewSession(project.project_id);
                        }}
                        className="p-1.5 rounded-md hover:bg-gray-200 text-gray-500 hover:text-gray-800"
                        title="New chat in this project"
                      >
                        <svg className="w-3.5 h-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 4v16m8-8H4" />
                        </svg>
                      </button>
                      <button
                        onClick={() => onOpenProjectSettings(project.project_id)}
                        className="p-1.5 rounded-md hover:bg-gray-200 text-gray-500 hover:text-gray-800"
                        title="Project settings and documents"
                      >
                        <svg className="w-3.5 h-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M10.325 4.317c.426-1.756 2.924-1.756 3.35 0a1.724 1.724 0 002.573 1.066c1.543-.94 3.31.826 2.37 2.37a1.724 1.724 0 001.065 2.572c1.756.426 1.756 2.924 0 3.35a1.724 1.724 0 00-1.066 2.573c.94 1.543-.826 3.31-2.37 2.37a1.724 1.724 0 00-2.572 1.065c-.426 1.756-2.924 1.756-3.35 0a1.724 1.724 0 00-2.573-1.066c-1.543.94-3.31-.826-2.37-2.37a1.724 1.724 0 00-1.065-2.572c-1.756-.426-1.756-2.924 0-3.35a1.724 1.724 0 001.066-2.573c-.94-1.543.826-3.31 2.37-2.37.996.608 2.296.07 2.572-1.065z" />
                          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15 12a3 3 0 11-6 0 3 3 0 016 0z" />
                        </svg>
                      </button>
                    </div>
                  </div>
                  {expanded && (
                    <div className="ml-4 pl-2 border-l border-gray-200 space-y-0.5">
                      {projectSessions.map((session) => (
                        <SessionItem key={session.session_id} session={session} />
                      ))}
                      {projectSessions.length === 0 && (
                        <button
                          onClick={() => onNewSession(project.project_id)}
                          className="w-full text-left px-3 py-1.5 text-sm text-gray-400 hover:text-gray-700"
                        >
                          Start a chat
                        </button>
                      )}
                    </div>
                  )}
                </div>
              );
            })}
            {projects.length === 0 && (
              <button
                onClick={onNewProject}
                className="w-full text-left px-3 py-2 text-sm text-gray-400 hover:text-gray-700"
              >
                Create a project to group chats with shared files and instructions
              </button>
            )}
          </div>
        )}

        <SectionHeader label="Chats" expanded={sessionsExpanded} onToggle={() => setSessionsExpanded((v) => !v)} />

        {sessionsExpanded && (
          <div className="space-y-0.5 mt-1">
            {looseSessions.map((session) => (
              <SessionItem key={session.session_id} session={session} />
            ))}
            {looseSessions.length === 0 && (
              <div className="px-3 py-2 text-sm text-gray-400">No conversations yet</div>
            )}
          </div>
        )}
        </>
        )}
      </div>
    </div>
  );
};
