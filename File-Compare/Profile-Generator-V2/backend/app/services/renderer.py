from __future__ import annotations

from datetime import datetime
from html import escape

import markdown


def render_markdown_cv(profile: dict, ats_report: dict, target_role: str = "", target_company: str = "") -> str:
    skills = profile.get("core_skills", [])
    exp = profile.get("experience_highlights", [])
    proj = profile.get("project_highlights", [])

    lines = [
        f"# {profile.get('name', 'Candidate')}",
        "",
        f"**{profile.get('title', '') or target_role}**",
        "",
        "## Contact",
        f"- Email: {profile.get('email', '')}",
        f"- Phone: {profile.get('phone', '')}",
        f"- LinkedIn: {profile.get('linkedin', '')}",
        f"- GitHub: {profile.get('github', '')}",
        f"- Website: {profile.get('website', '')}",
        "",
        "## Professional Summary",
        profile.get("summary", ""),
        "",
        "## Core Skills",
        ", ".join(skills) if skills else "N/A",
        "",
        "## Experience Highlights",
    ]

    if exp:
        lines.extend([f"- {item}" for item in exp])
    else:
        lines.append("- N/A")

    lines.extend(["", "## Project Highlights"])
    if proj:
        lines.extend([f"- {item}" for item in proj])
    else:
        lines.append("- N/A")

    lines.extend(
        [
            "",
            "## Education",
            profile.get("education_notes", "N/A") or "N/A",
            "",
            "## Certifications",
            profile.get("certification_notes", "N/A") or "N/A",
            "",
            "## ATS Optimization Report",
            f"- ATS Score: {ats_report.get('score', 0)} / 100",
            f"- Matched Keywords: {', '.join(ats_report.get('matched_keywords', []))}",
            f"- Missing Keywords: {', '.join(ats_report.get('missing_keywords', []))}",
            f"- Recommendations: {', '.join(ats_report.get('section_tips', []))}",
            "",
            f"_Generated on {datetime.utcnow().strftime('%Y-%m-%d %H:%M UTC')}_",
        ]
    )

    if target_company:
        lines.insert(4, f"- Target Company: {target_company}")

    return "\n".join(lines)


