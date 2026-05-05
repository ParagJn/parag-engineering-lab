"""
PDF export using Playwright — renders the generated HTML CV to a PDF file.
Uses the venv's Playwright installation.
"""
import asyncio
import logging
import os
import re
import tempfile
from pathlib import Path

logger = logging.getLogger(__name__)

# Injected before </head> — overrides whatever print CSS the HTML contains
PRINT_CSS_OVERRIDE = """
<style id="pdf-print-overrides">
@media print {
    /* ── Page setup ── */
    @page {
        size: A4;
        margin: 0;
    }

    /* ── Reset animations & reveals ── */
    *, *::before, *::after {
        animation: none !important;
        transition: none !important;
    }
    .reveal, [class*="reveal"] {
        opacity: 1 !important;
        transform: none !important;
    }
    canvas { display: none !important; }

    /* ── Floating / sticky UI chrome ── */
    nav, .nav, .floating-nav, .sticky-nav,
    [class*="floating"], [class*="sticky"] {
        display: none !important;
    }

    /* ── Page background & text ── */
    html, body {
        background: #ffffff !important;
        color: #1e293b !important;
        font-size: 10.5pt !important;
        line-height: 1.45 !important;
        width: 100% !important;
        margin: 0 !important;
        padding: 0 !important;
    }

    /* ── Container ── */
    .page,
    .resume-page,
    .container {
        width: 210mm !important;
        min-height: 297mm !important;
        max-width: 100% !important;
        padding: 0.5in !important;
        margin: 0 auto !important;
        box-sizing: border-box !important;
        box-shadow: none !important;
        background: #ffffff !important;
    }

    /* ── Header: keep dark, reduce padding ── */
    .header, header {
        padding: 22px 0 18px !important;
        -webkit-print-color-adjust: exact !important;
        print-color-adjust: exact !important;
    }
    .name, .header h1 { font-size: 1.9rem !important; }
    .title, .header p  { font-size: 0.95rem !important; }

    /* ── Sections: tighter spacing, no orphan breaks ── */
    .section, section {
        padding: 18px 0 !important;
        page-break-inside: avoid;
    }
    .section-title, h2 {
        font-size: 1.1rem !important;
        margin-bottom: 12px !important;
        page-break-after: avoid;
    }

    /* ── Cards & blocks: never split mid-card ── */
    .summary,
    .current-role-card,
    .competencies-card,
    .tech-card,
    .cert-card,
    .achievement-item,
    .achievements-list {
        page-break-inside: avoid !important;
        box-shadow: none !important;
        border: 1px solid #e2e8f0 !important;
    }

    /* ── Timeline: each job stays together ── */
    .timeline-item {
        page-break-inside: avoid !important;
        box-shadow: none !important;
        border: 1px solid #e2e8f0 !important;
        margin-bottom: 12px !important;
        padding: 16px !important;
    }
    /* Keep the vertical line visible */
    .timeline::before {
        -webkit-print-color-adjust: exact !important;
        print-color-adjust: exact !important;
    }

    /* ── Projects: 2-col for print (3-col is too narrow on A4) ── */
    .projects-grid {
        grid-template-columns: 1fr 1fr !important;
        gap: 14px !important;
    }
    .project-card {
        page-break-inside: avoid !important;
        box-shadow: none !important;
        border: 1px solid #e2e8f0 !important;
        padding: 16px !important;
        -webkit-print-color-adjust: exact !important;
        print-color-adjust: exact !important;
    }

    /* ── Competencies & certs: keep 2-col ── */
    .competencies-grid,
    .certs-grid {
        grid-template-columns: 1fr 1fr !important;
        gap: 14px !important;
    }

    /* ── Badges: preserve colour fills ── */
    .competency-badge,
    .tech-badge,
    .status-badge,
    [class*="badge"] {
        -webkit-print-color-adjust: exact !important;
        print-color-adjust: exact !important;
    }

    /* ── Value / footer section ── */
    .value-section, footer, [class*="value"] {
        page-break-inside: avoid !important;
        -webkit-print-color-adjust: exact !important;
        print-color-adjust: exact !important;
        padding: 24px 0 !important;
    }
    .cv-footer, .resume-footer, footer {
        border-top: 1px solid #cbd5e1 !important;
        margin-top: 24px !important;
        padding-top: 12px !important;
        text-align: center !important;
    }

    /* ── Links: show URL in print ── */
    a[href]::after {
        content: none !important; /* don't append URLs — clutters the CV */
    }
    a { color: inherit !important; text-decoration: none !important; }
}
</style>
"""


def _inject_print_css(html: str) -> str:
    """Insert PRINT_CSS_OVERRIDE immediately before </head>."""
    close_head = re.compile(r"</head>", re.IGNORECASE)
    if close_head.search(html):
        return close_head.sub(PRINT_CSS_OVERRIDE + "\n</head>", html, count=1)
    # Fallback: prepend to body
    return PRINT_CSS_OVERRIDE + html


async def html_to_pdf(html_content: str, output_path: str) -> bool:
    """Render html_content to a PDF at output_path. Returns True on success."""
    try:
        from playwright.async_api import async_playwright

        patched_html = _inject_print_css(html_content)

        async with async_playwright() as p:
            browser = await p.chromium.launch()
            page = await browser.new_page(viewport={"width": 1280, "height": 900})

            with tempfile.NamedTemporaryFile(
                suffix=".html", delete=False, mode="w", encoding="utf-8"
            ) as tmp:
                tmp.write(patched_html)
                tmp_path = tmp.name

            try:
                await page.goto(f"file://{tmp_path}", wait_until="domcontentloaded")
                # Wait for web fonts (Google Fonts, Font Awesome) to finish loading
                try:
                    await page.wait_for_load_state("networkidle", timeout=8000)
                except Exception:
                    # If network never idles (e.g. CDN blocked), wait a fixed amount
                    await page.wait_for_timeout(4000)

                await page.pdf(
                    path=output_path,
                    format="A4",
                    print_background=True,
                    prefer_css_page_size=False,  # let @page margin rule
                    display_header_footer=False,
                    margin={"top": "0", "right": "0", "bottom": "0", "left": "0"},
                )
            finally:
                os.unlink(tmp_path)

            await browser.close()
        return True
    except Exception as e:
        logger.error(f"PDF generation error: {e}")
        return False
