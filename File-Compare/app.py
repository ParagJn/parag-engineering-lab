import json
import os
from io import BytesIO
from pathlib import Path
from typing import Any, Dict, List, Tuple

import streamlit as st
from dotenv import load_dotenv
from openai import AzureOpenAI
from pypdf import PdfReader
import difflib


CONFIG_PATH = Path("config.json")


def load_config() -> Dict:
    if not CONFIG_PATH.exists():
        raise FileNotFoundError("config.json not found in project root.")
    with open(CONFIG_PATH, "r", encoding="utf-8") as f:
        return json.load(f)


def build_azure_client() -> AzureOpenAI:
    api_key = os.getenv("AZURE_OPENAI_API_KEY")
    endpoint = os.getenv("AZURE_OPENAI_ENDPOINT")
    api_version = os.getenv("AZURE_OPENAI_API_VERSION", "2024-02-15-preview")

    if not api_key or not endpoint:
        raise ValueError(
            "Missing Azure OpenAI credentials. Set AZURE_OPENAI_API_KEY and AZURE_OPENAI_ENDPOINT in .env"
        )

    return AzureOpenAI(
        api_key=api_key,
        api_version=api_version,
        azure_endpoint=endpoint,
    )


def extract_pdf_text(
    pdf_bytes: bytes,
    include_page_markers: bool = True,
    max_pages: int = 300,
) -> Tuple[str, int]:
    reader = PdfReader(BytesIO(pdf_bytes))
    pages_to_read = min(len(reader.pages), max_pages)

    text_chunks: List[str] = []
    for idx in range(pages_to_read):
        page_text = reader.pages[idx].extract_text() or ""
        if include_page_markers:
            text_chunks.append(f"\n\n--- Page {idx + 1} ---\n{page_text}")
        else:
            text_chunks.append(page_text)

    full_text = "\n".join(text_chunks).strip()
    return full_text, pages_to_read


def truncate_for_llm(text: str, max_chars: int) -> str:
    if len(text) <= max_chars:
        return text
    return text[:max_chars] + "\n\n[TRUNCATED DUE TO LENGTH]"


def quick_text_diff(a: str, b: str, top_n: int = 12) -> Dict:
    a_lines = [line.strip() for line in a.splitlines() if line.strip()]
    b_lines = [line.strip() for line in b.splitlines() if line.strip()]

    matcher = difflib.SequenceMatcher(None, a_lines, b_lines)
    opcodes = matcher.get_opcodes()

    changes = []
    added = 0
    removed = 0
    replaced = 0

    for tag, i1, i2, j1, j2 in opcodes:
        if tag == "equal":
            continue

        a_segment = " ".join(a_lines[i1:i2])[:260]
        b_segment = " ".join(b_lines[j1:j2])[:260]

        if tag == "insert":
            added += (j2 - j1)
        elif tag == "delete":
            removed += (i2 - i1)
        elif tag == "replace":
            replaced += max(i2 - i1, j2 - j1)

        changes.append(
            {
                "type": tag,
                "file_a_excerpt": a_segment,
                "file_b_excerpt": b_segment,
                "file_a_lines": f"{i1 + 1}-{i2}",
                "file_b_lines": f"{j1 + 1}-{j2}",
            }
        )

    ratio = matcher.ratio()

    return {
        "similarity_ratio": ratio,
        "added_lines_estimate": added,
        "removed_lines_estimate": removed,
        "replaced_lines_estimate": replaced,
        "top_changes": changes[:top_n],
    }


