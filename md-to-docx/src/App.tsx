import JSZip from "jszip";
import { useCallback, useEffect, useRef, useState } from "react";
import { DropZone } from "./components/DropZone";
import { FileCard } from "./components/FileCard";
import { HistoryPanel } from "./components/HistoryPanel";
import { ArchiveIcon, RefreshIcon, ShieldIcon } from "./components/icons";
import { PasteDialog } from "./components/PasteDialog";
import { PreviewDialog } from "./components/PreviewDialog";
import type { PageSize } from "./converter/types";
import { convertFile } from "./lib/convertFile";
import { dateStamp, downloadBlob, isMarkdown, type PickedFile } from "./lib/files";
import {
  clearHistory,
  deleteHistory,
  getHistoryBlob,
  listHistory,
  saveHistory,
  type HistoryEntry,
} from "./lib/history";
import { basename, normalizePath, stem } from "./lib/paths";
import type { Item } from "./types";

const PAGE_SIZE_KEY = "md-to-docx.pageSize";

function loadPageSize(): PageSize {
  try {
    return localStorage.getItem(PAGE_SIZE_KEY) === "Letter" ? "Letter" : "A4";
  } catch {
    return "A4";
  }
}

/** `name.docx`, or `name (2).docx`, `name (3).docx`… if already used. */
function uniqueName(base: string, taken: Set<string>): string {
  let name = `${base}.docx`;
  for (let n = 2; taken.has(name); n++) name = `${base} (${n}).docx`;
  return name;
}

