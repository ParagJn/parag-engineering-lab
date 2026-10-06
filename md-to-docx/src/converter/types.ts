export type ImageType = "png" | "jpg" | "gif" | "bmp";

/** An image ready to embed: raster bytes plus the size it should display at (px @ 96 dpi). */
export interface ResolvedImage {
  type: ImageType;
  data: Uint8Array;
  width: number;
  height: number;
}

/**
 * Loads the external pieces a markdown file refers to. The converter itself is
 * environment-agnostic; the browser provides the real implementation and tests
 * provide stubs.
 */
export interface AssetResolver {
  image(src: string): Promise<ResolvedImage | null>;
  mermaid(code: string): Promise<ResolvedImage | null>;
}

export type PageSize = "A4" | "Letter";

export interface ConvertOptions {
  pageSize: PageSize;
}

export interface DocumentMeta {
  title?: string;
  author?: string;
  subject?: string;
  description?: string;
  keywords?: string;
  [key: string]: unknown;
}