def build_prompt(
    file_a_name: str,
    file_b_name: str,
    text_a: str,
    text_b: str,
    quick_diff: Dict,
    report_style: str,
) -> str:
    return f"""
You are a meticulous document comparison analyst.
Compare two PDF documents and produce a precise, structured report in markdown.

Report requirements:
1) Executive Summary
2) Similarities
3) Differences (major first)
4) Missing sections/topics from either document
5) Final verdict with confidence score (0-100)

Formatting requirements:
- Use markdown headings and bullet points.
- Use a table for high-priority differences with columns:
  Difference Area | File A | File B | Severity | Notes
- Be specific and quote short snippets when needed.
- If content seems truncated, mention that clearly.
- Output must be concise but detailed and actionable.

Comparison context:
- Report style: {report_style}
- File A: {file_a_name}
- File B: {file_b_name}
- Quick diff summary (pre-analysis): {json.dumps(quick_diff, ensure_ascii=True)}

===== FILE A CONTENT START =====
{text_a}
===== FILE A CONTENT END =====

===== FILE B CONTENT START =====
{text_b}
===== FILE B CONTENT END =====
""".strip()


def generate_llm_report(
    client: AzureOpenAI,
    deployment: str,
    prompt: str,
    max_output_tokens: int,
) -> str:
    system_msg = "You produce accurate document comparison reports with clear structure."
    messages = [
        {"role": "system", "content": system_msg},
        {"role": "user", "content": prompt},
    ]

    def _text_from_chat_message(message: Any) -> str:
        content = getattr(message, "content", None)
        if isinstance(content, str):
            return content.strip()
        if isinstance(content, list):
            parts: List[str] = []
            for item in content:
                text_val = None
                if isinstance(item, dict):
                    text_val = item.get("text")
                else:
                    text_val = getattr(item, "text", None)
                if isinstance(text_val, str) and text_val.strip():
                    parts.append(text_val.strip())
            return "\n".join(parts).strip()
        return ""

    def _text_from_responses(resp: Any) -> str:
        output_text = getattr(resp, "output_text", None)
        if isinstance(output_text, str) and output_text.strip():
            return output_text.strip()
        if isinstance(output_text, list):
            parts = [p.strip() for p in output_text if isinstance(p, str) and p.strip()]
            if parts:
                return "\n".join(parts)

        parts: List[str] = []
        for item in getattr(resp, "output", []) or []:
            for c in getattr(item, "content", []) or []:
                text_val = getattr(c, "text", None)
                if not text_val and isinstance(c, dict):
                    text_val = c.get("text")
                if isinstance(text_val, str) and text_val.strip():
                    parts.append(text_val.strip())
        return "\n".join(parts).strip()

    try:
        response = client.chat.completions.create(
            model=deployment,
            max_completion_tokens=max_output_tokens,
            messages=messages,
        )
        choice = response.choices[0] if response.choices else None
        if choice and getattr(choice, "message", None):
            content = _text_from_chat_message(choice.message)
            if content:
                return content
    except Exception:
        # Fall back to Responses API below.
        pass

    try:
        response = client.responses.create(
            model=deployment,
            input=messages,
            max_output_tokens=max_output_tokens,
        )
        content = _text_from_responses(response)
        if content:
            return content
    except Exception as exc:
        raise RuntimeError(
            "Both Chat Completions and Responses API calls failed. "
            "Check deployment name, model compatibility, and Azure API version."
        ) from exc

    raise RuntimeError(
        "Azure model returned an empty output. Try increasing max_output_tokens or using a different deployment."
    )


