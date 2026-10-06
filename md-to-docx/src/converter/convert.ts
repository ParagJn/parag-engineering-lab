/**
 * Markdown → Word converter.
 *
 * markdown-it produces a flat token stream; we fold it into a tree so every
 * block (code, tables, quotes, nested lists) renders correctly wherever it is
 * nested. Images and Mermaid diagrams are resolved up-front so the render
 * pass itself is synchronous.
 */
import {
  AlignmentType,
  Bookmark,
  BorderStyle,
  CheckBox,
  Document,
  ExternalHyperlink,
  HeadingLevel,
  ImageRun,
  InternalHyperlink,
  Paragraph,
  ShadingType,
  Tab,
  Table,
  TableCell,
  TableRow,
  TextRun,
  WidthType,
  type IRunOptions,
  type ParagraphChild,
} from "docx";
import MarkdownIt from "markdown-it";
import type { Token } from "markdown-it";
import { splitFrontMatter } from "./frontMatter";
import {
  BULLET_REF,
  COLORS,
  LIST_HANGING,
  LIST_INDENT,
  QUOTE_INDENT,
  STYLE,
  numbering,
  orderedRef,
  styles,
} from "./styles";
import type { AssetResolver, ConvertOptions, DocumentMeta, ResolvedImage } from "./types";

export interface ConvertResult {
  document: Document;
  meta: DocumentMeta;
  warnings: string[];
}

type Block = Paragraph | Table;

interface Node {
  token: Token;
  children: Node[];
}

interface ListMarker {
  numbering?: { reference: string; level: number; instance?: number };
  /** Task-list state; undefined for a regular bullet/number item. */
  task?: boolean;
  used: boolean;
}

interface Ctx {
  /** -1 outside of lists. */
  listLevel: number;
  quoteDepth: number;
  /** Marker waiting to be attached to the first paragraph of a list item. */
  marker?: ListMarker;
  maxImageWidth: number;
}

interface HtmlImage {
  src: string;
  alt: string;
  width?: number;
}

const PAGE = {
  A4: { width: 11906, height: 16838 },
  Letter: { width: 12240, height: 15840 },
};
const MARGIN = 1440;
const TWIPS_PER_PX = 15;

const HEADINGS = [
  HeadingLevel.HEADING_1,
  HeadingLevel.HEADING_2,
  HeadingLevel.HEADING_3,
  HeadingLevel.HEADING_4,
  HeadingLevel.HEADING_5,
  HeadingLevel.HEADING_6,
];

const md = new MarkdownIt("default", { html: true, linkify: true, typographer: true });

export async function convertMarkdown(
  markdown: string,
  assets: AssetResolver,
  options: ConvertOptions,
): Promise<ConvertResult> {
  const { meta, body } = splitFrontMatter(markdown);
  const tokens = md.parse(body, {});
  const refs = collectReferences(tokens);
  const warnings = new Set<string>();

  const images = new Map<string, ResolvedImage | null>();
  await Promise.all(
    [...refs.images].map(async (src) => {
      const img = await assets.image(src).catch(() => null);
      if (!img) warnings.add(`Image could not be loaded: ${src}`);
      images.set(src, img);
    }),
  );
  // Mermaid keeps global render state, so diagrams are rendered one at a time.
  const diagrams = new Map<string, ResolvedImage | null>();
  for (const code of refs.diagrams) {
    diagrams.set(code, await assets.mermaid(code).catch(() => null));
  }

  const page = PAGE[options.pageSize];
  const contentWidth = (page.width - 2 * MARGIN) / TWIPS_PER_PX;
  const renderer = new Renderer(images, diagrams, buildAnchors(refs.headings), warnings);
  const children = renderer.blocks(buildTree(tokens), { listLevel: -1, quoteDepth: 0, maxImageWidth: contentWidth });

  const title = meta.title ?? (refs.headings[0] ? plainText(refs.headings[0]) : undefined);
  const document = new Document({
    title,
    creator: meta.author ?? "MD to DOCX Converter",
    subject: meta.subject,
    description: meta.description,
    keywords: meta.keywords,
    styles,
    numbering: numbering(renderer.orderedStarts),
    sections: [
      {
        properties: { page: { size: page, margin: { top: MARGIN, right: MARGIN, bottom: MARGIN, left: MARGIN } } },
        children: children.length ? children : [new Paragraph({})],
      },
    ],
  });

  return { document, meta: { ...meta, title }, warnings: [...warnings] };
}

