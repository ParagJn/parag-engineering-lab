import { useState, useEffect, useRef } from 'react';
import { Sidebar } from './components/Sidebar';
import { ChatWindow } from './components/ChatWindow';
import type { ComposerHandle } from './components/Composer';
import type { RateLimitInfo } from './components/RateLimitTimer';
import { apiService } from './services/api';
import type { ModelProvider, Session, SessionListItem } from './types';

const RATE_LIMIT_WAIT_SECONDS = 90;

function App() {
  const [sessions, setSessions] = useState<SessionListItem[]>([]);
  const [currentSession, setCurrentSession] = useState<Session | null>(null);
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [rateLimitInfo, setRateLimitInfo] = useState<RateLimitInfo | null>(null);

  const composerRef = useRef<ComposerHandle>(null);
  const countdownIntervalRef = useRef<number | null>(null);
  const cancelRateLimitRef = useRef<(() => void) | null>(null);

  // Load sessions on mount
  useEffect(() => {
    loadSessions();
  }, []);

  // Make sure a running countdown doesn't keep firing after unmount
  useEffect(() => {
    return () => {
      if (countdownIntervalRef.current) {
        clearInterval(countdownIntervalRef.current);
      }
    };
  }, []);

  const loadSessions = async () => {
    try {
      const sessionList = await apiService.listSessions();
      setSessions(sessionList);
    } catch (err) {
      console.error('Failed to load sessions:', err);
      setError('Failed to load sessions');
    }
  };

  const handleNewSession = async () => {
    try {
      const newSession = await apiService.createSession();
      await loadSessions();

      // Load the new session
      const fullSession = await apiService.getSession(newSession.session_id);
      setCurrentSession(fullSession);
      setError(null);
    } catch (err) {
      console.error('Failed to create session:', err);
      setError('Failed to create new session');
    }
  };

  const handleSelectSession = async (sessionId: string) => {
    try {
      const session = await apiService.getSession(sessionId);
      setCurrentSession(session);
      setError(null);
    } catch (err) {
      console.error('Failed to load session:', err);
      setError('Failed to load session');
    }
  };

  const handleDeleteSession = async (sessionId: string) => {
    try {
      await apiService.deleteSession(sessionId);

      // If deleting current session, clear it
      if (currentSession?.session_id === sessionId) {
        setCurrentSession(null);
      }

      // Refresh session list
      await loadSessions();
      setError(null);
    } catch (err) {
      console.error('Failed to delete session:', err);
      setError('Failed to delete session');
    }
  };

  const handleRenameSession = async (sessionId: string, newTitle: string) => {
    try {
      await apiService.renameSession(sessionId, newTitle);

      // Refresh session list
      await loadSessions();

      // Update current session if it's the one being renamed
      if (currentSession?.session_id === sessionId) {
        const updatedSession = await apiService.getSession(sessionId);
        setCurrentSession(updatedSession);
      }

      setError(null);
    } catch (err) {
      console.error('Failed to rename session:', err);
      setError('Failed to rename session');
    }
  };

  const handleModelChange = async (model: ModelProvider) => {
    if (!currentSession) return;

    // Optimistic update so the dropdown feels immediate
    setCurrentSession({ ...currentSession, model });

    try {
      await apiService.updateSession(currentSession.session_id, { model });
      await loadSessions();
    } catch (err) {
      console.error('Failed to update model:', err);
      setError('Failed to update model');
    }
  };

  const handleWebSearchToggle = async (webSearchEnabled: boolean) => {
    if (!currentSession) return;

    setCurrentSession({ ...currentSession, web_search_enabled: webSearchEnabled });

    try {
      await apiService.updateSession(currentSession.session_id, { web_search_enabled: webSearchEnabled });
      await loadSessions();
    } catch (err) {
      console.error('Failed to update web search setting:', err);
      setError('Failed to update web search setting');
    }
  };

  // Starts a 90s countdown (shown via rateLimitInfo), then calls onDone once.
  const startRateLimitCountdown = (onDone: () => void) => {
    let secondsLeft = RATE_LIMIT_WAIT_SECONDS;
    setRateLimitInfo({ secondsLeft, total: RATE_LIMIT_WAIT_SECONDS });

    countdownIntervalRef.current = window.setInterval(() => {
      secondsLeft -= 1;
      if (secondsLeft <= 0) {
        if (countdownIntervalRef.current) {
          clearInterval(countdownIntervalRef.current);
          countdownIntervalRef.current = null;
        }
        setRateLimitInfo(null);
        onDone();
      } else {
        setRateLimitInfo({ secondsLeft, total: RATE_LIMIT_WAIT_SECONDS });
      }
    }, 1000);
  };

  const handleSendMessage = async (content: string, files: File[]) => {
    if (!currentSession) return;

    setIsLoading(true);
    setError(null);
    setRateLimitInfo(null);

    // Upload attachments once; a rate-limit retry reuses the same attachment ids.
    const attachmentIds: string[] = [];
    try {
      for (const file of files) {
        const attachment = await apiService.uploadAttachment(currentSession.session_id, file);
        attachmentIds.push(attachment.attachment_id);
      }
    } catch (err) {
      console.error('Failed to upload attachment:', err);
      setError('Failed to upload attachment. Please try again.');
      setIsLoading(false);
      return;
    }

    const attemptSend = async (isRetry: boolean) => {
      try {
        await apiService.sendMessage(currentSession.session_id, {
          content,
          attachment_ids: attachmentIds,
        });

        // Reload the current session to get updated messages
        const updatedSession = await apiService.getSession(currentSession.session_id);
        setCurrentSession(updatedSession);

        // Refresh session list to update timestamps
        await loadSessions();
        setIsLoading(false);
      } catch (err) {
        const status = (err as any)?.response?.status;

        if (status === 429) {
          if (!isRetry) {
            // Wait 90s (with a visible countdown), then retry exactly once.
            // The user can cancel the wait early via the timer's Cancel button.
            cancelRateLimitRef.current = () => {
              if (countdownIntervalRef.current) {
                clearInterval(countdownIntervalRef.current);
                countdownIntervalRef.current = null;
              }
              cancelRateLimitRef.current = null;
              setRateLimitInfo(null);
              composerRef.current?.restoreContent(content);
              setIsLoading(false);
            };
            startRateLimitCountdown(() => {
              cancelRateLimitRef.current = null;
              attemptSend(true);
            });
          } else {
            // Still rate-limited after the retry: give up and hand the prompt back.
            composerRef.current?.restoreContent(content);
            setError('Still getting rate-limited. Your message was restored to the input box — try again when ready.');
            setIsLoading(false);
          }
          return;
        }

        console.error('Failed to send message:', err);
        const detail = (err as any)?.response?.data?.detail;
        setError(detail ? `Failed to send message: ${detail}` : 'Failed to send message. Please try again.');
        setIsLoading(false);
      }
    };

    await attemptSend(false);
  };

  const handleCancelRateLimitWait = () => {
    cancelRateLimitRef.current?.();
  };

  return (
    <div className="flex h-screen bg-white">
      <Sidebar
        sessions={sessions}
        currentSessionId={currentSession?.session_id || null}
        onSelectSession={handleSelectSession}
        onNewSession={handleNewSession}
        onDeleteSession={handleDeleteSession}
        onRenameSession={handleRenameSession}
      />

      <div className="flex-1 flex flex-col">
        {error && (
          <div className="px-6 py-3 bg-red-50 border-b border-red-100">
            <p className="text-sm text-red-700">{error}</p>
          </div>
        )}

        {currentSession ? (
          <ChatWindow
            ref={composerRef}
            messages={currentSession.messages}
            onSendMessage={handleSendMessage}
            isLoading={isLoading}
            model={currentSession.model}
            onModelChange={handleModelChange}
            webSearchEnabled={currentSession.web_search_enabled}
            onWebSearchToggle={handleWebSearchToggle}
            rateLimitInfo={rateLimitInfo}
            onCancelRateLimitWait={handleCancelRateLimitWait}
          />
        ) : (
          <div className="flex-1 flex flex-col items-center justify-center bg-white px-6">
            <h1 className="text-3xl font-normal text-gray-900 mb-3">AI Assistant</h1>
            <p className="text-gray-500 mb-8">Your personal assistant for technical work and document analysis</p>
            <button
              onClick={handleNewSession}
              className="px-5 py-2.5 text-sm font-medium text-white bg-gray-900 rounded-lg hover:bg-gray-700 transition-colors"
            >
              Start a conversation
            </button>
          </div>
        )}
      </div>
    </div>
  );
}

export default App;
