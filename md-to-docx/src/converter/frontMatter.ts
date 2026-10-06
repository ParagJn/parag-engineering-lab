import { parse } from "yaml";
import type { DocumentMeta } from "./types";

const FRONT_MATTER = /^﻿?---[ \t]*\r?\n([\s\S]*?)\r?\n(?:---|\.\.\.)[ \t]*(?:\r?\n|$)/;

/**
 * Split a leading YAML front-matter block from the markdown body.
 * If the block isn't a YAML mapping it is left in place as ordinary markdown
 * (a document may legitimately start with a horizontal rule).
 */
export function splitFrontMatter(markdown: string): { meta: DocumentMeta; body: string } {
  const match = FRONT_MATTER.exec(markdown);
  if (match) {
    try {
      const data: unknown = parse(match[1]);
      if (data && typeof data === "object" && !Array.isArray(data)) {
        return { meta: normaliseMeta(data as Record<string, unknown>), body: markdown.slice(match[0].length) };
      }
    } catch {
      // not YAML – fall through and treat it as markdown
    }
  }
  return { meta: {}, body: markdown };
}

function normaliseMeta(data: Record<string, unknown>): DocumentMeta {
  const meta: DocumentMeta = { ...data };
  const text = (v: unknown) => (v == null ? undefined : Array.isArray(v) ? v.join(", ") : String(v));
  meta.title = text(data.title);
  meta.author = text(data.author ?? data.authors);
  meta.subject = text(data.subject ?? data.subtitle);
  meta.description = text(data.description ?? data.summary);
  meta.keywords = text(data.keywords ?? data.tags);
  return meta;
}
