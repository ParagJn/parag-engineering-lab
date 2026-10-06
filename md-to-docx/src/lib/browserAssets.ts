/**
 * Browser implementation of the converter's AssetResolver: loads images from
 * uploaded files, data URIs or the web, and renders Mermaid locally (nothing
 * is sent to a third-party rendering service).
 */
import type { AssetResolver, ImageType, ResolvedImage } from "../converter/types";
import { findAsset } from "./paths";

/** Resolution multiplier for rasterised SVG/Mermaid so they stay crisp in print. */
const RASTER_SCALE = 3;
const MAX_CANVAS = 8192;

export function createBrowserAssets(files: Map<string, File>, markdownPath: string): AssetResolver {
  return {
    async image(src) {
      const bytes = await loadBytes(src, files, markdownPath);
      return bytes ? toDocxImage(bytes) : null;
    },
    mermaid: renderMermaid,
  };
}

async function loadBytes(src: string, files: Map<string, File>, markdownPath: string): Promise<Uint8Array | null> {
  if (src.startsWith("data:")) {
    const res = await fetch(src);
    return new Uint8Array(await res.arrayBuffer());
  }
  if (/^https?:\/\//i.test(src)) {
    // Fails for hosts that don't allow cross-origin requests; the converter shows a placeholder.
    const res = await fetch(src);
    return res.ok ? new Uint8Array(await res.arrayBuffer()) : null;
  }
  const file = findAsset(files, src, markdownPath);
  return file ? new Uint8Array(await file.arrayBuffer()) : null;
}

function sniff(bytes: Uint8Array): ImageType | "svg" | null {
  const b = bytes;
  if (b[0] === 0x89 && b[1] === 0x50 && b[2] === 0x4e && b[3] === 0x47) return "png";
  if (b[0] === 0xff && b[1] === 0xd8 && b[2] === 0xff) return "jpg";
  if (b[0] === 0x47 && b[1] === 0x49 && b[2] === 0x46) return "gif";
  if (b[0] === 0x42 && b[1] === 0x4d) return "bmp";
  const head = new TextDecoder().decode(b.slice(0, 1024)).toLowerCase();
  if (head.includes("<svg")) return "svg";
  return null;
}

/** Turn arbitrary image bytes into something Word can embed (PNG/JPG/GIF/BMP). */
async function toDocxImage(bytes: Uint8Array): Promise<ResolvedImage | null> {
  const kind = sniff(bytes);
  if (kind === "svg") return svgToPng(new TextDecoder().decode(bytes));
  const blob = new Blob([bytes as BlobPart]);
  const bitmap = await createImageBitmap(blob).catch(() => null);
  if (!bitmap) return null;
  try {
    if (kind) return { type: kind, data: bytes, width: bitmap.width, height: bitmap.height };
    // WebP, AVIF, … – Word can't embed these, so re-encode as PNG.
    const data = await canvasToPng(bitmap, bitmap.width, bitmap.height, 1);
    return { type: "png", data, width: bitmap.width, height: bitmap.height };
  } finally {
    bitmap.close();
  }
}

/** Give the SVG explicit pixel dimensions (Mermaid emits width="100%"). */
function normalizeSvg(svgText: string): { svg: string; width: number; height: number } {
  const doc = new DOMParser().parseFromString(svgText, "image/svg+xml");
  const root = doc.documentElement;
  if (root.nodeName.toLowerCase() !== "svg") throw new Error("Not an SVG document");
  const viewBox = (root.getAttribute("viewBox") ?? "").split(/[\s,]+/).map(Number);
  const px = (attr: string) => {
    const v = root.getAttribute(attr) ?? "";
    return /%$/.test(v) ? NaN : parseFloat(v);
  };
  let width = px("width");
  let height = px("height");
  const [vbW, vbH] = viewBox.length === 4 ? [viewBox[2], viewBox[3]] : [NaN, NaN];
  if (!(width > 0)) width = vbW > 0 ? vbW : height > 0 && vbH > 0 ? (height * vbW) / vbH : 300;
  if (!(height > 0)) height = vbH > 0 && vbW > 0 ? (width * vbH) / vbW : 150;
  root.setAttribute("width", String(width));
  root.setAttribute("height", String(height));
  root.removeAttribute("style");
  if (!root.getAttribute("xmlns")) root.setAttribute("xmlns", "http://www.w3.org/2000/svg");
  return { svg: new XMLSerializer().serializeToString(root), width, height };
}

async function svgToPng(svgText: string): Promise<ResolvedImage> {
  const { svg, width, height } = normalizeSvg(svgText);
  const url = URL.createObjectURL(new Blob([svg], { type: "image/svg+xml" }));
  try {
    const img = new Image();
    img.src = url;
    await img.decode();
    const data = await canvasToPng(img, width, height, RASTER_SCALE);
    return { type: "png", data, width, height };
  } finally {
    URL.revokeObjectURL(url);
  }
}

async function canvasToPng(source: CanvasImageSource, width: number, height: number, scale: number): Promise<Uint8Array> {
  const s = Math.min(scale, MAX_CANVAS / width, MAX_CANVAS / height);
  const canvas = document.createElement("canvas");
  canvas.width = Math.max(1, Math.round(width * s));
  canvas.height = Math.max(1, Math.round(height * s));
  canvas.getContext("2d")!.drawImage(source, 0, 0, canvas.width, canvas.height);
  const blob = await new Promise<Blob>((resolve, reject) =>
    canvas.toBlob((b) => (b ? resolve(b) : reject(new Error("PNG encoding failed"))), "image/png"),
  );
  return new Uint8Array(await blob.arrayBuffer());
}

// ---------------------------------------------------------------------------
// Mermaid (loaded lazily – it is large)
// ---------------------------------------------------------------------------

type Mermaid = (typeof import("mermaid"))["default"];
let mermaidReady: Promise<Mermaid> | null = null;
let diagramCounter = 0;

function loadMermaid(): Promise<Mermaid> {
  mermaidReady ??= import("mermaid").then(({ default: mermaid }) => {
    mermaid.initialize({
      startOnLoad: false,
      securityLevel: "strict",
      theme: "default",
      fontFamily: "Arial, Helvetica, sans-serif",
      // Plain SVG text instead of HTML labels, so the diagram can be rasterised.
      htmlLabels: false,
      flowchart: { htmlLabels: false },
    } as Parameters<Mermaid["initialize"]>[0]);
    return mermaid;
  });
  return mermaidReady;
}

async function renderMermaid(code: string): Promise<ResolvedImage | null> {
  const mermaid = await loadMermaid();
  const id = `mmd-${++diagramCounter}`;
  try {
    const { svg } = await mermaid.render(id, code);
    return await svgToPng(svg);
  } catch (err) {
    console.warn("Mermaid render failed", err);
    return null;
  } finally {
    // Mermaid leaves a temporary container behind when rendering fails.
    document.getElementById(`d${id}`)?.remove();
    document.getElementById(id)?.remove();
  }
}
