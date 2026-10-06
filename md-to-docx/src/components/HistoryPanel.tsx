import { formatBytes } from "../lib/files";
import type { HistoryEntry } from "../lib/history";
import { DownloadIcon, FileIcon, TrashIcon } from "./icons";

interface Props {
  entries: HistoryEntry[];
  onDownload: (entry: HistoryEntry) => void;
  onDelete: (entry: HistoryEntry) => void;
  onClear: () => void;
}

const when = (ts: number) =>
  new Date(ts).toLocaleString(undefined, { day: "2-digit", month: "short", hour: "2-digit", minute: "2-digit" });

export function HistoryPanel({ entries, onDownload, onDelete, onClear }: Props) {
  return (
    <aside className="rounded-2xl border border-slate-200 bg-white shadow-sm lg:sticky lg:top-6">
      <div className="flex items-center justify-between border-b border-slate-100 px-5 py-4">
        <div>
          <h2 className="font-semibold text-slate-900">History</h2>
          <p className="text-xs text-slate-500">Stored in this browser · last 50</p>
        </div>
        {entries.length > 0 && (
          <button type="button" onClick={onClear} className="text-xs font-medium text-slate-500 hover:text-rose-600">
            Clear all
          </button>
        )}
      </div>
      {entries.length === 0 ? (
        <p className="px-5 py-10 text-center text-sm text-slate-400">No conversions yet.</p>
      ) : (
        <ul className="max-h-[70vh] divide-y divide-slate-100 overflow-y-auto">
          {entries.map((e) => (
            <li key={e.id} className="group flex items-center gap-3 px-5 py-3 hover:bg-slate-50">
              <FileIcon className="shrink-0 text-slate-400" />
              <div className="min-w-0 flex-1">
                <p className="truncate text-sm font-medium text-slate-800" title={e.name}>
                  {e.name}
                </p>
                <p className="text-xs text-slate-500">
                  {when(e.createdAt)} · {formatBytes(e.size)}
                </p>
              </div>
              <button type="button" onClick={() => onDownload(e)} className="icon-btn" title="Download">
                <DownloadIcon width={16} height={16} />
              </button>
              <button
                type="button"
                onClick={() => onDelete(e)}
                className="icon-btn opacity-0 group-hover:opacity-100 hover:text-rose-600 focus:opacity-100"
                title="Delete"
              >
                <TrashIcon width={16} height={16} />
              </button>
            </li>
          ))}
        </ul>
      )}
    </aside>
  );
}
