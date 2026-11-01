"""The two looks an Architecture diagram can have (S14b, second version): a draw.io look and a Notion look.

A style is only colours, corner radius, line weight and font weight. The layout is the same in both, so the same list gives the same picture
in either look and the person can switch between them without anything moving.

Every value is a plain colour or number from this file. Nothing a model wrote ever reaches an attribute here; text is escaped before it is placed.
"""
from __future__ import annotations

from dataclasses import dataclass

DRAWIO = "drawio"
NOTION = "notion"
STYLES = (DRAWIO, NOTION)
DEFAULT = DRAWIO


@dataclass(frozen=True)
class Style:
    key: str
    background: str
    box_fill: str
    box_stroke: str
    box_radius: int
    box_stroke_width: float
    title: str
    id_ink: str
    line: str
    line_width: float
    badge_fill: str
    badge_stroke: str
    badge_ink: str
    key_ink: str
    key_muted: str
    key_rule: str
    actor_fill: str
    actor_stroke: str
    case_fill: str
    case_stroke: str
    boundary: str
    font: str
    title_weight: str


THEMES = {
    # draw.io: white page, light-blue boxes with a darker blue outline, dark grey lines, small numbered circles
    DRAWIO: Style(
        key=DRAWIO, background="#ffffff", box_fill="#dae8fc", box_stroke="#6c8ebf", box_radius=3, box_stroke_width=1.5,
        title="#1f2937", id_ink="#4b6584", line="#4b5563", line_width=1.6,
        badge_fill="#ffffff", badge_stroke="#6c8ebf", badge_ink="#1f2937", key_ink="#1f2937", key_muted="#6b7280", key_rule="#d1d5db",
        actor_fill="#fff2cc", actor_stroke="#d6b656", case_fill="#d5e8d4", case_stroke="#82b366", boundary="#9ca3af",
        font="Helvetica, Arial, sans-serif", title_weight="normal",
    ),
    # Notion: warm off-white page, soft cards with a hairline border, light grey lines, quiet grey pills
    NOTION: Style(
        key=NOTION, background="#ffffff", box_fill="#f7f6f3", box_stroke="#e3e2de", box_radius=8, box_stroke_width=1,
        title="#37352f", id_ink="#9b9a97", line="#a8a7a3", line_width=1.4,
        badge_fill="#ebeae6", badge_stroke="#ebeae6", badge_ink="#37352f", key_ink="#37352f", key_muted="#9b9a97", key_rule="#ebeae6",
        actor_fill="#fbf3db", actor_stroke="#f1e2b6", case_fill="#ddebf1", case_stroke="#c3dbe6", boundary="#d3d1cb",
        font="Helvetica, Arial, sans-serif", title_weight="bold",
    ),
}


def style_of(name: str | None) -> Style:
    return THEMES.get(name or DEFAULT, THEMES[DEFAULT])
