// Search results shown in the sidebar while the search box has text

import React, { useEffect, useState } from 'react';
import { apiService } from '../services/api';
import type { ProjectSummary, SearchResponse } from '../types';

const SEARCH_DELAY_MS = 250;

interface SearchResultsProps {
  query: string;
  projects: ProjectSummary[];
  /** messageId is set when a message result was clicked, so the chat can scroll to it */
  onOpen: (sessionId: string, messageId?: string) => void;
}

const formatDate = (iso: string) => {
  const date = new Date(iso.endsWith('Z') || iso.includes('+') ? iso : `${iso}Z`);
  return Number.isNaN(date.getTime())
    ? ''
    : date.toLocaleDateString(undefined, { day: 'numeric', month: 'short', year: 'numeric' });
};

export const SearchResults: React.FC<SearchResultsProps> = ({ query, projects, onOpen }) => {
  const [results, setResults] = useState<SearchResponse | null>(null);
  const [searching, setSearching] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const projectNames = new Map(projects.map((p) => [p.project_id, p.name]));

  // Search after a short pause in typing; drop responses for older queries
  useEffect(() => {
    const controller = new AbortController();
    setSearching(true);
    const timer = window.setTimeout(async () => {
      try {
        const response = await apiService.search(query, null, controller.signal);
        setResults(response);
        setError(null);
      } catch (err) {
        if ((err as any)?.name === 'CanceledError' || controller.signal.aborted) return;
        console.error('Search failed:', err);
        setError('Search failed');
      } finally {
        if (!controller.signal.aborted) setSearching(false);
      }
    }, SEARCH_DELAY_MS);
    return () => {
      window.clearTimeout(timer);
      controller.abort();
    };
  }, [query]);

  const projectLabel = (projectId: string | null) =>
    projectId && projectNames.has(projectId) ? (
      <span className="shrink-0 max-w-[45%] truncate text-[11px] text-gray-400">{projectNames.get(projectId)}</span>
    ) : null;

  if (error) {
    return <div className="px-3 py-2 text-sm text-red-600">{error}</div>;
  }
  if (!results) {
    return <div className="px-3 py-2 text-sm text-gray-400">Searching…</div>;
  }

  const empty = results.sessions.length === 0 && results.messages.length === 0;

  return (
    <div className={`space-y-3 ${searching ? 'opacity-60' : ''}`}>
      {empty && !searching && (
        <div className="px-3 py-2 text-sm text-gray-400">No chats or messages match "{query.trim()}"</div>
      )}

      {results.sessions.length > 0 && (
        <div>
          <div className="px-3 py-1.5 text-xs font-medium text-gray-400 uppercase tracking-wide">Chat titles</div>
          <div className="space-y-0.5">
            {results.sessions.map((hit) => (
              <button
                key={hit.session_id}
                onClick={() => onOpen(hit.session_id)}
                className="w-full flex items-center gap-2 text-left px-3 py-2 rounded-md hover:bg-gray-100 focus:outline-none focus-visible:ring-1 focus-visible:ring-gray-400"
              >
                <span className="flex-1 truncate text-[13.5px] text-gray-800">{hit.title}</span>
                {projectLabel(hit.project_id)}
              </button>
            ))}
          </div>
        </div>
      )}

      {results.messages.length > 0 && (
        <div>
          <div className="px-3 py-1.5 text-xs font-medium text-gray-400 uppercase tracking-wide">Messages</div>
          <div className="space-y-0.5">
            {results.messages.map((hit) => (
              <button
                key={hit.message_id}
                onClick={() => onOpen(hit.session_id, hit.message_id)}
                className="w-full text-left px-3 py-2 rounded-md hover:bg-gray-100 focus:outline-none focus-visible:ring-1 focus-visible:ring-gray-400"
              >
                <div className="flex items-center gap-2 mb-0.5">
                  <span className="flex-1 truncate text-[12.5px] font-medium text-gray-800">{hit.session_title}</span>
                  {projectLabel(hit.project_id)}
                </div>
                <div className="text-xs text-gray-500 leading-snug line-clamp-3">
                  <span className="text-gray-400">{hit.role === 'user' ? 'You' : 'Assistant'}: </span>
                  {hit.snippet.map((part, i) =>
                    part.match ? (
                      <mark key={i} className="bg-yellow-100 text-gray-900 rounded-sm px-0.5">
                        {part.text}
                      </mark>
                    ) : (
                      <span key={i}>{part.text}</span>
                    ),
                  )}
                </div>
                <div className="mt-0.5 text-[11px] text-gray-400">{formatDate(hit.created_at)}</div>
              </button>
            ))}
          </div>
        </div>
      )}
    </div>
  );
};
