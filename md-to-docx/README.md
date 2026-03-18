# MD to DOCX Converter

A utility to convert Markdown (`.md`) documents to Word (`.docx`) format, producing professionally formatted documents that can be shared in a business-friendly format.

## Features

- Upload one or more `.md` files and convert them to `.docx`
- Mermaid diagrams rendered as embedded PNG images
- Full support for tables, code blocks, lists, blockquotes, images, and all standard Markdown elements
- Converted files saved to `docx-outputs/` with date-stamped filenames
- Sidebar with conversion history and one-click downloads
- Bulk download as ZIP when converting multiple files

## Setup

```bash
pip install -r requirements.txt
```

## Usage

```bash
streamlit run app.py
```

Upload your `.md` files through the web interface and download the converted `.docx` documents.
