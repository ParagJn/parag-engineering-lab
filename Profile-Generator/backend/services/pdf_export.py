"""
PDF export using Playwright — renders the generated HTML CV to a PDF file.
Uses the venv's Playwright installation.
"""
import asyncio
import logging
import os
import tempfile
from pathlib import Path

logger = logging.getLogger(__name__)


async def html_to_pdf(html_content: str, output_path: str) -> bool:
    """Render html_content to a PDF at output_path. Returns True on success."""
    try:
        from playwright.async_api import async_playwright

        async with async_playwright() as p:
            browser = await p.chromium.launch()
            page = await browser.new_page()

            # Write HTML to a temp file so local resources resolve correctly
            with tempfile.NamedTemporaryFile(
                suffix=".html", delete=False, mode="w", encoding="utf-8"
            ) as tmp:
                tmp.write(html_content)
                tmp_path = tmp.name

            try:
                await page.goto(f"file://{tmp_path}")
                await page.wait_for_timeout(3000)  # allow fonts/icons to load
                await page.pdf(
                    path=output_path,
                    format="A4",
                    print_background=True,
                    prefer_css_page_size=True,
                    margin={"top": "0", "right": "0", "bottom": "0", "left": "0"},
                )
            finally:
                os.unlink(tmp_path)

            await browser.close()
        return True
    except Exception as e:
        logger.error(f"PDF generation error: {e}")
        return False