def render_html_cv(markdown_cv: str, profile: dict, ats_report: dict) -> str:
    body_html = markdown.markdown(markdown_cv)
    skill_tags = "".join(
        f"<span class='skill-chip'>{escape(skill)}</span>" for skill in profile.get("core_skills", [])[:24]
    )

    score = ats_report.get("score", 0)
    score_color = "#15803d" if score >= 80 else "#b45309" if score >= 60 else "#b91c1c"

    return f"""<!DOCTYPE html>
<html lang=\"en\">
<head>
  <meta charset=\"UTF-8\" />
  <meta name=\"viewport\" content=\"width=device-width, initial-scale=1.0\" />
  <title>{escape(profile.get('name', 'Candidate'))} - CV</title>
  <style>
    :root {{
      --bg1: #f2f7fb;
      --bg2: #d8e9f8;
      --text: #10243a;
      --primary: #0d4a8f;
      --accent: #0c8f8a;
      --card: #ffffff;
      --muted: #4f6b87;
      --line: #d6e4f2;
    }}
    * {{ box-sizing: border-box; }}
    body {{
      margin: 0;
      font-family: "Segoe UI", "SF Pro Text", -apple-system, BlinkMacSystemFont, sans-serif;
      color: var(--text);
      background:
        radial-gradient(circle at 10% 0%, rgba(12, 143, 138, 0.12), transparent 35%),
        radial-gradient(circle at 85% 0%, rgba(13, 74, 143, 0.16), transparent 35%),
        linear-gradient(180deg, var(--bg1), #eef6fc 38%, #f9fbfd 100%);
      min-height: 100vh;
      line-height: 1.6;
    }}
    .container {{ max-width: 1100px; margin: 0 auto; padding: 24px 18px 64px; }}
    .hero {{
      background: linear-gradient(135deg, #0d4a8f, #0f6aa8 48%, #0c8f8a);
      color: #fff;
      border-radius: 24px;
      padding: 28px;
      box-shadow: 0 18px 40px rgba(13, 74, 143, 0.24);
      position: relative;
      overflow: hidden;
    }}
    .hero::after {{
      content: "";
      position: absolute;
      width: 240px;
      height: 240px;
      right: -60px;
      top: -90px;
      border-radius: 50%;
      background: rgba(255, 255, 255, 0.18);
    }}
    .hero h1 {{ margin: 0; font-size: clamp(1.8rem, 4vw, 2.9rem); letter-spacing: 0.2px; }}
    .hero p {{ margin: 8px 0 0; font-size: clamp(1rem, 2.8vw, 1.2rem); opacity: 0.96; }}
    .meta {{ margin-top: 16px; display: flex; flex-wrap: wrap; gap: 8px; }}
    .meta span {{
      border: 1px solid rgba(255, 255, 255, 0.3);
      background: rgba(255, 255, 255, 0.12);
      border-radius: 999px;
      padding: 6px 12px;
      font-size: 0.86rem;
    }}
    .grid {{
      margin-top: 20px;
      display: grid;
      grid-template-columns: 2fr 1fr;
      gap: 18px;
    }}
    .card {{
      background: var(--card);
      border: 1px solid var(--line);
      border-radius: 18px;
      padding: 18px;
      box-shadow: 0 8px 22px rgba(17, 38, 62, 0.08);
    }}
    .section-title {{ margin: 0 0 10px; color: var(--primary); font-size: 1.05rem; letter-spacing: 0.25px; }}
    .skills {{ display: flex; flex-wrap: wrap; gap: 8px; margin-top: 8px; }}
    .skill-chip {{
      display: inline-flex;
      align-items: center;
      border: 1px solid #b9d4ea;
      background: #edf5fc;
      color: #103b63;
      border-radius: 999px;
      padding: 6px 12px;
      font-size: 0.82rem;
      font-weight: 600;
    }}
    .ats-score {{
      font-size: 2rem;
      margin: 4px 0 0;
      color: {score_color};
      font-weight: 800;
    }}
    .kv-list {{ margin: 0; padding-left: 18px; }}
    .kv-list li {{ margin: 6px 0; }}
    article h1, article h2, article h3 {{ color: var(--primary); }}
    article h1 {{ font-size: 1.4rem; margin-top: 0; }}
    article h2 {{ font-size: 1.12rem; margin-top: 22px; }}
    article ul {{ padding-left: 20px; }}
    .aside-note {{ color: var(--muted); font-size: 0.9rem; margin-top: 10px; }}

    @media (max-width: 920px) {{
      .grid {{ grid-template-columns: 1fr; }}
    }}
    @media (max-width: 640px) {{
      .container {{ padding: 14px 12px 28px; }}
      .hero {{ padding: 20px; border-radius: 18px; }}
      .card {{ padding: 14px; border-radius: 14px; }}
      .meta span {{ font-size: 0.78rem; }}
    }}

    @media print {{
      body {{ background: white !important; }}
      .container {{ max-width: none; padding: 0; }}
      .hero {{ box-shadow: none; border-radius: 0; }}
      .grid {{ grid-template-columns: 2fr 1fr; gap: 10px; }}
      .card {{ box-shadow: none; border: 1px solid #c7d7e8; }}
      a {{ color: inherit; text-decoration: none; }}
      @page {{ size: A4; margin: 12mm; }}
    }}
  </style>
</head>
<body>
  <div class=\"container\">
    <section class=\"hero\">
      <h1>{escape(profile.get('name', 'Candidate'))}</h1>
      <p>{escape(profile.get('title', 'Professional Profile'))}</p>
      <div class=\"meta\">
        {f"<span>{escape(profile.get('email', ''))}</span>" if profile.get('email') else ""}
        {f"<span>{escape(profile.get('phone', ''))}</span>" if profile.get('phone') else ""}
        {f"<span>{escape(profile.get('linkedin', ''))}</span>" if profile.get('linkedin') else ""}
        {f"<span>{escape(profile.get('github', ''))}</span>" if profile.get('github') else ""}
      </div>
    </section>

    <section class=\"grid\">
      <article class=\"card\">{body_html}</article>
      <aside class=\"card\">
        <h3 class=\"section-title\">ATS Readiness</h3>
        <p class=\"ats-score\">{score}/100</p>
        <p class=\"aside-note\">Keyword alignment and role relevance score.</p>

        <h4 class=\"section-title\" style=\"margin-top:16px;\">Top Skills</h4>
        <div class=\"skills\">{skill_tags}</div>

        <h4 class=\"section-title\" style=\"margin-top:16px;\">Missing Keywords</h4>
        <ul class=\"kv-list\">
          {''.join(f"<li>{escape(k)}</li>" for k in ats_report.get('missing_keywords', [])[:10]) or '<li>None</li>'}
        </ul>

        <h4 class=\"section-title\" style=\"margin-top:16px;\">Improvement Tips</h4>
        <ul class=\"kv-list\">
          {''.join(f"<li>{escape(t)}</li>" for t in ats_report.get('section_tips', [])[:5])}
        </ul>
      </aside>
    </section>
  </div>
</body>
</html>
"""
