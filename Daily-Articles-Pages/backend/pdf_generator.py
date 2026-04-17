"""Generate PDF from magazine HTML using Playwright (Chromium).

Renders the exact same as a browser — full CSS fidelity, clickable hyperlinks.
"""

import re
from playwright.async_api import async_playwright


def _prepare_html_for_pdf(html: str) -> str:
    """Adjust HTML for better PDF rendering."""
    # Remove the back-to-top button (not useful in PDF)
    html = re.sub(
        r'<button class="back-to-top".*?</button>',
        '',
        html,
        flags=re.DOTALL,
    )
    # Remove the back-to-top JS
    html = re.sub(
        r"<script>\s*\(function\(\)\s*\{.*?backToTop.*?\}\)\(\);\s*</script>",
        '',
        html,
        flags=re.DOTALL,
    )
    # Remove "Applies to You" badges
    html = re.sub(
        r'<div class="flag-badge">.*?</div>',
        '',
        html,
        flags=re.DOTALL,
    )

    # Add PDF-specific CSS: page breaks between spreads, disable animations
    pdf_css = """
    <style>
    /* PDF overrides */
    .cover {
      min-height: 100vh !important;
      page-break-after: always;
    }
    .toc {
      page-break-after: always;
    }
    .spread {
      page-break-before: always;
      page-break-inside: avoid;
    }
    .footer {
      page-break-before: always;
    }
    /* Disable animations */
    *, *::before, *::after {
      animation: none !important;
      transition: none !important;
    }
    </style>
    """
    html = html.replace('</head>', pdf_css + '\n</head>')
    return html


async def generate_pdf(html: str) -> bytes:
    """Convert magazine HTML to PDF bytes using headless Chromium.

    Returns raw PDF bytes suitable for saving or email attachment.
    """
    prepared = _prepare_html_for_pdf(html)
    async with async_playwright() as p:
        browser = await p.chromium.launch()
        page = await browser.new_page()
        await page.set_content(prepared, wait_until="networkidle")
        pdf_bytes = await page.pdf(
            format="A4",
            print_background=True,
            margin={"top": "0", "right": "0", "bottom": "0", "left": "0"},
        )
        await browser.close()
    return pdf_bytes
