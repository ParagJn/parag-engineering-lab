import { Packer } from "docx";
import JSZip from "jszip";
import { describe, expect, it } from "vitest";
import { findAsset, resolveLocal } from "../lib/paths";
import { convertMarkdown } from "./convert";
import type { AssetResolver, ResolvedImage } from "./types";

// 1×1 transparent PNG
const PNG = Uint8Array.from(
  atob("iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNkYPhfDwAChwGA60e6kgAAAABJRU5ErkJggg=="),
  (c) => c.charCodeAt(0),
);
const image = (width = 200, height = 100): ResolvedImage => ({ type: "png", data: PNG, width, height });

const assets = (overrides: Partial<AssetResolver> = {}): AssetResolver => ({
  image: async () => image(),
  mermaid: async () => image(800, 400),
  ...overrides,
});

async function convert(markdown: string, resolver = assets()) {
  const result = await convertMarkdown(markdown, resolver, { pageSize: "A4" });
  const zip = await JSZip.loadAsync(await Packer.toBuffer(result.document));
  const xml = await zip.file("word/document.xml")!.async("string");
  const core = await zip.file("docProps/core.xml")!.async("string");
  const paragraphs = [...xml.matchAll(/<w:p>[\s\S]*?<\/w:p>|<w:p [\s\S]*?<\/w:p>/g)].map((m) => m[0]);
  const text = (p: string) => [...p.matchAll(/<w:t[^>]*>([^<]*)<\/w:t>/g)].map((m) => m[1]).join("");
  return { result, xml, core, paragraphs, text };
}

describe("convertMarkdown", () => {
  it("keeps code blocks nested inside list items", async () => {
    const { xml } = await convert("1. First step\n   ```bash\n   kubectl apply -f x.yaml\n   ```\n2. Second step\n");
    expect(xml).toContain("kubectl apply -f x.yaml");
    expect(xml).toContain('w:pStyle w:val="CodeBlock"');
  });

  it("reads front matter as metadata instead of rendering it", async () => {
    const { xml, core, result } = await convert("---\ntitle: Ops Guide\nauthor: Parag\n---\n\nBody text\n");
    expect(xml).not.toContain("title: Ops Guide");
    expect(core).toContain("Ops Guide");
    expect(core).toContain("Parag");
    expect(result.meta.title).toBe("Ops Guide");
  });

  it("joins soft-wrapped lines with a space", async () => {
    const { paragraphs, text, xml } = await convert("Line one wrapped\ncontinues here.\n");
    expect(text(paragraphs[0])).toBe("Line one wrapped continues here.");
    expect(xml).not.toContain("<w:br/>");
  });

  it("creates real external and internal hyperlinks", async () => {
    const { xml } = await convert("# Rollback Plan\n\nSee [docs](https://example.com) and [rollback](#rollback-plan).\n");
    expect(xml).toMatch(/<w:hyperlink[^>]* r:id="[^"]+"/);
    expect(xml).toMatch(/<w:hyperlink[^>]* w:anchor="_h0_rollback_plan"/);
    expect(xml).toContain('w:name="_h0_rollback_plan"');
  });

  it("renders task lists as checkboxes", async () => {
    const { xml, text, paragraphs } = await convert("- [x] done task\n- [ ] open task\n");
    expect(xml.match(/w14:checkbox>/g)?.length).toBeGreaterThanOrEqual(2);
    expect(paragraphs.map(text).join("|")).not.toContain("[x]");
  });

  it("restarts numbering for each ordered list and honours start numbers", async () => {
    const { xml, result } = await convert("1. a\n2. b\n\nText\n\n1. c\n2. d\n\nMore text\n\n5. e\n");
    const numIds = new Set([...xml.matchAll(/<w:numId w:val="(\d+)"\/>/g)].map((m) => m[1]));
    expect(numIds.size).toBe(3);
    expect(result.warnings).toEqual([]);
  });

  it("keeps lists inside blockquotes as lists", async () => {
    const { paragraphs } = await convert("> Quote with list:\n> - item in quote\n");
    const item = paragraphs.find((p) => p.includes("item in quote"))!;
    expect(item).toContain("<w:numPr>");
    expect(item).toContain('w:val="BlockQuote"');
  });

  it("applies column alignment and repeats the header row", async () => {
    const { xml } = await convert("| L | C | R |\n|:--|:-:|--:|\n| a | b | 1 |\n");
    expect(xml).toContain('<w:jc w:val="center"/>');
    expect(xml).toContain('<w:jc w:val="right"/>');
    expect(xml).toContain("<w:tblHeader/>");
  });

  it("keeps inline images in reading order", async () => {
    const { paragraphs, xml } = await convert("Before ![icon](icon.png) after\n");
    expect(paragraphs).toHaveLength(1);
    const p = paragraphs[0];
    expect(p.indexOf("Before")).toBeLessThan(p.indexOf("<w:drawing>"));
    expect(p.indexOf("<w:drawing>")).toBeLessThan(p.indexOf("after"));
    expect(xml).toContain('descr="icon"');
  });

  it("survives images that fail to load", async () => {
    const { xml, result } = await convert(
      "![badge](https://img.shields.io/badge/x.svg)\n",
      assets({ image: async () => Promise.reject(new Error("CORS")) }),
    );
    expect(xml).toContain("[Image: badge]");
    expect(result.warnings[0]).toContain("img.shields.io");
  });

  it("embeds rendered mermaid diagrams and falls back to code", async () => {
    const ok = await convert("```mermaid\ngraph TD; A-->B\n```\n");
    expect(ok.xml).toContain("<w:drawing>");
    const failed = await convert("```mermaid\ngraph TD; A-->B\n```\n", assets({ mermaid: async () => null }));
    expect(failed.xml).toContain("graph TD; A--&gt;B");
    expect(failed.result.warnings[0]).toMatch(/Mermaid/);
  });

  it("scales oversized images to the page width", async () => {
    const { xml } = await convert("![big](big.png)\n", assets({ image: async () => image(3000, 1500) }));
    const cx = Number(/<wp:extent cx="(\d+)"/.exec(xml)![1]);
    const contentWidthEmu = ((11906 - 2880) / 15) * 9525;
    expect(cx).toBeLessThanOrEqual(Math.ceil(contentWidthEmu));
  });

  it("supports HTML <img> tags", async () => {
    const seen: string[] = [];
    const { xml } = await convert(
      '<p align="center"><img src="docs/logo.png" alt="Logo" width="120"></p>\n',
      assets({ image: async (src) => (seen.push(src), image(600, 300)) }),
    );
    expect(seen).toEqual(["docs/logo.png"]);
    expect(xml).toContain('<wp:extent cx="1143000"'); // 120px
  });
});

describe("local image paths", () => {
  it("resolves relative to the markdown file", () => {
    expect(resolveLocal("../img/a%20b.png?raw=1", "docs/guide/intro.md")).toBe("docs/img/a b.png");
    expect(resolveLocal("./x.png", "README.md")).toBe("x.png");
  });

  it("falls back to an unambiguous file name", () => {
    const files = new Map([["screens/arch.png", "A"], ["other/logo.png", "L1"], ["more/logo.png", "L2"]]);
    expect(findAsset(files, "images/arch.png", "doc.md")).toBe("A");
    expect(findAsset(files, "logo.png", "doc.md")).toBeUndefined();
  });
});
