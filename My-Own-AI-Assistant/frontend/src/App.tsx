import { useState, useEffect, useRef } from 'react';
import { Sidebar } from './components/Sidebar';
import { ChatWindow } from './components/ChatWindow';
import { ProjectSettings } from './components/ProjectSettings';
import type { ComposerHandle } from './components/Composer';
import type { RateLimitInfo } from './components/RateLimitTimer';
import { apiService } from './services/api';
import type {
  ModelProvider,
  ProjectDetail,
  ProjectSummary,
  Session,
  SessionListItem,
  SvgEditTarget,
} from './types';

const RATE_LIMIT_WAIT_SECONDS = 90;

function App() {
  const [sessions, setSessions] = useState<SessionListItem[]>([]);
  const [currentSession, setCurrentSession] = useState<Session | null>(null);
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [rateLimitInfo, setRateLimitInfo] = useState<RateLimitInfo | null>(null);
  const [streamingText, setStreamingText] = useState<string | null>(null);
  const [svgMode, setSvgMode] = useState(false);
  const [svgEditTarget, setSvgEditTarget] = useState<SvgEditTarget | null>(null);
  const [projects, setProjects] = useState<ProjectSummary[]>([]);
  const [currentProject, setCurrentProject] = useState<ProjectDetail | null>(null);
  // undefined = closed, null = creating a new project, string = editing that project
  const [settingsProjectId, setSettingsProjectId] = useState<string | null | undefined>(undefined);
  const [focusMessageId, setFocusMessageId] = useState<string | null>(null);

  const composerRef = useRef<ComposerHandle>(null);
  const countdownIntervalRef = useRef<number | null>(null);
  const cancelRateLimitRef = useRef<(() => void) | null>(null);

  // Load sessions on mount
  useEffect(() => {
    loadSessions();
    loadProjects();
  }, []);

  // Load the open chat's project (instructions, documents) for the header and pinning
  const currentProjectId = currentSession?.project_id ?? null;
  useEffect(() => {
    if (!currentProjectId) {
      setCurrentProject(null);
      return;
    }
    let cancelled = false;
    apiService
      .getProject(currentProjectId)
      .then((detail) => {
        if (!cancelled) setCurrentProject(detail);
      })
      .catch((err) => {
        console.error('Failed to load project:', err);
        if (!cancelled) setCurrentProject(null);
      });
    return () => {
      cancelled = true;
    };
  }, [currentProjectId]);

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

  const loadProjects = async () => {
    try {
      setProjects(await apiService.listProjects());
    } catch (err) {
      console.error('Failed to load projects:', err);
      setError('Failed to load projects');
    }
  };

  const handleNewSession = async (projectId?: string | null) => {
    try {
      const newSession = await apiService.createSession(projectId);
      await loadSessions();
      if (projectId) await loadProjects();

      // Load the new session
      const fullSession = await apiService.getSession(newSession.session_id);
      setCurrentSession(fullSession);
      setError(null);
    } catch (err) {
      console.error('Failed to create session:', err);
      setError('Failed to create new session');
    }
  };

  const handleSelectSession = async (sessionId: string, messageId?: string) => {
    try {
      const session = await apiService.getSession(sessionId);
      setFocusMessageId(messageId ?? null);
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
      await loadProjects();
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

  const handleMoveSession = async (sessionId: string, projectId: string | null) => {
    try {
      await apiService.moveSessionToProject(sessionId, projectId);
      if (currentSession?.session_id === sessionId) {
        setCurrentSession({ ...currentSession, project_id: projectId });
      }
      await Promise.all([loadSessions(), loadProjects()]);
      setError(null);
    } catch (err) {
      console.error('Failed to move chat:', err);
      const detail = (err as any)?.response?.data?.detail;
      setError(detail ? `Failed to move chat: ${detail}` : 'Failed to move chat');
    }
  };

  const handlePinAttachment = async (attachmentId: string) => {
    if (!currentProject) return;
    try {
      await apiService.pinDocumentToProject(currentProject.project_id, attachmentId);
      setCurrentProject(await apiService.getProject(currentProject.project_id));
      await loadProjects();
      setError(null);
    } catch (err) {
      console.error('Failed to pin file:', err);
      const detail = (err as any)?.response?.data?.detail;
      setError(detail ? `Couldn't add the file to the project: ${detail}` : "Couldn't add the file to the project");
    }
  };

  const handleProjectChanged = async (detail: ProjectDetail) => {
    // A new project stays open in the modal so documents can be added straight away
    if (settingsProjectId === null) setSettingsProjectId(detail.project_id);
    if (detail.project_id === currentProjectId) setCurrentProject(detail);
    await loadProjects();
  };

  const handleProjectDeleted = async (projectId: string, deletedChats: boolean) => {
    setSettingsProjectId(undefined);
    if (currentSession?.project_id === projectId) {
      setCurrentSession(deletedChats ? null : { ...currentSession, project_id: null });
    }
    await Promise.all([loadSessions(), loadProjects()]);
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

  // Edits refer to images in the open session, so drop the target when it changes
  useEffect(() => {
    setSvgEditTarget(null);
  }, [currentSession?.session_id]);

  const handleSvgModeToggle = (enabled: boolean) => {
    setSvgMode(enabled);
    if (!enabled) setSvgEditTarget(null);
  };

  const handleEditSvg = (target: SvgEditTarget) => {
    setSvgMode(true);
    setSvgEditTarget(target);
  };

  const handleGenerateSvg = async (prompt: string) => {
    if (!currentSession || !prompt.trim()) return;

    const previousSession = currentSession;
    setIsLoading(true);
    setError(null);

    // Show the prompt right away while the model draws
    setCurrentSession({
      ...currentSession,
      messages: [
        ...currentSession.messages,
        {
          id: 'pending-svg-prompt',
          role: 'user',
          content: prompt,
          created_at: new Date().toISOString(),
          attachments: [],
        },
      ],
    });

    try {
      const result = await apiService.generateSvgImage(
        currentSession.session_id,
        prompt,
        svgEditTarget?.svgImageId,
      );
      // Keep refining: the next prompt edits the version just produced
      if (svgEditTarget) {
        setSvgEditTarget({
          svgImageId: result.svg_image_id,
          version: result.message.svg_version ?? svgEditTarget.version + 1,
        });
      }
      const updatedSession = await apiService.getSession(currentSession.session_id);
      setCurrentSession(updatedSession);
      await loadSessions();
    } catch (err) {
      console.error('Failed to generate SVG image:', err);
      setCurrentSession(previousSession);
      composerRef.current?.restoreContent(prompt);
      const status = (err as any)?.response?.status;
      const detail = (err as any)?.response?.data?.detail;
      setError(
        status === 429
          ? 'Rate-limited by the model provider. Your prompt was restored — try again shortly.'
          : detail ? `Failed to generate SVG image: ${detail}` : 'Failed to generate SVG image. Please try again.'
      );
    } finally {
      setIsLoading(false);
    }
  };

  const handleSendMessage = async (content: string, files: File[]) => {
    if (!currentSession) return;

    if (svgMode) {
      await handleGenerateSvg(content);
      return;
    }

    setIsLoading(true);
    setError(null);
    setRateLimitInfo(null);
    setStreamingText(null);

    // Upload attachments once; a rate-limit retry reuses the same attachment ids.
    const attachmentIds: string[] = [];
    try {
      for (const file of files) {
        const attachment = await apiService.uploadAttachment(currentSession.session_id, file);
        attachmentIds.push(attachment.attachment_id);
      }
    } catch (err) {
      console.error('Failed to upload attachment:', err);
      const detail = (err as any)?.response?.data?.detail;
      setError(detail ? `Failed to upload attachment: ${detail}` : 'Failed to upload attachment. Please try again.');
      composerRef.current?.restoreContent(content);
      setIsLoading(false);
      return;
    }

    const attemptSend = (isRetry: boolean) => {
      setStreamingText(null);

      apiService.streamMessage(currentSession.session_id, {
        content,
        attachment_ids: attachmentIds,
      }, {
        onChunk: (text) => {
          setStreamingText((prev) => (prev ?? '') + text);
        },
        onDone: async () => {
          setStreamingText(null);
          // Reload the current session to get the persisted messages
          const updatedSession = await apiService.getSession(currentSession.session_id);
          setCurrentSession(updatedSession);
          await loadSessions();
          setIsLoading(false);
        },
        onError: (err) => {
          setStreamingText(null);
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
        },
      });
    };

    attemptSend(false);
  };

  const handleCancelRateLimitWait = () => {
    cancelRateLimitRef.current?.();
  };

  return (
    <div className="flex h-screen bg-white">
      <Sidebar
        sessions={sessions}
        projects={projects}
        currentSessionId={currentSession?.session_id || null}
        onSelectSession={handleSelectSession}
        onNewSession={handleNewSession}
        onDeleteSession={handleDeleteSession}
        onRenameSession={handleRenameSession}
        onNewProject={() => setSettingsProjectId(null)}
        onOpenProjectSettings={(projectId) => setSettingsProjectId(projectId)}
        onMoveSession={handleMoveSession}
        onOpenSearchResult={handleSelectSession}
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
            streamingText={streamingText}
            svgMode={svgMode}
            onSvgModeToggle={handleSvgModeToggle}
            svgEditTarget={svgMode ? svgEditTarget : null}
            onEditSvg={handleEditSvg}
            onClearSvgEdit={() => setSvgEditTarget(null)}
            project={currentProject}
            onOpenProject={() => currentProject && setSettingsProjectId(currentProject.project_id)}
            onPinAttachment={handlePinAttachment}
            focusMessageId={focusMessageId}
            onFocusHandled={() => setFocusMessageId(null)}
          />
        ) : (
          <div className="flex-1 flex flex-col items-center justify-center bg-white px-6">
            <h1 className="text-3xl font-normal text-gray-900 mb-3">AI Assistant</h1>
            <p className="text-gray-500 mb-8">Your personal assistant for technical work and document analysis</p>
            <button
              onClick={() => handleNewSession()}
              className="px-5 py-2.5 text-sm font-medium text-white bg-gray-900 rounded-lg hover:bg-gray-700 transition-colors"
            >
              Start a conversation
            </button>
          </div>
        )}
      </div>

      {settingsProjectId !== undefined && (
        <ProjectSettings
          key={settingsProjectId ?? 'new'}
          projectId={settingsProjectId}
          onClose={() => setSettingsProjectId(undefined)}
          onChanged={handleProjectChanged}
          onDeleted={handleProjectDeleted}
        />
      )}
    </div>
  );
}

export default App;
