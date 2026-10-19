import type { AskResult, AskSession, Dashboard, DatasetListItem, DatasetSummary, DeckOptions, ExecSummary, Filter, Panel, QueryData, Story } from "./types";

async function req<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(`/api${path}`, init);
  if (!res.ok) {
    let msg = `${res.status} ${res.statusText}`;
    try {
      const body = await res.json();
      if (body?.detail) msg = typeof body.detail === "string" ? body.detail : JSON.stringify(body.detail);
    } catch {
      /* not JSON */
    }
    throw new Error(msg);
  }
  return res.json() as Promise<T>;
}

const json = (body: unknown): RequestInit => ({
  method: "POST",
  headers: { "Content-Type": "application/json" },
  body: JSON.stringify(body),
});

function files(list: File[]): FormData {
  const fd = new FormData();
  for (const f of list) fd.append("files", f);
  return fd;
}

const base = (ds: string, scope: string) => `/datasets/${ds}/dashboards/${encodeURIComponent(scope)}`;

export const api = {
  health: () => req<{ ok: boolean; llm: boolean; model: string | null; min_rows: number }>("/health"),
  list: () => req<DatasetListItem[]>("/datasets"),
  get: (id: string) => req<DatasetSummary>(`/datasets/${id}`),
  remove: (id: string) => req<{ ok: boolean }>(`/datasets/${id}`, { method: "DELETE" }),
  example: () => req<DatasetSummary>("/example", { method: "POST" }),
  upload: (list: File[]) => req<DatasetSummary>("/datasets", { method: "POST", body: files(list) }),
  addFiles: (id: string, list: File[]) => req<DatasetSummary>(`/datasets/${id}/files`, { method: "POST", body: files(list) }),
  removeFile: (id: string, stored: string) => req<DatasetSummary>(`/datasets/${id}/files/${encodeURIComponent(stored)}`, { method: "DELETE" }),
  preview: (id: string, table: string, o: { offset: number; limit: number; sort?: string; desc?: boolean; search?: string }) =>
    req<QueryData & { total: number; offset: number }>(
      `/datasets/${id}/tables/${encodeURIComponent(table)}/preview?` +
        new URLSearchParams({ offset: String(o.offset), limit: String(o.limit), sort: o.sort ?? "", desc: String(!!o.desc), search: o.search ?? "" }),
    ),
  fix: (id: string, fix: object) => req<DatasetSummary>(`/datasets/${id}/fix`, json(fix)),
  setup: (id: string, body: object) => req<DatasetSummary>(`/datasets/${id}/setup`, json(body)),
  generate: (id: string, scope: string) => req<Dashboard>(base(id, scope), { method: "POST" }),
  dashboard: (id: string, scope: string) => req<Dashboard>(base(id, scope)),
  filter: (id: string, scope: string, filters: Filter[]) => req<{ panels: Record<string, Panel> }>(`${base(id, scope)}/filter`, json({ filters })),
  ask: (id: string, scope: string, question: string, history: { role: string; text: string }[], filters: Filter[], sessionId: string) =>
    req<AskResult>(`${base(id, scope)}/ask`, json({ question, history, filters, session_id: sessionId })),
  askSessions: (id: string, scope: string) => req<{ sessions: AskSession[] }>(`${base(id, scope)}/ask/sessions`),
  askSession: (id: string, sessionId: string) =>
    req<{ messages: { asked_at: string; question: string; result: AskResult }[] }>(`/datasets/${id}/ask/sessions/${sessionId}`),
  askSessionDelete: (id: string, sessionId: string) => req<{ ok: boolean }>(`/datasets/${id}/ask/sessions/${sessionId}`, { method: "DELETE" }),
  redraw: (id: string, scope: string, panel: string, body: { instruction?: string; recipe?: object; filters: Filter[] }) =>
    req<Panel>(`${base(id, scope)}/panels/${panel}/redraw`, json(body)),
  undo: (id: string, scope: string, panel: string) => req<Panel>(`${base(id, scope)}/panels/${panel}/undo`, { method: "POST" }),
  addPanel: (id: string, scope: string, panel: Panel, section = -1) => req<Dashboard>(`${base(id, scope)}/panels`, json({ panel, section })),
  layout: (id: string, scope: string, story: Partial<Story>) =>
    req<Dashboard>(`${base(id, scope)}/layout`, { method: "PUT", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ story }) }),
  sql: (id: string, scope: string, sql: string) => req<QueryData>(`${base(id, scope)}/sql`, json({ sql })),
  deckOptions: () => req<DeckOptions>("/deck/themes"),
  summary: (id: string, scope: string, regenerate = false) => req<ExecSummary>(`${base(id, scope)}/summary?regenerate=${regenerate}`, { method: "POST" }),
  async summaryFile(id: string, scope: string, kind: "md" | "pdf"): Promise<{ blob: Blob; name: string }> {
    const res = await fetch(`/api${base(id, scope)}/summary/${kind}`);
    if (!res.ok) {
      let msg = `${res.status} ${res.statusText}`;
      try {
        msg = (await res.json()).detail ?? msg;
      } catch {
        /* ignore */
      }
      throw new Error(msg);
    }
    const name = (res.headers.get("Content-Disposition") ?? "").match(/filename="([^"]+)"/)?.[1] ?? `executive-summary.${kind}`;
    return { blob: await res.blob(), name };
  },
  async exportFile(id: string, scope: string, kind: "html" | "pdf" | "pptx", filters: Filter[], deck?: { design: string; palette: string; regenerate?: boolean }): Promise<{ blob: Blob; name: string }> {
    const res = await fetch(`/api${base(id, scope)}/export/${kind}${deck ? `?design=${encodeURIComponent(deck.design)}&palette=${encodeURIComponent(deck.palette)}${deck.regenerate ? "&regenerate=true" : ""}` : ""}`, json({ filters }));
    if (!res.ok) {
      let msg = `${res.status} ${res.statusText}`;
      try {
        msg = (await res.json()).detail ?? msg;
      } catch {
        /* ignore */
      }
      throw new Error(msg);
    }
    const cd = res.headers.get("Content-Disposition") ?? "";
    const name = cd.match(/filename="([^"]+)"/)?.[1] ?? `dashboard.${kind}`;
    return { blob: await res.blob(), name };
  },
};
