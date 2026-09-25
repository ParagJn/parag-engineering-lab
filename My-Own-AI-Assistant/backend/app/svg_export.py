"""Experimental: export an (optionally animated) SVG as MP4 or GIF.

SVG animations (SMIL <animate>/<animateTransform>, CSS @keyframes) only play
in a real browser, so the SVG is loaded into headless Chromium via
Playwright. Animations are paused and stepped to exact timestamps, one
screenshot per frame, and ffmpeg encodes the frames. Stepping (rather than
recording in real time) gives smooth, deterministic frames.

Requires: `playwright` + `playwright install chromium`, and ffmpeg on PATH.
"""

import asyncio
import shutil
import tempfile
from pathlib import Path
from typing import Literal

ExportFormat = Literal["mp4", "gif"]

FPS = 15
RENDER_WIDTH = 800
MAX_RENDER_HEIGHT = 1200
DEFAULT_DURATION = 3.0      # seconds, when animations don't declare a finite duration
MAX_DURATION = 10.0         # cap so a long animation can't produce a huge file
STATIC_DURATION = 2.0       # MP4 length for an SVG with no animations
RENDER_TIMEOUT = 120        # seconds for the whole export

PAGE_TEMPLATE = (
    "<!DOCTYPE html><html><head><style>"
    "html,body{{margin:0;padding:0;background:#fff;overflow:hidden}}"
    "svg{{display:block}}"
    "</style></head><body>{svg}</body></html>"
)

# Returns the SVG's intrinsic aspect ratio from its viewBox (or rendered box)
JS_ASPECT = """() => {
  const svg = document.querySelector('svg');
  const vb = svg.viewBox && svg.viewBox.baseVal;
  if (vb && vb.width && vb.height) return vb.height / vb.width;
  const r = svg.getBoundingClientRect();
  return r.width && r.height ? r.height / r.width : 0.625;
}"""

JS_SIZE = """([w, h]) => {
  const svg = document.querySelector('svg');
  svg.setAttribute('width', w);
  svg.setAttribute('height', h);
}"""

# Finds SMIL + CSS animations and the longest single cycle among them
JS_ANIMATION_INFO = """() => {
  const parse = (v) => {
    if (!v) return 0;
    v = v.trim();
    let n;
    if (v.endsWith('ms')) n = parseFloat(v) / 1000;
    else if (v.endsWith('min')) n = parseFloat(v) * 60;
    else if (v.endsWith('h')) n = parseFloat(v) * 3600;
    else n = parseFloat(v);  // "2s" or bare "2"
    return isNaN(n) ? 0 : n;
  };
  let count = 0, longest = 0;
  document.querySelectorAll('animate, animateTransform, animateMotion, animateColor, set').forEach((el) => {
    count++;
    const begin = parse((el.getAttribute('begin') || '0').split(';')[0]);
    longest = Math.max(longest, begin + parse(el.getAttribute('dur')));
  });
  document.getAnimations().forEach((a) => {
    count++;
    const t = a.effect.getTiming();
    const d = typeof t.duration === 'number' ? t.duration : 0;
    longest = Math.max(longest, ((t.delay || 0) + d) / 1000);
  });
  return { count, longest };
}"""

# Pauses everything and jumps to time t (seconds); resolves after a repaint
JS_SEEK = """(t) => new Promise((resolve) => {
  document.querySelectorAll('svg').forEach((svg) => {
    if (!svg.ownerSVGElement && svg.pauseAnimations) {
      svg.pauseAnimations();
      svg.setCurrentTime(t);
    }
  });
  document.getAnimations().forEach((a) => { a.pause(); a.currentTime = t * 1000; });
  requestAnimationFrame(() => requestAnimationFrame(resolve));
})"""


class SvgExportError(RuntimeError):
    """Raised when an SVG can't be exported."""


def _even(n: float) -> int:
    """H.264 (yuv420p) needs even dimensions."""
    return max(2, int(round(n / 2)) * 2)


