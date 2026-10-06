/** Helpers for picking up files from drag-and-drop (including whole folders) and for downloads. */

export interface PickedFile {
  path: string;
  file: File;
}

export const isMarkdown = (path: string) => /\.(md|markdown|mdown|mkd)$/i.test(path);

export function fromFileList(list: FileList | File[]): PickedFile[] {
  return [...list].map((file) => ({ path: file.webkitRelativePath || file.name, file }));
}

/** Read dropped items, walking into folders when the browser exposes them. */
export async function fromDataTransfer(dt: DataTransfer): Promise<PickedFile[]> {
  const entries = [...dt.items].map((item) => item.webkitGetAsEntry?.()).filter((e): e is FileSystemEntry => !!e);
  if (!entries.length) return fromFileList(dt.files);
  const nested = await Promise.all(entries.map((entry) => walk(entry, "")));
  return nested.flat();
}

async function walk(entry: FileSystemEntry, prefix: string): Promise<PickedFile[]> {
  const path = prefix ? `${prefix}/${entry.name}` : entry.name;
  if (entry.isFile) {
    const file = await new Promise<File>((resolve, reject) => (entry as FileSystemFileEntry).file(resolve, reject));
    return [{ path, file }];
  }
  if (entry.name.startsWith(".") || entry.name === "node_modules") return [];
  const reader = (entry as FileSystemDirectoryEntry).createReader();
  const children: FileSystemEntry[] = [];
  // readEntries returns results in batches until it yields an empty array.
  for (;;) {
    const batch = await new Promise<FileSystemEntry[]>((resolve, reject) => reader.readEntries(resolve, reject));
    if (!batch.length) break;
    children.push(...batch);
  }
  const nested = await Promise.all(children.map((child) => walk(child, path)));
  return nested.flat();
}

export function downloadBlob(blob: Blob, name: string) {
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = name;
  a.click();
  setTimeout(() => URL.revokeObjectURL(url), 10_000);
}

export function dateStamp(date = new Date()): string {
  const dd = String(date.getDate()).padStart(2, "0");
  const mm = String(date.getMonth() + 1).padStart(2, "0");
  return `${dd}${mm}${date.getFullYear()}`;
}

export function formatBytes(bytes: number): string {
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
  return `${(bytes / 1024 / 1024).toFixed(1)} MB`;
}
