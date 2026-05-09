from __future__ import annotations

import re
import textwrap
import uuid
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

from .config import Settings


def _font(size: int):
    candidates = [
        "/System/Library/Fonts/Supplemental/Arial.ttf",
        "/System/Library/Fonts/Helvetica.ttc",
    ]
    for candidate in candidates:
        if Path(candidate).exists():
            return ImageFont.truetype(candidate, size=size)
    return ImageFont.load_default()


def _bullets(markdown: str) -> list[str]:
    lines = []
    for line in markdown.splitlines():
        if re.match(r"^\s*[-*]\s+", line):
            cleaned = re.sub(r"^\s*[-*]\s+", "", line)
            cleaned = re.sub(r"\*\*", "", cleaned).strip()
            if len(cleaned) > 18:
                lines.append(cleaned)
        if len(lines) == 5:
            break
    return lines or [
        "Align interim work to the target-state architecture.",
        "Reduce migration rework through source-aligned delivery.",
        "Track cost, turnaround, ownership, and cloud consumption.",
    ]


def create_visual_summary(settings: Settings, analysis: str) -> Path:
    output_dir = settings.upload_path / "visuals"
    output_dir.mkdir(parents=True, exist_ok=True)
    path = output_dir / f"strategy-visual-{uuid.uuid4()}.png"

    width, height = 1400, 900
    image = Image.new("RGB", (width, height), "#f8fafc")
    draw = ImageDraw.Draw(image)
    title_font = _font(54)
    label_font = _font(25)
    body_font = _font(24)
    small_font = _font(19)

    draw.rounded_rectangle((60, 55, width - 60, height - 55), radius=28, fill="#ffffff", outline="#dbe3ef", width=2)
    draw.rectangle((60, 55, width - 60, 170), fill="#0f172a")
    draw.text((100, 88), "Strategy Action Map", fill="#ffffff", font=title_font)
    draw.text((102, 150), "Generated from the multi-agent analysis", fill="#cbd5e1", font=small_font)

    columns = [
        ("Objective", "#2563eb", "Clarify the outcome and measurable value."),
        ("Cost", "#059669", "Prioritize reuse, right-sizing, and staged commitments."),
        ("Turnaround", "#9333ea", "Use patterns, templates, and decision gates."),
    ]
    x = 100
    for label, color, body in columns:
        draw.rounded_rectangle((x, 220, x + 360, 410), radius=18, fill="#f8fafc", outline="#dbe3ef", width=2)
        draw.ellipse((x + 26, 246, x + 64, 284), fill=color)
        draw.text((x + 82, 246), label, fill="#0f172a", font=label_font)
        for idx, wrapped in enumerate(textwrap.wrap(body, width=31)):
            draw.text((x + 28, 315 + idx * 32), wrapped, fill="#475569", font=body_font)
        x += 420

    draw.text((100, 470), "Priority recommendations", fill="#0f172a", font=label_font)
    y = 525
    for index, bullet in enumerate(_bullets(analysis), start=1):
        draw.rounded_rectangle((100, y, width - 100, y + 58), radius=14, fill="#f8fafc", outline="#e2e8f0", width=1)
        draw.text((126, y + 15), str(index), fill="#0f172a", font=body_font)
        draw.text((170, y + 15), textwrap.shorten(bullet, width=118, placeholder="..."), fill="#334155", font=body_font)
        y += 72

    image.save(path, "PNG")
    return path
