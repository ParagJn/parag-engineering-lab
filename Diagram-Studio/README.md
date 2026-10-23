# Diagram Studio

Upload a Markdown, text or Word file (or paste text) and get back the diagrams it contains, drawn in an editorial style
inspired by [cathrynlavery/diagram-design](https://github.com/cathrynlavery/diagram-design): one accent colour, 1px
hairlines, no shadows, serif titles, mono sublabels.

## How it works

1. **Plan** (`POST /api/plan`): the model reads the document and decides which diagrams it supports (0 to 8), picking a
   type for each. Nothing is drawn yet.
2. **Draw** (`POST /api/diagram`, one call per diagram, three at a time): the model returns a small JSON spec for one
   diagram. `backend/app/spec.py` validates and cleans it (dangling edges, duplicate ids, too many focal nodes).
3. **Layout + render** (browser): ELK lays out graphs, the sequence / timeline / quadrant layouts are hand-written, and
   `frontend/src/diagram/Diagram.jsx` draws SVG. The model never sees coordinates, so the diagrams stay tidy.

Diagram types: architecture, flowchart, state, sequence, timeline, quadrant.

Per diagram: SVG and PNG export, and a redraw with an optional plain-language instruction. Light and dark theme.

## Run

```
./start.sh
```

Frontend http://localhost:5250, API http://localhost:8070/docs. Needs `backend/.env` with `IBM_ICA_ENDPOINT` and
`IBM_ICA_API_KEY` (see `backend/.env.example`).

## Adding styles later

A theme is an object in `frontend/src/diagram/theme.js`; the renderer takes it as a prop. Layout is separate from
colour, so a draw.io-like or Visio-like style is a new theme plus shape tweaks keyed on `theme.style`.