// ---------------------------------------------------------------------------
// Pre-pass: everything that has to be fetched or looked up before rendering
// ---------------------------------------------------------------------------

function collectReferences(tokens: Token[]) {
  const images = new Set<string>();
  const diagrams = new Set<string>();
  const headings: Token[] = [];

  tokens.forEach((t, i) => {
    if (t.type === "fence" && isMermaid(t.info)) diagrams.add(t.content);
    else if (t.type === "html_block") htmlImages(t.content).forEach((img) => images.add(img.src));
    else if (t.type === "heading_open" && tokens[i + 1]?.type === "inline") headings.push(tokens[i + 1]);
    else if (t.type === "inline") {
      for (const c of t.children ?? []) {
        if (c.type === "image") images.add(attr(c, "src"));
        else if (c.type === "html_inline") htmlImages(c.content).forEach((img) => images.add(img.src));
      }
    }
  });
  images.delete("");
  return { images, diagrams, headings };
}

function buildTree(tokens: Token[]): Node[] {
  const root: Node = { token: tokens[0], children: [] };
  const stack = [root];
  for (const token of tokens) {
    if (token.nesting === -1) {
      if (stack.length > 1) stack.pop();
      continue;
    }
    const node: Node = { token, children: [] };
    stack[stack.length - 1].children.push(node);
    if (token.nesting === 1) stack.push(node);
  }
  return root.children;
}

/** GitHub-style heading anchors mapped to Word bookmark names. */
function buildAnchors(headings: Token[]) {
  const bookmarks = new Map<Token, string>();
  const anchors = new Map<string, string>();
  const seen = new Map<string, number>();
  headings.forEach((inline, i) => {
    const base = githubSlug(plainText(inline));
    const count = seen.get(base) ?? 0;
    seen.set(base, count + 1);
    const slug = count ? `${base}-${count}` : base;
    // Leading underscore keeps it out of Word's visible bookmark list; Word caps names at 40 chars.
    const name = `_h${i}_${slug.replace(/[^A-Za-z0-9_]/g, "_")}`.slice(0, 40);
    bookmarks.set(inline, name);
    anchors.set(slug, name);
  });
  return { bookmarks, anchors };
}

function githubSlug(text: string): string {
  return text
    .trim()
    .toLowerCase()
    .replace(/[^\p{L}\p{N}\p{M}\s_-]/gu, "")
    .replace(/\s/g, "-");
}

function plainText(inline: Token): string {
  return (inline.children ?? [])
    .filter((c) => c.type === "text" || c.type === "code_inline")
    .map((c) => c.content)
    .join("");
}

function isMermaid(info: string): boolean {
  return info.trim().split(/\s+/)[0]?.toLowerCase() === "mermaid";
}

const IMG_TAG = /<img\b[^>]*>/gi;
const HTML_ATTR = /\b(src|alt|width)\s*=\s*(?:"([^"]*)"|'([^']*)'|([^\s>]+))/gi;

function htmlImages(html: string): HtmlImage[] {
  return [...html.matchAll(IMG_TAG)].flatMap(([tag]) => {
    const attrs: Record<string, string> = {};
    for (const m of tag.matchAll(HTML_ATTR)) attrs[m[1].toLowerCase()] = m[2] ?? m[3] ?? m[4] ?? "";
    if (!attrs.src) return [];
    const width = parseInt(attrs.width ?? "", 10);
    return [{ src: attrs.src, alt: attrs.alt ?? "", width: attrs.width?.endsWith("%") || !width ? undefined : width }];
  });
}

const BR_TAG = /^<br\s*\/?>$/i;
const HTML_COMMENT = /^<!--[\s\S]*-->$/;
const TASK_PREFIX = /^\[([ xX])\]\s+/;

function alignment(style: string | null | undefined) {
  const m = /text-align:\s*(left|center|right)/.exec(style ?? "");
  if (!m) return undefined;
  return m[1] === "center" ? AlignmentType.CENTER : m[1] === "right" ? AlignmentType.RIGHT : AlignmentType.LEFT;
}

// ---------------------------------------------------------------------------
// Render pass
// ---------------------------------------------------------------------------

class Renderer {
  readonly orderedStarts = new Set<number>();
  private nextListInstance = 1;
  private readonly bookmarks: Map<Token, string>;
  private readonly anchors: Map<string, string>;