def main() -> None:
    load_dotenv()
    config = load_config()
    app_cfg = config.get("app", {})
    pdf_cfg = config.get("pdf", {})
    llm_cfg = config.get("llm", {})
    report_cfg = config.get("report", {})

    st.set_page_config(page_title=app_cfg.get("title", "PDF Compare"), layout="wide")

    st.title(app_cfg.get("title", "PDF Comparison Tool"))
    st.caption(app_cfg.get("description", "Upload two PDFs and compare their content."))

    with st.sidebar:
        st.header("Configuration")
        st.write("Runtime settings are loaded from `config.json`.")
        st.json(config)

    col1, col2 = st.columns(2)
    with col1:
        file_a = st.file_uploader("Upload File A (PDF)", type=["pdf"], key="file_a")
    with col2:
        file_b = st.file_uploader("Upload File B (PDF)", type=["pdf"], key="file_b")

    if not file_a or not file_b:
        st.info("Please upload both PDF files to continue.")
        return

    if st.button("Compare Files", type="primary"):
        try:
            with st.spinner("Extracting PDF text..."):
                text_a, pages_a = extract_pdf_text(
                    file_a.getvalue(),
                    include_page_markers=pdf_cfg.get("include_page_markers", True),
                    max_pages=pdf_cfg.get("max_pages", 300),
                )
                text_b, pages_b = extract_pdf_text(
                    file_b.getvalue(),
                    include_page_markers=pdf_cfg.get("include_page_markers", True),
                    max_pages=pdf_cfg.get("max_pages", 300),
                )

                if not text_a.strip() or not text_b.strip():
                    st.error(
                        "Could not extract text from one or both files. The PDFs may be scanned/image-only."
                    )
                    return

                quick_diff = quick_text_diff(
                    text_a,
                    text_b,
                    top_n=report_cfg.get("summary_top_n", 12),
                )

                max_chars = pdf_cfg.get("max_characters_for_llm", 180000)
                text_a_for_llm = truncate_for_llm(text_a, max_chars)
                text_b_for_llm = truncate_for_llm(text_b, max_chars)

            st.subheader("Quick Comparison Stats")
            s1, s2, s3, s4, s5 = st.columns(5)
            s1.metric("Pages A", pages_a)
            s2.metric("Pages B", pages_b)
            s3.metric("Similarity", f"{quick_diff['similarity_ratio'] * 100:.2f}%")
            s4.metric("Added (est)", quick_diff["added_lines_estimate"])
            s5.metric("Removed/Replaced (est)", quick_diff["removed_lines_estimate"] + quick_diff["replaced_lines_estimate"])

            with st.expander("Top Raw Differences (Quick Heuristic)", expanded=False):
                for idx, change in enumerate(quick_diff["top_changes"], start=1):
                    st.markdown(
                        f"**{idx}. {change['type'].upper()}**  \
File A lines: `{change['file_a_lines']}`  \
File B lines: `{change['file_b_lines']}`"
                    )
                    st.write(f"A: {change['file_a_excerpt']}")
                    st.write(f"B: {change['file_b_excerpt']}")
                    st.divider()

            with st.spinner("Generating detailed AI report with Azure OpenAI..."):
                client = build_azure_client()
                deployment = os.getenv("AZURE_OPENAI_DEPLOYMENT")
                if not deployment:
                    st.error("Missing AZURE_OPENAI_DEPLOYMENT in .env")
                    return

                prompt = build_prompt(
                    file_a_name=file_a.name,
                    file_b_name=file_b.name,
                    text_a=text_a_for_llm,
                    text_b=text_b_for_llm,
                    quick_diff=quick_diff,
                    report_style=llm_cfg.get("report_style", "detailed"),
                )

                try:
                    report = generate_llm_report(
                        client=client,
                        deployment=deployment,
                        prompt=prompt,
                        max_output_tokens=llm_cfg.get("max_output_tokens", 1800),
                    )
                except Exception as llm_exc:
                    st.error(f"LLM report generation failed: {llm_exc}")
                    return

            st.subheader("Detailed Comparison Report")
            st.markdown(report)

            st.download_button(
                "Download Report (Markdown)",
                data=report.encode("utf-8"),
                file_name=f"comparison_report_{Path(file_a.name).stem}_vs_{Path(file_b.name).stem}.md",
                mime="text/markdown",
            )

            if report_cfg.get("show_raw_text_preview", False):
                with st.expander("Extracted Text Preview", expanded=False):
                    p1, p2 = st.columns(2)
                    with p1:
                        st.markdown(f"### {file_a.name}")
                        st.text_area("Text A", text_a[:5000], height=300)
                    with p2:
                        st.markdown(f"### {file_b.name}")
                        st.text_area("Text B", text_b[:5000], height=300)

        except Exception as exc:
            st.exception(exc)


if __name__ == "__main__":
    main()
