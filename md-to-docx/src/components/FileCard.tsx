import { useState } from "react";
import { formatBytes } from "../lib/files";
import type { Item } from "../types";
import { AlertIcon, CheckIcon, ClockIcon, CloseIcon, DownloadIcon, EyeIcon, FileIcon, Spinner } from "./icons";

interface Props {
  item: Item;
  onPreview: () => void;
  onDownload: () => void;
  onRemove: () => void;
}

function StatusChip({ item }: { item: Item }) {
  switch (item.status) {
    case "queued":
      return (
        <span className="chip bg-slate-100 text-slate-600">
          <ClockIcon width={14} height={14} /> Queued
        </span>
      );
    case "converting":
      return (
        <span className="chip bg-indigo-50 text-indigo-700">
          <Spinner className="h-3.5 w-3.5" /> Converting
        </span>
      );
    case "done":
      return (
        <span className="chip bg-emerald-50 text-emerald-700">
          <CheckIcon width={14} height={14} /> Ready
        </span>
      );
    case "error":
      return (
        <span className="chip bg-rose-50 text-rose-700">
          <AlertIcon width={14} height={14} /> Failed
        </span>
      );
  }
}

export function FileCard({ item, onPreview, onDownload, onRemove }: Props) {
  const [showWarnings, setShowWarnings] = useState(false);
  const warnings = item.warnings.length;

  return (
    <li className="rounded-xl border border-slate-200 bg-white p-4 shadow-sm transition hover:shadow">
      <div className="flex items-start gap-3">
        <div className="mt-0.5 flex h-10 w-10 shrink-0 items-center justify-center rounded-lg bg-blue-50 text-blue-600">
          <FileIcon width={20} height={20} />
        </div>
        <div className="min-w-0 flex-1">
          <div className="flex flex-wrap items-center gap-2">
            <p className="truncate font-medium text-slate-900" title={item.path}>
              {item.title || item.name}
            </p>
            <StatusChip item={item} />
            {warnings > 0 && (
              <button
                type="button"
                onClick={() => setShowWarnings((v) => !v)}
                className="chip bg-amber-50 text-amber-700 hover:bg-amber-100"
              >
                <AlertIcon width={14} height={14} /> {warnings} warning{warnings > 1 ? "s" : ""}
              </button>
            )}
          </div>
          <p className="mt-0.5 truncate text-xs text-slate-500">
            {item.path}
            {item.blob && (
              <>
                {" "}
                → <span className="font-medium text-slate-600">{item.outName}</span> · {formatBytes(item.blob.size)}
              </>
            )}
          </p>
          {item.status === "error" && <p className="mt-2 text-sm text-rose-700">{item.error}</p>}
          {showWarnings && (
            <ul className="mt-3 space-y-1 rounded-lg bg-amber-50 p-3 text-xs text-amber-800">
              {item.warnings.map((w) => (
                <li key={w} className="break-all">
                  • {w}
                </li>
              ))}
            </ul>
          )}
        </div>
        <div className="flex shrink-0 items-center gap-1">
          <button type="button" onClick={onPreview} className="icon-btn" title="Preview">
            <EyeIcon />
          </button>
          <button
            type="button"
            onClick={onDownload}
            disabled={item.status !== "done"}
            className="btn-primary px-3 py-1.5 text-sm"
            title="Download .docx"
          >
            <DownloadIcon width={16} height={16} /> .docx
          </button>
          <button type="button" onClick={onRemove} className="icon-btn hover:text-rose-600" title="Remove">
            <CloseIcon />
          </button>
        </div>
      </div>
    </li>
  );
}
