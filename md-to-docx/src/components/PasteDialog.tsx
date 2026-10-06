import { useState } from "react";
import { Modal } from "./Modal";

interface Props {
  onClose: () => void;
  onSubmit: (name: string, text: string) => void;
}

export function PasteDialog({ onClose, onSubmit }: Props) {
  const [name, setName] = useState("document");
  const [text, setText] = useState("");

  const submit = () => {
    if (!text.trim()) return;
    const base = name.trim().replace(/\.(md|markdown)$/i, "").replace(/[\\/:*?"<>|]+/g, "-") || "document";
    onSubmit(`${base}.md`, text);
  };

  return (
    <Modal
      title="Paste Markdown"
      subtitle="Handy for chat responses, notes or snippets"
      onClose={onClose}
      footer={
        <>
          <button type="button" onClick={onClose} className="btn-secondary">
            Cancel
          </button>
          <button type="button" onClick={submit} disabled={!text.trim()} className="btn-primary">
            Convert
          </button>
        </>
      }
    >
      <div className="space-y-4 px-6 py-5">
        <label className="block">
          <span className="text-sm font-medium text-slate-700">File name</span>
          <div className="mt-1 flex rounded-lg border border-slate-300 focus-within:border-indigo-500 focus-within:ring-2 focus-within:ring-indigo-100">
            <input
              value={name}
              onChange={(e) => setName(e.target.value)}
              className="w-full rounded-l-lg px-3 py-2 text-sm outline-none"
            />
            <span className="flex items-center rounded-r-lg bg-slate-50 px-3 text-sm text-slate-500">.md</span>
          </div>
        </label>
        <label className="block">
          <span className="text-sm font-medium text-slate-700">Markdown</span>
          <textarea
            autoFocus
            value={text}
            onChange={(e) => setText(e.target.value)}
            onKeyDown={(e) => (e.metaKey || e.ctrlKey) && e.key === "Enter" && submit()}
            rows={14}
            placeholder={"# Title\n\nPaste or type Markdown here…"}
            className="mt-1 w-full rounded-lg border border-slate-300 px-3 py-2 font-mono text-sm outline-none focus:border-indigo-500 focus:ring-2 focus:ring-indigo-100"
          />
          <span className="text-xs text-slate-400">⌘/Ctrl + Enter to convert</span>
        </label>
      </div>
    </Modal>
  );
}
