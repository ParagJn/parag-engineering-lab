"""Render LinkedIn posts as styled, self-contained HTML documents (3 themes)."""

import html as _html
from datetime import datetime


def _esc(text: str) -> str:
    return _html.escape(str(text or ""))


def _nl2br(text: str) -> str:
    """Convert newline characters to <br> tags for HTML display."""
    return _esc(text).replace("\n", "<br>")


def render_linkedin_html(posts: list[dict], magazine_title: str, style: str) -> str:
    """Return a self-contained HTML document for the given style.

    style: "professional" | "editorial" | "dark"
    """
    if style == "editorial":
        return _render_editorial(posts, magazine_title)
    elif style == "dark":
        return _render_dark(posts, magazine_title)
    else:
        return _render_professional(posts, magazine_title)


# ─── Style 1: Professional Cards ────────────────────────────────────────────

def _render_professional(posts: list[dict], magazine_title: str) -> str:
    date_str = datetime.now().strftime("%B %d, %Y")
    cards_html = ""
    for i, item in enumerate(posts):
        post_html = _nl2br(item.get("post", ""))
        headline = _esc(item.get("headline", f"Post {i+1}"))
        cards_html += f"""
  <div class="card">
    <div class="card-header">
      <span class="num">{str(i + 1).zfill(2)}</span>
      <h2 class="headline">{headline}</h2>
    </div>
    <div class="post-body">{post_html}</div>
    <div class="card-footer">
      <span class="platform-badge">
        <svg width="14" height="14" viewBox="0 0 24 24" fill="currentColor">
          <path d="M16 8a6 6 0 016 6v7h-4v-7a2 2 0 00-2-2 2 2 0 00-2 2v7h-4v-7a6 6 0 016-6zM2 9h4v12H2z"/>
          <circle cx="4" cy="4" r="2"/>
        </svg>
        LinkedIn
      </span>
      <span class="story-ref">Story {i + 1} of {len(posts)}</span>
    </div>
  </div>"""

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>{_esc(magazine_title)} — LinkedIn Posts</title>
<link rel="preconnect" href="https://fonts.googleapis.com">
<link href="https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700;800&display=swap" rel="stylesheet">
<style>
  *, *::before, *::after {{ box-sizing: border-box; margin: 0; padding: 0; }}
  body {{
    font-family: 'Inter', sans-serif;
    background: #f3f4f6;
    color: #1f2937;
    padding: 2.5rem 1.5rem;
  }}
  .page-header {{
    text-align: center;
    margin-bottom: 2.5rem;
  }}
  .page-header .brand {{
    display: inline-flex;
    align-items: center;
    gap: 0.5rem;
    background: #0a66c2;
    color: #fff;
    font-size: 0.75rem;
    font-weight: 700;
    letter-spacing: 0.1em;
    text-transform: uppercase;
    padding: 0.4rem 1rem;
    border-radius: 999px;
    margin-bottom: 1rem;
  }}
  .page-header h1 {{
    font-size: 1.8rem;
    font-weight: 800;
    color: #111827;
    margin-bottom: 0.4rem;
  }}
  .page-header .meta {{
    color: #6b7280;
    font-size: 0.85rem;
  }}
  .grid {{
    display: grid;
    grid-template-columns: repeat(auto-fill, minmax(480px, 1fr));
    gap: 1.5rem;
    max-width: 1200px;
    margin: 0 auto;
  }}
  .card {{
    background: #fff;
    border-radius: 16px;
    border: 1px solid #e5e7eb;
    overflow: hidden;
    box-shadow: 0 2px 8px rgba(0,0,0,0.06);
    display: flex;
    flex-direction: column;
  }}
  .card-header {{
    display: flex;
    align-items: flex-start;
    gap: 0.875rem;
    padding: 1.25rem 1.5rem 1rem;
    border-bottom: 1px solid #f3f4f6;
    background: #fafafa;
  }}
  .num {{
    font-size: 1.5rem;
    font-weight: 800;
    color: #0a66c2;
    line-height: 1;
    min-width: 2.25rem;
  }}
  .headline {{
    font-size: 0.95rem;
    font-weight: 700;
    color: #111827;
    line-height: 1.4;
  }}
  .post-body {{
    padding: 1.25rem 1.5rem;
    font-size: 0.875rem;
    line-height: 1.75;
    color: #374151;
    white-space: pre-wrap;
    flex: 1;
  }}
  .card-footer {{
    display: flex;
    align-items: center;
    justify-content: space-between;
    padding: 0.875rem 1.5rem;
    border-top: 1px solid #f3f4f6;
    background: #fafafa;
  }}
  .platform-badge {{
    display: inline-flex;
    align-items: center;
    gap: 0.375rem;
    color: #0a66c2;
    font-size: 0.75rem;
    font-weight: 600;
  }}
  .story-ref {{
    color: #9ca3af;
    font-size: 0.75rem;
  }}
  @media print {{
    body {{ background: #fff; padding: 0; }}
    .card {{ page-break-inside: avoid; break-inside: avoid; box-shadow: none; border: 1px solid #d1d5db; }}
    .grid {{ grid-template-columns: 1fr 1fr; gap: 1rem; }}
  }}
</style>
</head>
<body>
  <div class="page-header">
    <div class="brand">
      <svg width="14" height="14" viewBox="0 0 24 24" fill="currentColor">
        <path d="M16 8a6 6 0 016 6v7h-4v-7a2 2 0 00-2-2 2 2 0 00-2 2v7h-4v-7a6 6 0 016-6zM2 9h4v12H2z"/><circle cx="4" cy="4" r="2"/>
      </svg>
      LinkedIn Posts
    </div>
    <h1>{_esc(magazine_title)}</h1>
    <p class="meta">{len(posts)} posts · {date_str} · Morning Edition</p>
  </div>
  <div class="grid">
    {cards_html}
  </div>
</body>
</html>"""


# ─── Style 2: Editorial Digest ───────────────────────────────────────────────

def _render_editorial(posts: list[dict], magazine_title: str) -> str:
    date_str = datetime.now().strftime("%A, %B %d, %Y").upper()
    items_html = ""
    for i, item in enumerate(posts):
        post_html = _nl2br(item.get("post", ""))
        headline = _esc(item.get("headline", f"Post {i+1}"))
        roman = ["I","II","III","IV","V","VI","VII","VIII","IX","X"]
        numeral = roman[i] if i < len(roman) else str(i + 1)
        items_html += f"""
  <article class="story">
    <div class="story-numeral">{numeral}</div>
    <div class="story-content">
      <h2 class="story-headline">{headline}</h2>
      <div class="divider"></div>
      <div class="post-body">{post_html}</div>
    </div>
  </article>"""

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>{_esc(magazine_title)} — LinkedIn Posts</title>
<link rel="preconnect" href="https://fonts.googleapis.com">
<link href="https://fonts.googleapis.com/css2?family=Fraunces:ital,opsz,wght@0,9..144,400;0,9..144,700;0,9..144,900;1,9..144,400&family=Inter:wght@400;500;600&display=swap" rel="stylesheet">
<style>
  *, *::before, *::after {{ box-sizing: border-box; margin: 0; padding: 0; }}
  body {{
    font-family: 'Inter', sans-serif;
    background: #faf9f6;
    color: #1a1a1a;
    padding: 0;
  }}
  .masthead {{
    background: #1a1a1a;
    color: #fff;
    text-align: center;
    padding: 3rem 2rem 2.5rem;
    border-bottom: 4px solid #c9a84c;
  }}
  .masthead .edition-label {{
    font-size: 0.65rem;
    letter-spacing: 0.25em;
    text-transform: uppercase;
    color: #c9a84c;
    margin-bottom: 0.75rem;
  }}
  .masthead h1 {{
    font-family: 'Fraunces', serif;
    font-size: clamp(2rem, 5vw, 3.5rem);
    font-weight: 900;
    line-height: 1.1;
    margin-bottom: 0.5rem;
  }}
  .masthead .dateline {{
    font-size: 0.75rem;
    letter-spacing: 0.15em;
    color: #9ca3af;
    margin-top: 0.75rem;
  }}
  .masthead .li-badge {{
    display: inline-flex;
    align-items: center;
    gap: 0.4rem;
    background: #0a66c2;
    color: #fff;
    font-size: 0.7rem;
    font-weight: 700;
    letter-spacing: 0.08em;
    padding: 0.3rem 0.8rem;
    border-radius: 4px;
    margin-top: 1rem;
  }}
  .container {{
    max-width: 800px;
    margin: 0 auto;
    padding: 2.5rem 2rem;
  }}
  .story {{
    display: grid;
    grid-template-columns: 3.5rem 1fr;
    gap: 1.5rem;
    padding: 2rem 0;
    border-bottom: 1px solid #e5e0d8;
  }}
  .story:last-child {{ border-bottom: none; }}
  .story-numeral {{
    font-family: 'Fraunces', serif;
    font-size: 2.5rem;
    font-weight: 900;
    color: #c9a84c;
    line-height: 1;
    padding-top: 0.25rem;
    text-align: right;
  }}
  .story-headline {{
    font-family: 'Fraunces', serif;
    font-size: 1.3rem;
    font-weight: 700;
    color: #111;
    line-height: 1.3;
    margin-bottom: 0.75rem;
  }}
  .divider {{
    width: 2.5rem;
    height: 3px;
    background: #c9a84c;
    margin-bottom: 1rem;
  }}
  .post-body {{
    font-size: 0.9rem;
    line-height: 1.8;
    color: #374151;
    white-space: pre-wrap;
  }}
  @media print {{
    body {{ background: #fff; }}
    .story {{ page-break-inside: avoid; break-inside: avoid; }}
  }}
</style>
</head>
<body>
  <div class="masthead">
    <p class="edition-label">Morning Edition · LinkedIn Digest</p>
    <h1>{_esc(magazine_title)}</h1>
    <div class="li-badge">
      <svg width="12" height="12" viewBox="0 0 24 24" fill="currentColor">
        <path d="M16 8a6 6 0 016 6v7h-4v-7a2 2 0 00-2-2 2 2 0 00-2 2v7h-4v-7a6 6 0 016-6zM2 9h4v12H2z"/><circle cx="4" cy="4" r="2"/>
      </svg>
      {len(posts)} LinkedIn Posts Ready
    </div>
    <p class="dateline">{date_str}</p>
  </div>
  <div class="container">
    {items_html}
  </div>
</body>
</html>"""


# ─── Style 3: Dark Compact ───────────────────────────────────────────────────

def _render_dark(posts: list[dict], magazine_title: str) -> str:
    date_str = datetime.now().strftime("%Y-%m-%d")
    items_html = ""
    for i, item in enumerate(posts):
        post_html = _nl2br(item.get("post", ""))
        headline = _esc(item.get("headline", f"Post {i+1}"))
        items_html += f"""
  <div class="card">
    <div class="card-top">
      <span class="idx">[{str(i + 1).zfill(2)}]</span>
      <span class="headline">{headline}</span>
    </div>
    <div class="post-body">{post_html}</div>
  </div>"""

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>{_esc(magazine_title)} — LinkedIn Posts</title>
<link rel="preconnect" href="https://fonts.googleapis.com">
<link href="https://fonts.googleapis.com/css2?family=JetBrains+Mono:wght@400;700&family=Inter:wght@400;500;700&display=swap" rel="stylesheet">
<style>
  *, *::before, *::after {{ box-sizing: border-box; margin: 0; padding: 0; }}
  body {{
    font-family: 'Inter', sans-serif;
    background: #0d1117;
    color: #c9d1d9;
    padding: 2rem 1.5rem;
    min-height: 100vh;
  }}
  .header {{
    max-width: 720px;
    margin: 0 auto 2rem;
    padding-bottom: 1.25rem;
    border-bottom: 1px solid #30363d;
  }}
  .header .top-line {{
    display: flex;
    align-items: center;
    gap: 0.75rem;
    margin-bottom: 0.5rem;
  }}
  .header .tag {{
    font-family: 'JetBrains Mono', monospace;
    font-size: 0.7rem;
    color: #2dd4bf;
    background: rgba(45,212,191,0.1);
    border: 1px solid rgba(45,212,191,0.25);
    padding: 0.2rem 0.6rem;
    border-radius: 4px;
    letter-spacing: 0.05em;
  }}
  .header .li-tag {{
    font-family: 'JetBrains Mono', monospace;
    font-size: 0.7rem;
    color: #58a6ff;
    background: rgba(88,166,255,0.08);
    border: 1px solid rgba(88,166,255,0.2);
    padding: 0.2rem 0.6rem;
    border-radius: 4px;
    letter-spacing: 0.05em;
  }}
  .header h1 {{
    font-size: 1.4rem;
    font-weight: 700;
    color: #f0f6fc;
    line-height: 1.3;
  }}
  .header .meta {{
    font-family: 'JetBrains Mono', monospace;
    font-size: 0.72rem;
    color: #8b949e;
    margin-top: 0.5rem;
  }}
  .list {{
    max-width: 720px;
    margin: 0 auto;
    display: flex;
    flex-direction: column;
    gap: 1px;
  }}
  .card {{
    background: #161b22;
    border: 1px solid #30363d;
    border-radius: 8px;
    overflow: hidden;
    margin-bottom: 1rem;
  }}
  .card-top {{
    display: flex;
    align-items: flex-start;
    gap: 0.875rem;
    padding: 0.875rem 1.25rem;
    background: #1c2128;
    border-bottom: 1px solid #30363d;
  }}
  .idx {{
    font-family: 'JetBrains Mono', monospace;
    font-size: 0.8rem;
    color: #2dd4bf;
    font-weight: 700;
    white-space: nowrap;
    padding-top: 0.1rem;
  }}
  .headline {{
    font-size: 0.9rem;
    font-weight: 600;
    color: #f0f6fc;
    line-height: 1.45;
  }}
  .post-body {{
    padding: 1rem 1.25rem;
    font-size: 0.83rem;
    line-height: 1.75;
    color: #c9d1d9;
    white-space: pre-wrap;
  }}
  @media print {{
    body {{ background: #0d1117 !important; -webkit-print-color-adjust: exact; print-color-adjust: exact; }}
    .card {{ page-break-inside: avoid; break-inside: avoid; }}
  }}
</style>
</head>
<body>
  <div class="header">
    <div class="top-line">
      <span class="tag">morning-edition</span>
      <span class="li-tag">linkedin-posts · {len(posts)}</span>
    </div>
    <h1>{_esc(magazine_title)}</h1>
    <p class="meta">// generated {date_str} · copy-paste ready</p>
  </div>
  <div class="list">
    {items_html}
  </div>
</body>
</html>"""
