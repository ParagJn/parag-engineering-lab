"""
Streamlit app – Markdown to Word Document Converter.

Upload one or more .md files and download professionally formatted .docx files.
Mermaid diagrams are rendered as embedded images.
"""

import io
import os
import zipfile
from datetime import datetime
from pathlib import Path

import streamlit as st
from converter import convert_md_to_docx

OUTPUT_DIR = Path("docx-outputs")
OUTPUT_DIR.mkdir(exist_ok=True)

# ---------------------------------------------------------------------------
# Page config
# ---------------------------------------------------------------------------
st.set_page_config(
    page_title="MD → DOCX Converter",
    page_icon="📄",
    layout="wide",
)

# ---------------------------------------------------------------------------
# Custom CSS
# ---------------------------------------------------------------------------
st.markdown(
    """
    <style>
    .stFileUploader > div { border: 2px dashed #4A90D9; border-radius: 12px; padding: 1rem; }
    h1 { color: #1A1A2E; }
    .success-box { background: #E8F5E9; border-left: 4px solid #43A047; padding: 12px 16px;
                   border-radius: 6px; margin: 8px 0; }
    .info-box { background: #E3F2FD; border-left: 4px solid #1E88E5; padding: 12px 16px;
                border-radius: 6px; margin: 8px 0; }
    </style>
    """,
    unsafe_allow_html=True,
)

# ---------------------------------------------------------------------------
# Sidebar
# ---------------------------------------------------------------------------
st.sidebar.title("📄 MD → DOCX Converter")


def _render_sidebar_history():
    """Render the conversion history in the sidebar."""
    st.sidebar.divider()
    st.sidebar.subheader("📂 Conversion History")
    history_files = sorted(OUTPUT_DIR.glob("*.docx"), key=lambda f: f.stat().st_mtime, reverse=True)
    if history_files:
        for hf in history_files:
            st.sidebar.download_button(
                label=f"📥 {hf.name}",
                data=hf.read_bytes(),
                file_name=hf.name,
                mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                key=f"hist_{hf.name}",
                use_container_width=True,
            )
    else:
        st.sidebar.caption("No files converted yet.")

# ---------------------------------------------------------------------------
# Header
# ---------------------------------------------------------------------------
st.title("📄 Markdown → Word Converter")
st.markdown(
    "Upload one or more **`.md`** files and convert them to beautifully "
    "formatted **Word documents** (`.docx`). Mermaid diagrams, images, tables, "
    "code blocks, and all standard Markdown elements are fully supported."
)

st.divider()

# ---------------------------------------------------------------------------
# File uploader
# ---------------------------------------------------------------------------
uploaded_files = st.file_uploader(
    "Drop your Markdown files here",
    type=["md"],
    accept_multiple_files=True,
    help="You can upload one or more .md files at once.",
)

if not uploaded_files:
    _render_sidebar_history()
    st.info("👆 Upload at least one `.md` file to get started.")
    st.stop()

# ---------------------------------------------------------------------------
# Conversion
# ---------------------------------------------------------------------------
st.divider()
st.subheader("📋 Uploaded Files")

converted: list[tuple[str, io.BytesIO]] = []

with st.spinner("Converting files…"):
    date_suffix = datetime.now().strftime("%d%m%Y")
    for uf in uploaded_files:
        md_text = uf.read().decode("utf-8", errors="replace")
        stem = Path(uf.name).stem
        fname = f"{stem}_{date_suffix}.docx"

        col1, col2 = st.columns([3, 1])
        with col1:
            with st.expander(f"📝 {uf.name}", expanded=False):
                st.markdown(md_text[:3000] + ("…" if len(md_text) > 3000 else ""))

        try:
            docx_buf = convert_md_to_docx(md_text)
            # Save to docx-outputs folder
            output_path = OUTPUT_DIR / fname
            output_path.write_bytes(docx_buf.getvalue())
            converted.append((fname, docx_buf))
            with col2:
                st.success("✅ Done")
        except Exception as e:
            with col2:
                st.error("❌ Error")
            st.exception(e)

# Render sidebar history after conversion so new files appear immediately
_render_sidebar_history()

# ---------------------------------------------------------------------------
# Downloads
# ---------------------------------------------------------------------------
if converted:
    st.divider()
    st.subheader("⬇️ Download")

    # Individual downloads
    for fname, buf in converted:
        st.download_button(
            label=f"📥 {fname}",
            data=buf.getvalue(),
            file_name=fname,
            mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            use_container_width=True,
        )

    # Zip bundle when multiple files
    if len(converted) > 1:
        st.markdown("---")
        zip_buf = io.BytesIO()
        with zipfile.ZipFile(zip_buf, "w", zipfile.ZIP_DEFLATED) as zf:
            for fname, buf in converted:
                zf.writestr(fname, buf.getvalue())
        zip_buf.seek(0)

        st.download_button(
            label="📦 Download All as ZIP",
            data=zip_buf.getvalue(),
            file_name="converted_documents.zip",
            mime="application/zip",
            use_container_width=True,
        )

# ---------------------------------------------------------------------------
# Footer
# ---------------------------------------------------------------------------
st.divider()
st.caption(
    "Built with Streamlit & python-docx · "
    "Mermaid diagrams rendered via mermaid.ink"
)
