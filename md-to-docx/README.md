# MD to DOCX Converter

Convert Markdown (`.md`) files into professionally formatted Word (`.docx`) documents. The app runs entirely in the browser: your files, images and diagrams are never uploaded anywhere.

## Features

- Drag and drop files or **whole folders**, or **paste Markdown** directly (handy for chat responses)
- Native Word structure: real heading styles, numbered and bulleted lists (numbering restarts per list), **clickable links**, internal `#anchor` links to headings, task-list **checkboxes**
- Code blocks (including inside list items), block quotes with nested content, horizontal rules
- Tables with column alignment, a header row that repeats across pages, and striped rows
- Images from your folder, data URIs or the web. SVG and WebP are converted automatically, `<img>` HTML tags are supported, and everything is scaled to fit the page
- **Mermaid diagrams rendered locally** at high resolution (no third-party service)
- YAML front matter (`title`, `author`, `subject`, `description`, `keywords`) becomes document properties
- A4 or Letter page size
- Formatting is defined as Word styles (Code Block, Block Quote, Caption, …), so documents can be restyled in Word
- Conversion history (last 50) kept in the browser, plus ZIP download for multiple files

## Getting started

```bash
./start.sh              # installs/updates dependencies, then opens http://localhost:5173
./start.sh --latest     # also upgrades dependencies to new major versions
./start.sh --no-update  # skip updating (offline)
```

Requires Node.js 20+.

## Development

```bash
npm test          # converter tests (Vitest)
npm run typecheck
npm run build
```

### Layout

```
src/
  converter/        Markdown → docx core (environment-agnostic, unit tested)
    convert.ts      token tree walker / renderer
    styles.ts       Word styles and list numbering
    frontMatter.ts  YAML front matter
  lib/
    browserAssets.ts  image loading, SVG rasterising, local Mermaid rendering
    history.ts        IndexedDB conversion history
    paths.ts, files.ts
  components/       React UI (Tailwind CSS)
```

## Known limitations

- Remote images on hosts that block cross-origin requests can't be fetched from the browser. They appear as `[Image: …]` placeholders with a warning. Workaround: download them next to the `.md` file.
- Raw HTML other than `<img>` and `<br>` is skipped.
