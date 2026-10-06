/**
 * Word styles and list numbering definitions.
 *
 * Formatting lives in named styles rather than on individual runs, so a
 * document can be restyled in Word (Home → Styles) after conversion.
 */
import { AlignmentType, BorderStyle, LevelFormat, ShadingType, type INumberingOptions, type IStylesOptions } from "docx";

export const FONT = "Calibri";
export const MONO_FONT = "Consolas";

export const COLORS = {
  text: "333333",
  muted: "666666",
  accent: "2C3E6B",
  link: "2A7AE2",
  quoteBar: "4A90D9",
  codeBg: "F6F8FA",
  codeBorder: "D0D7DE",
  inlineCode: "C7254E",
  tableBorder: "CCCCCC",
  tableStripe: "F2F2F2",
  rule: "AAAAAA",
};

/** Indent per list level, in twentieths of a point (720 = 0.5"). */
export const LIST_INDENT = 720;
export const LIST_HANGING = 360;
/** Extra indent per level of blockquote nesting. */
export const QUOTE_INDENT = 567;

export const STYLE = {
  quote: "BlockQuote",
  codeBlock: "CodeBlock",
  codeLabel: "CodeLabel",
  inlineCode: "InlineCode",
  caption: "Caption",
  figure: "Figure",
  tableText: "TableText",
  tableHeader: "TableHeader",
  spacer: "Spacer",
  hyperlink: "Hyperlink",
} as const;

const heading = (size: number, color: string, before: number) => ({
  run: { font: FONT, size, bold: true, color },
  paragraph: { spacing: { before, after: 80 }, keepNext: true, keepLines: true },
});

export const styles: IStylesOptions = {
  default: {
    document: {
      run: { font: FONT, size: 22, color: COLORS.text },
      paragraph: { spacing: { after: 120, line: 276 } },
    },
    heading1: heading(48, "1A1A2E", 360),
    heading2: heading(36, COLORS.accent, 300),
    heading3: heading(30, "345B8A", 240),
    heading4: heading(26, "3D6E9E", 200),
    heading5: heading(24, "555555", 200),
    heading6: heading(22, "777777", 200),
    hyperlink: { run: { color: COLORS.link, underline: {} } },
  },
  paragraphStyles: [
    {
      id: STYLE.quote,
      name: "Block Quote",
      basedOn: "Normal",
      next: "Normal",
      quickFormat: true,
      run: { color: "555555" },
      paragraph: {
        indent: { left: QUOTE_INDENT },
        border: { left: { style: BorderStyle.SINGLE, size: 18, color: COLORS.quoteBar, space: 8 } },
      },
    },
    {
      id: STYLE.codeBlock,
      name: "Code Block",
      basedOn: "Normal",
      quickFormat: true,
      run: { font: MONO_FONT, size: 18, color: "24292F" },
      paragraph: {
        spacing: { before: 0, after: 200, line: 240 },
        shading: { type: ShadingType.CLEAR, color: "auto", fill: COLORS.codeBg },
        border: {
          top: { style: BorderStyle.SINGLE, size: 4, color: COLORS.codeBorder, space: 4 },
          bottom: { style: BorderStyle.SINGLE, size: 4, color: COLORS.codeBorder, space: 4 },
          left: { style: BorderStyle.SINGLE, size: 4, color: COLORS.codeBorder, space: 4 },
          right: { style: BorderStyle.SINGLE, size: 4, color: COLORS.codeBorder, space: 4 },
        },
      },
    },
    {
      id: STYLE.codeLabel,
      name: "Code Label",
      basedOn: "Normal",
      next: STYLE.codeBlock,
      run: { size: 16, bold: true, color: COLORS.muted },
      paragraph: { spacing: { before: 120, after: 40 }, keepNext: true },
    },
    {
      id: STYLE.figure,
      name: "Figure",
      basedOn: "Normal",
      next: STYLE.caption,
      paragraph: { alignment: AlignmentType.CENTER, spacing: { before: 120, after: 60 }, keepNext: true },
    },
    {
      id: STYLE.caption,
      name: "Caption",
      basedOn: "Normal",
      next: "Normal",
      quickFormat: true,
      run: { size: 18, italics: true, color: COLORS.muted },
      paragraph: { alignment: AlignmentType.CENTER, spacing: { after: 200 } },
    },
    {
      id: STYLE.tableText,
      name: "Table Text",
      basedOn: "Normal",
      run: { size: 20 },
      paragraph: { spacing: { before: 40, after: 40, line: 240 } },
    },
    {
      id: STYLE.tableHeader,
      name: "Table Header",
      basedOn: STYLE.tableText,
      run: { bold: true, color: "FFFFFF" },
    },
    {
      id: STYLE.spacer,
      name: "Spacer",
      basedOn: "Normal",
      run: { size: 8 },
      paragraph: { spacing: { before: 0, after: 120, line: 240 } },
    },
  ],
  characterStyles: [
    {
      id: STYLE.inlineCode,
      name: "Inline Code",
      basedOn: "DefaultParagraphFont",
      run: {
        font: MONO_FONT,
        size: 19,
        color: COLORS.inlineCode,
        shading: { type: ShadingType.CLEAR, color: "auto", fill: "F5F5F5" },
      },
    },
  ],
};

const BULLET_GLYPHS = ["•", "◦", "▪"];
const ORDERED_FORMATS = [LevelFormat.DECIMAL, LevelFormat.LOWER_LETTER, LevelFormat.LOWER_ROMAN];
const LEVELS = [0, 1, 2, 3, 4, 5, 6, 7, 8];

const levelIndent = (level: number) => ({
  paragraph: { indent: { left: LIST_INDENT * (level + 1), hanging: LIST_HANGING } },
});

export const BULLET_REF = "bullet";
export const orderedRef = (start: number) => (start === 1 ? "ordered" : `ordered-from-${start}`);

/**
 * Numbering definitions. Ordered lists that start at something other than 1
 * need their own definition because the start value lives on the definition.
 */
export function numbering(orderedStarts: Iterable<number>): INumberingOptions {
  const starts = new Set([1, ...orderedStarts]);
  return {
    config: [
      {
        reference: BULLET_REF,
        levels: LEVELS.map((level) => ({
          level,
          format: LevelFormat.BULLET,
          text: BULLET_GLYPHS[level % BULLET_GLYPHS.length],
          alignment: AlignmentType.LEFT,
          style: levelIndent(level),
        })),
      },
      ...[...starts].map((start) => ({
        reference: orderedRef(start),
        levels: LEVELS.map((level) => ({
          level,
          format: ORDERED_FORMATS[level % ORDERED_FORMATS.length],
          text: `%${level + 1}.`,
          start: level === 0 ? start : 1,
          alignment: AlignmentType.LEFT,
          style: levelIndent(level),
        })),
      })),
    ],
  };
}
