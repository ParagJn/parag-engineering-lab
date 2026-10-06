import MarkdownIt from "markdown-it";
import { useEffect, useMemo } from "react";
import { splitFrontMatter } from "../converter/frontMatter";
import { findAsset } from "../lib/paths";
import type { Item } from "../types";
import { DownloadIcon } from "./icons";
import { Modal } from "./Modal";

interface Props {
  item: Item;
  assets: Map<string, File>;
  onClose: () => void;
  onDownload: () => void;
}

/** Raw HTML is disabled here, so previewing untrusted markdown can't inject markup. */
const previewMd = new MarkdownIt({ linkify: true, typographer: true });

export function PreviewDialog({ item, assets, onClose, onDownload }: Props) {
  const { html, meta, urls } = useMemo(() => {
    const { meta, body } = splitFrontMatter(item.text);
    const urls: string[] = [];
    const env = {};
    const tokens = previewMd.parse(body, env);
    // Point local image references at the uploaded files.
    for (const t of tokens) {
      for (const c of t.children ?? []) {
        const src = c.type === "image" ? String(c.attrGet("src") ?? "") : "";
        if (!src || /^(https?:|data:)/i.test(src)) continue;
        const file = findAsset(assets, src, item.path);
        if (file) {
          const url = URL.createObjectURL(file);
          urls.push(url);
          c.attrSet("src", url);
        }
      }
    }
    return { html: previewMd.renderer.render(tokens, previewMd.options, env), meta, urls };
  }, [item.text, item.path, assets]);

  useEffect(() => () => urls.forEach((u) => URL.revokeObjectURL(u)), [urls]);

  const metaRows = Object.entries(meta).filter(([, v]) => v != null && typeof v !== "object");

  return (
    <Modal
      wide
      title={item.title || item.name}
      subtitle={item.path}
      onClose={onClose}
      footer={
        <>
          <button type="button" onClick={onClose} className="btn-secondary">
            Close
          </button>
          <button type="button" onClick={onDownload} disabled={item.status !== "done"} className="btn-primary">
            <DownloadIcon /> Download .docx
          </button>
        </>
      }
    >
      {metaRows.length > 0 && (
        <dl className="grid grid-cols-[max-content_1fr] gap-x-4 gap-y-1 border-b border-slate-100 bg-slate-50 px-8 py-4 text-sm">
          {metaRows.map(([k, v]) => (
            <div key={k} className="contents">
              <dt className="font-medium text-slate-500 capitalize">{k}</dt>
              <dd className="text-slate-800">{String(v)}</dd>
            </div>
          ))}
        </dl>
      )}
      <article
        className="prose prose-slate max-w-none px-8 py-6 prose-headings:text-slate-900 prose-a:text-blue-600 prose-pre:bg-slate-50 prose-pre:text-slate-800 prose-img:mx-auto"
        dangerouslySetInnerHTML={{ __html: html }}
      />
    </Modal>
  );
}