async def _capture_frames(svg: str, frames_dir: Path, fmt: ExportFormat) -> int:
    """Render the SVG in Chromium and write frame_0000.png... Returns frame count."""
    try:
        from playwright.async_api import Error as PlaywrightError, async_playwright
    except ImportError as e:
        raise SvgExportError(
            "Playwright is not installed. Run: pip install playwright && playwright install chromium"
        ) from e

    try:
        async with async_playwright() as p:
            browser = await p.chromium.launch()
            try:
                page = await browser.new_page(viewport={"width": RENDER_WIDTH, "height": 600})
                await page.set_content(PAGE_TEMPLATE.format(svg=svg))

                aspect = await page.evaluate(JS_ASPECT)
                width = _even(RENDER_WIDTH)
                height = _even(min(RENDER_WIDTH * aspect, MAX_RENDER_HEIGHT))
                await page.set_viewport_size({"width": width, "height": height})
                await page.evaluate(JS_SIZE, [width, height])

                info = await page.evaluate(JS_ANIMATION_INFO)
                if info["count"] == 0:
                    # Static SVG: one frame for GIF, a short still clip for MP4
                    duration = 0 if fmt == "gif" else STATIC_DURATION
                else:
                    duration = min(info["longest"] or DEFAULT_DURATION, MAX_DURATION)

                # Frames cover [0, duration) so the loop point doesn't repeat a frame
                frame_count = max(1, round(duration * FPS))
                for i in range(frame_count):
                    await page.evaluate(JS_SEEK, i / FPS)
                    await page.screenshot(path=str(frames_dir / f"frame_{i:04d}.png"))
                return frame_count
            finally:
                await browser.close()
    except PlaywrightError as e:
        if "Executable doesn't exist" in str(e):
            raise SvgExportError("Chromium for Playwright is missing. Run: playwright install chromium") from e
        raise SvgExportError(f"Browser rendering failed: {e}") from e


async def _encode(frames_dir: Path, out_path: Path, fmt: ExportFormat) -> None:
    ffmpeg = shutil.which("ffmpeg")
    if not ffmpeg:
        raise SvgExportError("ffmpeg was not found on PATH (install with: brew install ffmpeg)")

    args = [ffmpeg, "-y", "-loglevel", "error", "-framerate", str(FPS), "-i", str(frames_dir / "frame_%04d.png")]
    if fmt == "mp4":
        args += ["-c:v", "libx264", "-pix_fmt", "yuv420p", "-crf", "18", "-movflags", "+faststart"]
    else:
        # Two-pass palette keeps GIF colours as close as 256 colours allow
        args += [
            "-vf", "split[a][b];[a]palettegen=stats_mode=diff[p];[b][p]paletteuse=dither=bayer:bayer_scale=5",
            "-loop", "0",
        ]
    args.append(str(out_path))

    proc = await asyncio.create_subprocess_exec(
        *args, stdout=asyncio.subprocess.DEVNULL, stderr=asyncio.subprocess.PIPE
    )
    _, stderr = await proc.communicate()
    if proc.returncode != 0:
        raise SvgExportError(f"ffmpeg failed: {stderr.decode('utf-8', 'replace')[-400:]}")


async def export_svg(svg_path: Path, fmt: ExportFormat) -> Path:
    """
    Export `svg_path` to MP4/GIF next to it (e.g. svg_x.svg -> svg_x.mp4).
    SVG files never change (edits create new IDs), so an existing export is reused.
    """
    out_path = svg_path.with_suffix(f".{fmt}")
    if out_path.exists():
        return out_path

    svg = svg_path.read_text(encoding="utf-8")
    tmp_out = out_path.with_suffix(f".tmp.{fmt}")

    async def run():
        with tempfile.TemporaryDirectory(prefix="svg_export_") as tmp:
            frames_dir = Path(tmp)
            await _capture_frames(svg, frames_dir, fmt)
            await _encode(frames_dir, tmp_out, fmt)
        tmp_out.replace(out_path)  # atomic: never serve a half-written file

    try:
        await asyncio.wait_for(run(), timeout=RENDER_TIMEOUT)
    except asyncio.TimeoutError as e:
        raise SvgExportError(f"Export timed out after {RENDER_TIMEOUT}s") from e
    finally:
        tmp_out.unlink(missing_ok=True)

    return out_path
