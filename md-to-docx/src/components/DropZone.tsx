import { useRef, useState, type DragEvent } from "react";
import { fromDataTransfer, fromFileList, type PickedFile } from "../lib/files";
import { ClipboardIcon, FileIcon, FolderIcon, UploadIcon } from "./icons";

interface Props {
  onFiles: (files: PickedFile[]) => void;
  onPaste: () => void;
  compact?: boolean;
}

const ACCEPT = ".md,.markdown,.png,.jpg,.jpeg,.gif,.bmp,.svg,.webp";

export function DropZone({ onFiles, onPaste, compact }: Props) {
  const [dragging, setDragging] = useState(false);
  const fileInput = useRef<HTMLInputElement>(null);
  const folderInput = useRef<HTMLInputElement>(null);

  const onDrop = async (e: DragEvent) => {
    e.preventDefault();
    setDragging(false);
    onFiles(await fromDataTransfer(e.dataTransfer));
  };

  const pick = (input: HTMLInputElement | null) => {
    if (input?.files?.length) onFiles(fromFileList(input.files));
    if (input) input.value = "";
  };

  return (
    <div
      onDragOver={(e) => {
        e.preventDefault();
        setDragging(true);
      }}
      onDragLeave={(e) => {
        if (!e.currentTarget.contains(e.relatedTarget as Node)) setDragging(false);
      }}
      onDrop={onDrop}
      className={`rounded-2xl border-2 border-dashed text-center transition-colors ${
        compact ? "px-6 py-6" : "px-6 py-14"
      } ${dragging ? "border-indigo-500 bg-indigo-50" : "border-slate-300 bg-white hover:border-indigo-300"}`}
    >
      <div
        className={`mx-auto flex items-center justify-center rounded-full bg-indigo-50 text-indigo-600 ${
          compact ? "mb-3 h-10 w-10" : "mb-4 h-14 w-14"
        }`}
      >
        <UploadIcon width={compact ? 20 : 26} height={compact ? 20 : 26} />
      </div>
      <p className="font-semibold text-slate-800">{dragging ? "Drop to convert" : "Drag & drop Markdown files or a folder"}</p>
      {!compact && (
        <p className="mt-1 text-sm text-slate-500">
          Include the images your files reference (or drop the whole folder) so they get embedded.
        </p>
      )}
      <div className="mt-5 flex flex-wrap items-center justify-center gap-2">
        <button type="button" onClick={() => fileInput.current?.click()} className="btn-primary">
          <FileIcon /> Choose files
        </button>
        <button type="button" onClick={() => folderInput.current?.click()} className="btn-secondary">
          <FolderIcon /> Choose folder
        </button>
        <button type="button" onClick={onPaste} className="btn-secondary">
          <ClipboardIcon /> Paste Markdown
        </button>
      </div>
      <input ref={fileInput} type="file" multiple accept={ACCEPT} hidden onChange={(e) => pick(e.currentTarget)} />
      <input
        ref={folderInput}
        type="file"
        hidden
        onChange={(e) => pick(e.currentTarget)}
        {...({ webkitdirectory: "", directory: "" } as Record<string, string>)}
      />
    </div>
  );
}
