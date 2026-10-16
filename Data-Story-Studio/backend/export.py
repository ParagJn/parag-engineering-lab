"""Exports: a self-contained interactive HTML report, and a PDF printed from it.

The HTML embeds the prebuilt viewer bundle (frontend/dist-viewer) plus the dashboard JSON, so
the file works offline — animation, hover tooltips, insight notes, data tables and SQL all run
locally. Filters are frozen as they were at export time; asking new questions needs the live app.
"""

import html
import json
import re
import time
from pathlib import Path

from config import get_settings
from workspace import jsonable


class ExportError(RuntimeError):
    pass


def _viewer_assets() -> tuple[str, str]:
    dist: Path = get_settings().viewer_dist
    js = sorted(dist.glob("*.js"))
    css = sorted(dist.glob("*.css"))
    if not js:
        raise ExportError("Report viewer isn't built yet — run start.sh (it builds frontend/dist-viewer).")
    return js[0].read_text(), "\n".join(c.read_text() for c in css)


def build_html(payload: dict, title: str) -> str:
    js, css = _viewer_assets()
    data = json.dumps(payload, default=jsonable, separators=(",", ":"))
    # keep "</script>" inside JSON from closing the tag
    data = data.replace("</", "<\\/")
    js = js.replace("</script", "<\\/script")
    return f"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{html.escape(title)}</title>
<style>{css}</style>
</head>
<body>
<div id="root"></div>
<script id="dashboard-data" type="application/json">{data}</script>
<script>{js}</script>
</body>
</html>"""


def safe_filename(title: str, ext: str) -> str:
    base = re.sub(r"[^A-Za-z0-9]+", "-", title).strip("-")[:60] or "dashboard"
    return f"{base}-{time.strftime('%Y%m%d')}.{ext}"


async def build_pdf(html_doc: str) -> bytes:
    try:
        from playwright.async_api import async_playwright
    except ImportError as err:
        raise ExportError("PDF export needs Playwright: pip install playwright && playwright install chromium") from err
    async with async_playwright() as p:
        try:
            browser = await p.chromium.launch()
        except Exception as err:
            raise ExportError(f"Couldn't start Chromium for PDF export ({err}). Run: playwright install chromium") from err
        try:
            page = await browser.new_page(viewport={"width": 1280, "height": 900}, device_scale_factor=2)
            await page.emulate_media(media="print", reduced_motion="reduce")
            # the viewer reads #print to skip animation and expand everything
            await page.set_content(html_doc.replace('<div id="root"></div>', '<div id="root" data-print="1"></div>'),
                                   wait_until="load")
            await page.wait_for_function("window.__DASHBOARD_READY__ === true", timeout=30000)
            await page.wait_for_timeout(400)
            return await page.pdf(format="A4", print_background=True, prefer_css_page_size=True,
                                  margin={"top": "14mm", "bottom": "14mm", "left": "12mm", "right": "12mm"})
        finally:
            await browser.close()


async def print_pdf(html_doc: str) -> bytes:
    """Print a plain static HTML document (no viewer bundle) to an A4 PDF; margins come from its @page rule."""
    try:
        from playwright.async_api import async_playwright
    except ImportError as err:
        raise ExportError("PDF export needs Playwright: pip install playwright && playwright install chromium") from err
    async with async_playwright() as p:
        try:
            browser = await p.chromium.launch()
        except Exception as err:
            raise ExportError(f"Couldn't start Chromium for PDF export ({err}). Run: playwright install chromium") from err
        try:
            page = await browser.new_page()
            await page.set_content(html_doc, wait_until="load")
            return await page.pdf(format="A4", print_background=True, prefer_css_page_size=True)
        finally:
            await browser.close()
