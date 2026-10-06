import { Packer } from "docx";
import { convertMarkdown } from "../converter/convert";
import type { ConvertOptions, DocumentMeta } from "../converter/types";
import { createBrowserAssets } from "./browserAssets";

export interface ConvertedFile {
  blob: Blob;
  meta: DocumentMeta;
  warnings: string[];
}

export async function convertFile(
  markdown: string,
  path: string,
  assets: Map<string, File>,
  options: ConvertOptions,
): Promise<ConvertedFile> {
  const { document, meta, warnings } = await convertMarkdown(markdown, createBrowserAssets(assets, path), options);
  return { blob: await Packer.toBlob(document), meta, warnings };
}