export default function App() {
  const [items, setItems] = useState<Item[]>([]);
  const [history, setHistory] = useState<HistoryEntry[]>([]);
  const [pageSize, setPageSize] = useState<PageSize>(loadPageSize);
  const [previewId, setPreviewId] = useState<string | null>(null);
  const [pasting, setPasting] = useState(false);
  /** Non-markdown files (images) by relative path, used to resolve references. */
  const assets = useRef(new Map<string, File>());
  const busy = useRef(false);

  const refreshHistory = useCallback(() => listHistory().then(setHistory), []);
  useEffect(() => void refreshHistory(), [refreshHistory]);

  const patch = (id: string, rev: number, changes: Partial<Item>) =>
    setItems((list) => list.map((i) => (i.id === id && i.rev === rev ? { ...i, ...changes } : i)));

  const requeueAll = () =>
    setItems((list) => list.map((i) => ({ ...i, status: "queued", rev: i.rev + 1 })));

  // Convert queued files one at a time (Mermaid rendering isn't safe to run concurrently).
  useEffect(() => {
    if (busy.current) return;
    const next = items.find((i) => i.status === "queued");
    if (!next) return;
    busy.current = true;
    patch(next.id, next.rev, { status: "converting" });
    convertFile(next.text, next.path, assets.current, { pageSize })
      .then(async ({ blob, meta, warnings }) => {
        patch(next.id, next.rev, { status: "done", blob, warnings, title: meta.title, error: undefined });
        await saveHistory(
          { id: next.historyId, name: next.outName, source: next.path, size: blob.size, createdAt: Date.now() },
          blob,
        );
        await refreshHistory();
      })
      .catch((err: unknown) => {
        console.error(err);
        patch(next.id, next.rev, { status: "error", error: err instanceof Error ? err.message : String(err) });
      })
      .finally(() => {
        busy.current = false;
        // Nudge the effect so the next queued item starts.
        setItems((list) => [...list]);
      });
  }, [items, pageSize, refreshHistory]);

  const addFiles = async (picked: PickedFile[]) => {
    const markdown = picked.filter((p) => isMarkdown(p.path));
    const others = picked.filter((p) => !isMarkdown(p.path));
    for (const p of others) assets.current.set(normalizePath(p.path), p.file);
    const loaded = await Promise.all(
      markdown.map(async (p) => ({ path: normalizePath(p.path), text: await p.file.text() })),
    );
    addMarkdown(loaded, others.length > 0);
  };

  const addMarkdown = (files: { path: string; text: string }[], requeueExisting = false) => {
    const stamp = dateStamp();
    setItems((list) => {
      const next = requeueExisting ? list.map((i) => ({ ...i, status: "queued" as const, rev: i.rev + 1 })) : [...list];
      const taken = new Set([...next.map((i) => i.outName), ...history.map((h) => h.name)]);
      for (const f of files) {
        // Skip exact re-drops; anything else is a new document, even if the name matches.
        if (next.some((i) => i.path === f.path && i.text === f.text)) continue;
        const outName = uniqueName(`${stem(f.path)}_${stamp}`, taken);
        taken.add(outName);
        next.push({
          id: crypto.randomUUID(),
          historyId: crypto.randomUUID(),
          path: f.path,
          name: basename(f.path),
          text: f.text,
          status: "queued",
          rev: 0,
          outName,
          warnings: [],
        });
      }
      return next;
    });
  };

  const changePageSize = (size: PageSize) => {
    if (size === pageSize) return;
    setPageSize(size);
    try {
      localStorage.setItem(PAGE_SIZE_KEY, size);
    } catch {
      // preference only
    }
    requeueAll();
  };

  const download = (item: Item) => item.blob && downloadBlob(item.blob, item.outName);

  const downloadZip = async () => {
    const zip = new JSZip();
    for (const i of items) if (i.blob) zip.file(i.outName, i.blob);
    downloadBlob(await zip.generateAsync({ type: "blob" }), `converted_documents_${dateStamp()}.zip`);
  };

  const ready = items.filter((i) => i.status === "done").length;
  const working = items.some((i) => i.status === "queued" || i.status === "converting");
  const preview = items.find((i) => i.id === previewId);

  return (
    <div className="min-h-screen bg-gradient-to-b from-slate-50 to-slate-100">
      <header className="border-b border-slate-200 bg-white/80 backdrop-blur">
        <div className="mx-auto flex max-w-7xl flex-wrap items-center justify-between gap-4 px-6 py-4">
          <div className="flex items-center gap-3">
            <img src="/favicon.svg" alt="" className="h-9 w-9" />
            <div>
              <h1 className="text-lg font-bold tracking-tight text-slate-900">Markdown → Word</h1>
              <p className="text-xs text-slate-500">Turn .md files into formatted, shareable .docx documents</p>
            </div>
          </div>
          <div className="flex items-center gap-4">
            <span className="hidden items-center gap-1.5 text-xs font-medium text-emerald-700 sm:flex">
              <ShieldIcon width={16} height={16} /> Converted in your browser, nothing uploaded
            </span>
            <div className="flex items-center gap-2">
              <span className="text-xs font-medium text-slate-500">Page</span>
              <div className="inline-flex rounded-lg bg-slate-100 p-0.5">
                {(["A4", "Letter"] as const).map((size) => (
                  <button
                    key={size}
                    type="button"
                    onClick={() => changePageSize(size)}
                    className={`rounded-md px-3 py-1 text-sm font-medium transition ${
                      pageSize === size ? "bg-white text-slate-900 shadow-sm" : "text-slate-500 hover:text-slate-800"
                    }`}
                  >
                    {size}
                  </button>
                ))}
              </div>
            </div>
          </div>
        </div>
      </header>

      <main className="mx-auto grid max-w-7xl gap-6 px-6 py-8 lg:grid-cols-[minmax(0,1fr)_340px]">
        <section className="space-y-6">
          <DropZone onFiles={addFiles} onPaste={() => setPasting(true)} compact={items.length > 0} />

          {items.length > 0 && (
            <div>
              <div className="mb-3 flex flex-wrap items-center justify-between gap-2">
                <h2 className="font-semibold text-slate-900">
                  Files <span className="font-normal text-slate-500">· {ready} of {items.length} ready</span>
                </h2>
                <div className="flex items-center gap-2">
                  <button type="button" onClick={requeueAll} disabled={working} className="btn-ghost">
                    <RefreshIcon width={16} height={16} /> Re-convert
                  </button>
                  <button
                    type="button"
                    onClick={() => setItems([])}
                    disabled={working}
                    className="btn-ghost hover:text-rose-600"
                  >
                    Clear
                  </button>
                  {ready > 1 && (
                    <button type="button" onClick={downloadZip} className="btn-secondary">
                      <ArchiveIcon width={16} height={16} /> Download all (.zip)
                    </button>
                  )}
                </div>
              </div>
              <ul className="space-y-3">
                {items.map((item) => (
                  <FileCard
                    key={item.id}
                    item={item}
                    onPreview={() => setPreviewId(item.id)}
                    onDownload={() => download(item)}
                    onRemove={() => setItems((list) => list.filter((i) => i.id !== item.id))}
                  />
                ))}
              </ul>
              {assets.current.size > 0 && (
                <p className="mt-3 text-xs text-slate-500">
                  {assets.current.size} image file{assets.current.size > 1 ? "s" : ""} available for embedding.
                </p>
              )}
            </div>
          )}

          {items.length === 0 && (
            <div className="grid gap-4 sm:grid-cols-3">
              {[
                ["Real Word structure", "Headings, numbered lists, clickable links and checkboxes, editable with Word's own styles."],
                ["Diagrams & images", "Mermaid is rendered locally in high resolution; local and web images are embedded."],
                ["Tables & code", "Header rows repeat across pages, columns keep their alignment, code stays monospaced."],
              ].map(([title, body]) => (
                <div key={title} className="rounded-xl border border-slate-200 bg-white p-4">
                  <p className="text-sm font-semibold text-slate-800">{title}</p>
                  <p className="mt-1 text-sm text-slate-500">{body}</p>
                </div>
              ))}
            </div>
          )}
        </section>

        <HistoryPanel
          entries={history}
          onDownload={async (e) => {
            const blob = await getHistoryBlob(e.id);
            if (blob) downloadBlob(blob, e.name);
          }}
          onDelete={async (e) => {
            await deleteHistory(e.id);
            await refreshHistory();
          }}
          onClear={async () => {
            if (!confirm("Delete all converted documents from history?")) return;
            await clearHistory();
            await refreshHistory();
          }}
        />
      </main>

      {preview && (
        <PreviewDialog
          item={preview}
          assets={assets.current}
          onClose={() => setPreviewId(null)}
          onDownload={() => download(preview)}
        />
      )}
      {pasting && (
        <PasteDialog
          onClose={() => setPasting(false)}
          onSubmit={(name, text) => {
            setPasting(false);
            addMarkdown([{ path: name, text }]);
          }}
        />
      )}
    </div>
  );
}