  constructor(
    private readonly images: Map<string, ResolvedImage | null>,
    private readonly diagrams: Map<string, ResolvedImage | null>,
    anchors: { bookmarks: Map<Token, string>; anchors: Map<string, string> },
    private readonly warnings: Set<string>,
  ) {
    this.bookmarks = anchors.bookmarks;
    this.anchors = anchors.anchors;
  }

  blocks(nodes: Node[], ctx: Ctx): Block[] {
    return nodes.flatMap((node) => this.block(node, ctx));
  }

  private block(node: Node, ctx: Ctx): Block[] {
    const t = node.token;
    switch (t.type) {
      case "heading_open":
        return this.heading(node, ctx);
      case "paragraph_open":
        return this.paragraph(node.children[0]?.token, ctx);
      case "bullet_list_open":
      case "ordered_list_open":
        return this.list(node, ctx);
      case "fence":
      case "code_block":
        return this.code(t, ctx);
      case "blockquote_open":
        return this.blocks(node.children, { ...ctx, quoteDepth: ctx.quoteDepth + 1 });
      case "table_open":
        return this.table(node, ctx);
      case "hr":
        return [
          new Paragraph({
            spacing: { before: 120, after: 120 },
            border: { bottom: { style: BorderStyle.SINGLE, size: 6, color: COLORS.rule, space: 1 } },
          }),
        ];
      case "html_block":
        return this.htmlBlock(t, ctx);
      default:
        return [];
    }
  }

  // ---- blocks -------------------------------------------------------------

  private heading(node: Node, ctx: Ctx): Block[] {
    const level = Number(node.token.tag.slice(1));
    const inline = node.children[0]?.token;
    const runs = inline ? this.inline(inline.children ?? [], ctx) : [];
    const bookmark = inline && this.bookmarks.get(inline);
    return [
      new Paragraph({
        heading: HEADINGS[level - 1],
        children: bookmark ? [new Bookmark({ id: bookmark, children: runs })] : runs,
      }),
    ];
  }

  private paragraph(inline: Token | undefined, ctx: Ctx): Block[] {
    const children = inline?.children ?? [];
    const marker = ctx.marker && !ctx.marker.used ? ctx.marker : undefined;
    if (marker) marker.used = true;
    else if (isFigure(children)) return this.figure(children, ctx);
    return [this.para(this.inline(children, ctx), ctx, marker)];
  }

  private para(runs: ParagraphChild[], ctx: Ctx, marker?: ListMarker): Paragraph {
    const style = ctx.quoteDepth ? STYLE.quote : undefined;
    const quoteIndent = QUOTE_INDENT * ctx.quoteDepth;
    if (marker) {
      const indent = { left: LIST_INDENT * (ctx.listLevel + 1) + quoteIndent, hanging: LIST_HANGING };
      if (marker.task !== undefined) {
        return new Paragraph({
          style,
          indent,
          children: [new CheckBox({ checked: marker.task }), new TextRun({ children: [new Tab()] }), ...runs],
        });
      }
      return new Paragraph({ style, numbering: marker.numbering, indent: quoteIndent ? indent : undefined, children: runs });
    }
    return new Paragraph({ style, indent: indentOf(ctx), children: runs });
  }

  private list(node: Node, ctx: Ctx): Block[] {
    const ordered = node.token.type === "ordered_list_open";
    const level = Math.min(ctx.listLevel + 1, 8);
    let numbering: ListMarker["numbering"];
    if (ordered) {
      const start = Number(attr(node.token, "start") || 1) || 1;
      this.orderedStarts.add(start);
      // A fresh instance per list restarts numbering at `start`.
      numbering = { reference: orderedRef(start), level, instance: this.nextListInstance++ };
    } else {
      numbering = { reference: BULLET_REF, level };
    }

    const out: Block[] = [];
    for (const item of node.children) {
      const task = takeTaskState(item);
      const marker: ListMarker = { numbering: task === undefined ? numbering : undefined, task, used: false };
      const itemCtx: Ctx = { ...ctx, listLevel: level, marker };
      for (const child of item.children) {
        if (!marker.used && child.token.type !== "paragraph_open") {
          // Item starts with e.g. a code block: give it an empty bullet line first.
          out.push(this.para([], itemCtx, marker));
          marker.used = true;
        }
        out.push(...this.block(child, itemCtx));
      }
      if (!marker.used) out.push(this.para([], itemCtx, marker));
    }
    return out;
  }

