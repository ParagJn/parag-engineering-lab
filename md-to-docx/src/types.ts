export type ItemStatus = "queued" | "converting" | "done" | "error";

/** A markdown file in the current session. */
export interface Item {
  id: string;
  path: string;
  name: string;
  text: string;
  status: ItemStatus;
  /** Bumped whenever the item is re-queued, so stale conversions are discarded. */
  rev: number;
  outName: string;
  historyId: string;
  title?: string;
  blob?: Blob;
  error?: string;
  warnings: string[];
}
