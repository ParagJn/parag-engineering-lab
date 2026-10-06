// Modal for creating a project and managing its instructions and documents

import React, { useEffect, useRef, useState } from 'react';
import { apiService } from '../services/api';
import type { ProjectDetail } from '../types';

const ACCEPTED_FILES = '.txt,.md,.pdf,.doc,.docx,.png,.jpg,.jpeg,.gif,.webp';

interface ProjectSettingsProps {
  /** null = create a new project */
  projectId: string | null;
  onClose: () => void;
  /** Called after anything changes, so the sidebar and chat header can refresh */
  onChanged: (project: ProjectDetail) => void;
  onDeleted: (projectId: string, deletedChats: boolean) => void;
}

const formatTokens = (tokens: number) =>
  tokens >= 1000 ? `${(tokens / 1000).toFixed(tokens >= 10000 ? 0 : 1)}k` : String(tokens);

const formatSize = (bytes: number) =>
  bytes >= 1024 * 1024 ? `${(bytes / (1024 * 1024)).toFixed(1)} MB` : `${Math.max(1, Math.round(bytes / 1024))} KB`;

const errorDetail = (err: unknown, fallback: string) =>
  (err as any)?.response?.data?.detail || fallback;

export const ProjectSettings: React.FC<ProjectSettingsProps> = ({ projectId, onClose, onChanged, onDeleted }) => {
  const [project, setProject] = useState<ProjectDetail | null>(null);
  const [name, setName] = useState('');
  const [description, setDescription] = useState('');
  const [instructions, setInstructions] = useState('');
  const [loading, setLoading] = useState(projectId !== null);
  const [saving, setSaving] = useState(false);
  const [uploading, setUploading] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [savedNotice, setSavedNotice] = useState(false);
  const [confirmDelete, setConfirmDelete] = useState(false);
  const [deleteChats, setDeleteChats] = useState(false);
  const fileInputRef = useRef<HTMLInputElement>(null);

  const applyProject = (detail: ProjectDetail) => {
    setProject(detail);
    setName(detail.name);
    setDescription(detail.description);
    setInstructions(detail.instructions);
  };

  useEffect(() => {
    if (!projectId) return;
    setLoading(true);
    apiService
      .getProject(projectId)
      .then(applyProject)
      .catch((err) => setError(errorDetail(err, 'Failed to load project')))
      .finally(() => setLoading(false));
  }, [projectId]);

  // Close on Escape
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if (e.key === 'Escape') onClose();
    };
    window.addEventListener('keydown', onKey);
    return () => window.removeEventListener('keydown', onKey);
  }, [onClose]);

  const isDirty =
    !project ||
    name.trim() !== project.name ||
    description.trim() !== project.description ||
    instructions.trim() !== project.instructions;

  const handleSave = async () => {
    if (!name.trim()) {
      setError('Project name is required');
      return;
    }
    setSaving(true);
    setError(null);
    try {
      const detail = project
        ? await apiService.updateProject(project.project_id, { name, description, instructions })
        : await apiService.createProject(name, description, instructions);
      applyProject(detail);
      onChanged(detail);
      setSavedNotice(true);
      window.setTimeout(() => setSavedNotice(false), 2000);
    } catch (err) {
      setError(errorDetail(err, 'Failed to save project'));
    } finally {
      setSaving(false);
    }
  };

  const refresh = async (id: string) => {
    const detail = await apiService.getProject(id);
    setProject(detail);
    onChanged(detail);
  };

  const handleUpload = async (files: FileList | null) => {
    if (!project || !files?.length) return;
    setError(null);
    const failures: string[] = [];
    for (const file of Array.from(files)) {
      setUploading(file.name);
      try {
        await apiService.uploadProjectDocument(project.project_id, file);
      } catch (err) {
        failures.push(`${file.name}: ${errorDetail(err, 'upload failed')}`);
      }
    }
    setUploading(null);
    if (fileInputRef.current) fileInputRef.current.value = '';
    if (failures.length) setError(failures.join('\n'));
    await refresh(project.project_id).catch(() => undefined);
  };

  const handleRemoveDocument = async (attachmentId: string, filename: string) => {
    if (!project) return;
    if (!window.confirm(`Remove "${filename}" from this project?`)) return;
    setError(null);
    try {
      await apiService.removeProjectDocument(project.project_id, attachmentId);
      await refresh(project.project_id);
    } catch (err) {
      setError(errorDetail(err, 'Failed to remove file'));
    }
  };

  const handleDelete = async () => {
    if (!project) return;
    setError(null);
    try {
      await apiService.deleteProject(project.project_id, deleteChats);
      onDeleted(project.project_id, deleteChats);
    } catch (err) {
      setError(errorDetail(err, 'Failed to delete project'));
    }
  };

  const budget = project?.context_budget_tokens ?? 0;
  const used = project?.context_tokens ?? 0;
  const usedPercent = budget ? Math.min(100, (used / budget) * 100) : 0;

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center bg-black/30 px-4"
      onMouseDown={(e) => {
        if (e.target === e.currentTarget) onClose();
      }}
    >
      <div className="w-full max-w-2xl max-h-[90vh] flex flex-col bg-white rounded-2xl shadow-xl border border-gray-200">
        <div className="flex items-center justify-between px-6 py-4 border-b border-gray-100">
          <h2 className="text-base font-medium text-gray-900">
            {project ? 'Project settings' : 'New project'}
          </h2>
          <button
            onClick={onClose}
            className="p-1.5 rounded-md text-gray-400 hover:text-gray-800 hover:bg-gray-100"
            title="Close"
          >
            <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
            </svg>
          </button>
        </div>

        {loading ? (
          <div className="px-6 py-10 text-sm text-gray-400 text-center">Loading…</div>
        ) : (
          <div className="flex-1 overflow-y-auto px-6 py-5 space-y-6">
            {error && (
              <div className="px-3 py-2 text-sm text-red-700 bg-red-50 border border-red-100 rounded-lg whitespace-pre-wrap">
                {error}
              </div>
            )}

            <section className="space-y-3">
              <div>
                <label className="block text-xs font-medium text-gray-500 mb-1">Name</label>
                <input
                  type="text"
                  value={name}
                  maxLength={100}
                  onChange={(e) => setName(e.target.value)}
                  placeholder="e.g. Tax return 2026"
                  className="w-full px-3 py-2 text-sm border border-gray-200 rounded-lg focus:outline-none focus:ring-1 focus:ring-gray-400"
                  autoFocus={!projectId}
                />
              </div>
              <div>
                <label className="block text-xs font-medium text-gray-500 mb-1">Description (for you only)</label>
                <input
                  type="text"
                  value={description}
                  onChange={(e) => setDescription(e.target.value)}
                  placeholder="What this project is about"
                  className="w-full px-3 py-2 text-sm border border-gray-200 rounded-lg focus:outline-none focus:ring-1 focus:ring-gray-400"
                />
              </div>
              <div>
                <label className="block text-xs font-medium text-gray-500 mb-1">Instructions</label>
                <textarea
                  value={instructions}
                  onChange={(e) => setInstructions(e.target.value)}
                  rows={5}
                  placeholder="Sent with every message in this project, e.g. &quot;Answer in bullet points. I'm based in Germany.&quot;"
                  className="w-full px-3 py-2 text-sm border border-gray-200 rounded-lg focus:outline-none focus:ring-1 focus:ring-gray-400 resize-y"
                />
                <p className="mt-1 text-xs text-gray-400">
                  Treated as preferences. They never override the assistant's accuracy rules.
                </p>
              </div>
              <div className="flex items-center justify-end gap-3">
                {savedNotice && <span className="text-xs text-green-700">Saved</span>}
                <button
                  onClick={handleSave}
                  disabled={saving || !isDirty || !name.trim()}
                  className="px-4 py-2 text-sm font-medium text-white bg-gray-900 rounded-lg hover:bg-gray-700 disabled:opacity-40 transition-colors"
                >
                  {saving ? 'Saving…' : project ? 'Save changes' : 'Create project'}
                </button>
              </div>
            </section>

            {project && (
              <section className="space-y-3">
                <div className="flex items-center justify-between">
                  <h3 className="text-sm font-medium text-gray-900">Documents</h3>
                  <button
                    onClick={() => fileInputRef.current?.click()}
                    disabled={uploading !== null}
                    className="flex items-center gap-1.5 px-3 py-1.5 text-xs font-medium text-gray-700 border border-gray-200 rounded-full hover:bg-gray-50 disabled:opacity-50"
                  >
                    <svg className="w-3.5 h-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 4v16m8-8H4" />
                    </svg>
                    {uploading ? `Reading ${uploading}…` : 'Add files'}
                  </button>
                  <input
                    ref={fileInputRef}
                    type="file"
                    multiple
                    accept={ACCEPTED_FILES}
                    className="hidden"
                    onChange={(e) => handleUpload(e.target.files)}
                  />
                </div>
                <p className="text-xs text-gray-400">
                  The text of these files is sent with every message in this project. Files too large for the
                  budget are refused rather than cut off.
                </p>

                <div>
                  <div className="flex justify-between text-xs text-gray-500 mb-1">
                    <span>Context used</span>
                    <span>
                      ~{formatTokens(used)} of {formatTokens(budget)} tokens
                    </span>
                  </div>
                  <div className="h-1.5 bg-gray-100 rounded-full overflow-hidden">
                    <div
                      className={`h-full rounded-full ${usedPercent > 85 ? 'bg-amber-500' : 'bg-gray-800'}`}
                      style={{ width: `${usedPercent}%` }}
                    />
                  </div>
                </div>

                {project.documents.length === 0 ? (
                  <div className="px-3 py-4 text-sm text-gray-400 text-center border border-dashed border-gray-200 rounded-lg">
                    No documents yet
                  </div>
                ) : (
                  <ul className="divide-y divide-gray-100 border border-gray-200 rounded-lg">
                    {project.documents.map((doc) => (
                      <li key={doc.attachment_id} className="flex items-center gap-3 px-3 py-2">
                        <svg className="w-4 h-4 text-gray-400 shrink-0" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" />
                        </svg>
                        <div className="flex-1 min-w-0">
                          <div className="truncate text-sm text-gray-800">{doc.filename}</div>
                          <div className="text-xs text-gray-400">
                            {formatSize(doc.size_bytes)} · ~{formatTokens(doc.tokens)} tokens
                          </div>
                        </div>
                        <button
                          onClick={() => handleRemoveDocument(doc.attachment_id, doc.filename)}
                          className="p-1.5 rounded-md text-gray-400 hover:text-gray-800 hover:bg-gray-100"
                          title="Remove from project"
                        >
                          <svg className="w-3.5 h-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
                          </svg>
                        </button>
                      </li>
                    ))}
                  </ul>
                )}
              </section>
            )}

            {project && (
              <section className="pt-4 border-t border-gray-100">
                {!confirmDelete ? (
                  <button
                    onClick={() => setConfirmDelete(true)}
                    className="text-sm text-red-600 hover:text-red-800"
                  >
                    Delete project
                  </button>
                ) : (
                  <div className="space-y-3 p-3 bg-red-50 border border-red-100 rounded-lg">
                    <p className="text-sm text-red-800">
                      Delete "{project.name}"? Files used only by this project are deleted.
                    </p>
                    {project.session_count > 0 && (
                      <label className="flex items-center gap-2 text-sm text-red-800">
                        <input
                          type="checkbox"
                          checked={deleteChats}
                          onChange={(e) => setDeleteChats(e.target.checked)}
                        />
                        Also delete its {project.session_count} chat{project.session_count === 1 ? '' : 's'}
                        {!deleteChats && ' (otherwise they move to Chats)'}
                      </label>
                    )}
                    <div className="flex gap-2">
                      <button
                        onClick={handleDelete}
                        className="px-3 py-1.5 text-sm font-medium text-white bg-red-600 rounded-lg hover:bg-red-700"
                      >
                        Delete
                      </button>
                      <button
                        onClick={() => {
                          setConfirmDelete(false);
                          setDeleteChats(false);
                        }}
                        className="px-3 py-1.5 text-sm text-gray-700 bg-white border border-gray-200 rounded-lg hover:bg-gray-50"
                      >
                        Cancel
                      </button>
                    </div>
                  </div>
                )}
              </section>
            )}
          </div>
        )}
      </div>
    </div>
  );
};