  private code(token: Token, ctx: Ctx): Block[] {
    const lang = token.info.trim().split(/\s+/)[0] ?? "";
    if (token.type === "fence" && isMermaid(lang)) {
      const img = this.diagrams.get(token.content);
      if (img) return [new Paragraph({ style: STYLE.figure, indent: indentOf(ctx), children: [this.imageRun(img, "Diagram", ctx)] })];
      this.warnings.add("A Mermaid diagram could not be rendered; its source was included as a code block.");
    }
    const lines = token.content.replace(/\n$/, "").replace(/\t/g, "    ").split("\n");
    const indent = indentOf(ctx);
    return [
      ...(lang ? [new Paragraph({ style: STYLE.codeLabel, indent, text: lang.toUpperCase() })] : []),
      new Paragraph({
        style: STYLE.codeBlock,
        indent,
        children: lines.map((line, i) => new TextRun({ text: line, break: i > 0 ? 1 : undefined })),
      }),
    ];
  }

  private table(node: Node, ctx: Ctx): Block[] {
    const rows = node.children.flatMap((section) =>
      section.children.map((tr) => ({ header: section.token.type === "thead_open", cells: tr.children })),
    );
    const cols = Math.max(1, ...rows.map((r) => r.cells.length));
    const cellCtx: Ctx = { ...ctx, maxImageWidth: ctx.maxImageWidth / cols - 16 };
    const border = { style: BorderStyle.SINGLE, size: 4, color: COLORS.tableBorder };
    const fill = (color: string) => ({ type: ShadingType.CLEAR, color: "auto", fill: color });

    let dataRow = 0;
    const tableRows = rows.map((row) => {
      const striped = !row.header && dataRow++ % 2 === 1;
      return new TableRow({
        tableHeader: row.header,
        cantSplit: true,
        children: Array.from({ length: cols }, (_, ci) => {
          const cell = row.cells[ci];
          const inline = cell?.children[0]?.token;
          return new TableCell({
            shading: row.header ? fill(COLORS.accent) : striped ? fill(COLORS.tableStripe) : undefined,
            margins: { top: 40, bottom: 40, left: 100, right: 100 },
            children: [
              new Paragraph({
                style: row.header ? STYLE.tableHeader : STYLE.tableText,
                alignment: alignment(cell && attr(cell.token, "style")),
                children: inline ? this.inline(inline.children ?? [], cellCtx) : [],
              }),
            ],
          });
        }),
      });
    });

    const widthTwips = Math.round(ctx.maxImageWidth * TWIPS_PER_PX);
    return [
      new Table({
        rows: tableRows,
        width: { size: 100, type: WidthType.PERCENTAGE },
        columnWidths: Array(cols).fill(Math.floor(widthTwips / cols)),
        borders: { top: border, bottom: border, left: border, right: border, insideHorizontal: border, insideVertical: border },
      }),
      new Paragraph({ style: STYLE.spacer }),
    ];
  }

  private htmlBlock(token: Token, ctx: Ctx): Block[] {
    const html = token.content.trim();
    const imgs = htmlImages(html);
    if (imgs.length) return this.figureFrom(imgs, ctx);
    if (BR_TAG.test(html)) return [new Paragraph({})];
    if (!HTML_COMMENT.test(html)) this.warnings.add("Some raw HTML blocks were skipped (only <img> and <br> are supported).");
    return [];
  }

  // ---- images -------------------------------------------------------------

  private figure(children: Token[], ctx: Ctx): Block[] {
    const imgs: HtmlImage[] = children.flatMap((c) =>
      c.type === "image" ? [{ src: attr(c, "src"), alt: c.content }] : c.type === "html_inline" ? htmlImages(c.content) : [],
    );
    return this.figureFrom(imgs, ctx);
  }

  private figureFrom(imgs: HtmlImage[], ctx: Ctx): Block[] {
    const runs = imgs.flatMap((img, i) => [
      ...(i ? [new TextRun(" ")] : []),
      this.imageOrPlaceholder(img, ctx),
    ]);
    const caption = imgs.length === 1 ? imgs[0].alt.trim() : "";
    return [
      new Paragraph({ style: STYLE.figure, indent: indentOf(ctx), children: runs }),
      ...(caption ? [new Paragraph({ style: STYLE.caption, indent: indentOf(ctx), text: caption })] : []),
    ];
  }

  private imageOrPlaceholder(img: HtmlImage, ctx: Ctx): ParagraphChild {
    const resolved = this.images.get(img.src);
    if (resolved) return this.imageRun(resolved, img.alt, ctx, img.width);
    return new TextRun({ text: `[Image: ${img.alt || img.src}]`, italics: true, color: "999999" });
  }

