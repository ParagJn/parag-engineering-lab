/**
 * Conversion history stored in IndexedDB (replaces the old docx-outputs/ folder).
 * Metadata and file bytes live in separate stores so listing stays cheap.
 * Every call degrades to a no-op if IndexedDB is unavailable (e.g. private mode).
 */

export interface HistoryEntry {
  id: string;
  name: string;
  source: string;
  size: number;
  createdAt: number;
}

const DB_NAME = "md-to-docx";
const META = "history";
const BLOBS = "files";
const MAX_ENTRIES = 50;

let dbPromise: Promise<IDBDatabase> | null = null;

function openDb(): Promise<IDBDatabase> {
  dbPromise ??= new Promise((resolve, reject) => {
    const req = indexedDB.open(DB_NAME, 1);
    req.onupgradeneeded = () => {
      req.result.createObjectStore(META, { keyPath: "id" });
      req.result.createObjectStore(BLOBS);
    };
    req.onsuccess = () => resolve(req.result);
    req.onerror = () => reject(req.error);
  });
  return dbPromise;
}

function done(tx: IDBTransaction): Promise<void> {
  return new Promise((resolve, reject) => {
    tx.oncomplete = () => resolve();
    tx.onerror = tx.onabort = () => reject(tx.error);
  });
}

function request<T>(req: IDBRequest<T>): Promise<T> {
  return new Promise((resolve, reject) => {
    req.onsuccess = () => resolve(req.result);
    req.onerror = () => reject(req.error);
  });
}

export async function listHistory(): Promise<HistoryEntry[]> {
  try {
    const db = await openDb();
    const all = await request(db.transaction(META).objectStore(META).getAll() as IDBRequest<HistoryEntry[]>);
    return all.sort((a, b) => b.createdAt - a.createdAt);
  } catch {
    return [];
  }
}

export async function saveHistory(entry: HistoryEntry, blob: Blob): Promise<void> {
  try {
    const db = await openDb();
    const tx = db.transaction([META, BLOBS], "readwrite");
    tx.objectStore(META).put(entry);
    tx.objectStore(BLOBS).put(blob, entry.id);
    await done(tx);
    const all = await listHistory();
    await Promise.all(all.slice(MAX_ENTRIES).map((e) => deleteHistory(e.id)));
  } catch {
    // history is a convenience; ignore storage failures
  }
}

export async function getHistoryBlob(id: string): Promise<Blob | null> {
  try {
    const db = await openDb();
    return (await request(db.transaction(BLOBS).objectStore(BLOBS).get(id))) ?? null;
  } catch {
    return null;
  }
}

export async function deleteHistory(id: string): Promise<void> {
  try {
    const db = await openDb();
    const tx = db.transaction([META, BLOBS], "readwrite");
    tx.objectStore(META).delete(id);
    tx.objectStore(BLOBS).delete(id);
    await done(tx);
  } catch {
    // ignore
  }
}

export async function clearHistory(): Promise<void> {
  try {
    const db = await openDb();
    const tx = db.transaction([META, BLOBS], "readwrite");
    tx.objectStore(META).clear();
    tx.objectStore(BLOBS).clear();
    await done(tx);
  } catch {
    // ignore
  }
}
