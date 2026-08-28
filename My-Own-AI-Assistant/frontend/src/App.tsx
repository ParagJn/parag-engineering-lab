import { useState, useEffect } from 'react';
import { Sidebar } from './components/Sidebar';
import { ChatWindow } from './components/ChatWindow';
import { apiService } from './services/api';
import type { Session, SessionListItem } from './types';

function App() {
  const [sessions, setSessions] = useState<SessionListItem[]>([]);
  const [currentSession, setCurrentSession] = useState<Session | null>(null);
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  // Load sessions on mount
  useEffect(() => {
    loadSessions();
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

  const handleSendMessage = async (content: string, files: File[]) => {
    if (!currentSession) return;

    setIsLoading(true);
    setError(null);

    try {
      // Upload attachments first
      const attachmentIds: string[] = [];
      for (const file of files) {
        const attachment = await apiService.uploadAttachment(currentSession.session_id, file);
        attachmentIds.push(attachment.attachment_id);
      }

      // Send message
      await apiService.sendMessage(currentSession.session_id, {
        content,
        attachment_ids: attachmentIds,
      });

      // Reload the current session to get updated messages
      const updatedSession = await apiService.getSession(currentSession.session_id);
      setCurrentSession(updatedSession);

      // Refresh session list to update timestamps
      await loadSessions();
    } catch (err) {
      console.error('Failed to send message:', err);
      setError('Failed to send message. Please try again.');
    } finally {
      setIsLoading(false);
    }
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
          <div className="px-6 py-4 google-border-accent" style={{ backgroundColor: '#fef7f7', borderLeftColor: '#EA4335' }}>
            <div className="flex items-center gap-3">
              <span className="text-2xl">⚠️</span>
              <p className="text-gray-800 font-medium">{error}</p>
            </div>
          </div>
        )}

        {currentSession ? (
          <ChatWindow
            messages={currentSession.messages}
            onSendMessage={handleSendMessage}
            isLoading={isLoading}
          />
        ) : (
          <div className="flex-1 flex items-start justify-start bg-gray-50 p-6">
            <div className="text-left w-full">
              <div className="mb-8">
                <h1 className="text-6xl font-light mb-6 bg-gradient-to-r from-blue-600 via-red-500 via-yellow-500 to-green-600 bg-clip-text text-transparent">
                  AI Assistant
                </h1>
                <p className="text-lg text-gray-600 mb-8">Your personal AI companion for technical work and document analysis</p>
              </div>
              <button
                onClick={handleNewSession}
                className="px-8 py-4 text-base font-medium rounded-full shadow-lg hover:shadow-xl transition-all google-border-subtle"
                style={{ 
                  background: 'linear-gradient(135deg, #4285F4, #EA4335)',
                  color: 'white'
                }}
              >
                <span className="mr-2">✨</span>
                Start a Conversation
              </button>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}

export default App;