  private imageRun(img: ResolvedImage, alt: string, ctx: Ctx, requestedWidth?: number): ImageRun {
    let width = requestedWidth ?? img.width;
    let height = img.height * (width / img.width);
    const max = Math.max(ctx.maxImageWidth - indentLeft(ctx) / TWIPS_PER_PX, 48);
    if (width > max) {
      height *= max / width;
      width = Math.floor(max);
    }
    return new ImageRun({
      type: img.type,
      data: img.data,
      transformation: { width: Math.round(width), height: Math.round(height) },
      altText: { name: alt || "image", description: alt, title: alt },
    });
  }

  // ---- inline -------------------------------------------------------------

  private inline(children: Token[], ctx: Ctx): ParagraphChild[] {
    const out: ParagraphChild[] = [];
    let link: { href: string; runs: ParagraphChild[] } | null = null;
    let bold = 0;
    let italics = 0;
    let strike = 0;

    const push = (child: ParagraphChild) => (link ? link.runs : out).push(child);
    const text = (value: string, extra: IRunOptions = {}) =>
      push(
        new TextRun({
          text: value,
          bold: bold > 0 || undefined,
          italics: italics > 0 || undefined,
          strike: strike > 0 || undefined,
          style: link ? STYLE.hyperlink : undefined,
          ...extra,
        }),
      );

    for (const c of children) {
      switch (c.type) {
        case "text":
          text(c.content);
          break;
        case "softbreak":
          text(" ");
          break;
        case "hardbreak":
          push(new TextRun({ break: 1 }));
          break;
        case "code_inline":
          text(c.content, { style: STYLE.inlineCode });
          break;
        case "strong_open":
          bold++;
          break;
        case "strong_close":
          bold--;
          break;
        case "em_open":
          italics++;
          break;
        case "em_close":
          italics--;
          break;
        case "s_open":
          strike++;
          break;
        case "s_close":
          strike--;
          break;
        case "link_open":
          link = { href: attr(c, "href"), runs: [] };
          break;
        case "link_close":
          if (link) out.push(...this.link(link.href, link.runs));
          link = null;
          break;
        case "image":
          push(this.imageOrPlaceholder({ src: attr(c, "src"), alt: c.content }, ctx));
          break;
        case "html_inline":
          if (BR_TAG.test(c.content.trim())) push(new TextRun({ break: 1 }));
          else htmlImages(c.content).forEach((img) => push(this.imageOrPlaceholder(img, ctx)));
          break;
        default:
          if (c.content) text(c.content);
      }
    }
    if (link) out.push(...link.runs);
    return out;
  }

  private link(href: string, runs: ParagraphChild[]): ParagraphChild[] {
    if (!href) return runs;
    if (href.startsWith("#")) {
      const anchor = this.anchors.get(safeDecode(href.slice(1)).toLowerCase());
      if (anchor) return [new InternalHyperlink({ anchor, children: runs })];
      this.warnings.add(`Link target not found in this document: ${href}`);
      return runs;
    }
    return [new ExternalHyperlink({ link: href, children: runs })];
  }
}

function indentLeft(ctx: Ctx): number {
  return (ctx.listLevel >= 0 ? LIST_INDENT * (ctx.listLevel + 1) : 0) + QUOTE_INDENT * ctx.quoteDepth;
}

function indentOf(ctx: Ctx) {
  const left = indentLeft(ctx);
  return left ? { left } : undefined;
}

function isFigure(children: Token[]): boolean {
  let images = 0;
  for (const c of children) {
    if (c.type === "image") images++;
    else if (c.type === "html_inline" && htmlImages(c.content).length) images++;
    else if (c.type === "softbreak" || (c.type === "text" && !c.content.trim())) continue;
    else return false;
  }
  return images > 0;
}

/** Strip a leading `[ ]` / `[x]` from a list item and return its checked state. */
function takeTaskState(item: Node): boolean | undefined {
  const first = item.children[0];
  if (first?.token.type !== "paragraph_open") return undefined;
  const text = first.children[0]?.token.children?.[0];
  const m = text?.type === "text" ? TASK_PREFIX.exec(text.content) : null;
  if (!text || !m) return undefined;
  text.content = text.content.slice(m[0].length);
  return m[1] !== " ";
}

function attr(token: Token, name: string): string {
  return String(token.attrGet(name) ?? "");
}

function safeDecode(value: string): string {
  try {
    return decodeURIComponent(value);
  } catch {
    return value;
  }
}
