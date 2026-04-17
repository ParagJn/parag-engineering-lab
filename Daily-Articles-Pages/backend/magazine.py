"""Generate self-contained magazine HTML from curated content."""

import json
from datetime import datetime


def generate_magazine_html(magazine_data: dict, source_name: str) -> str:
    """Generate a complete self-contained HTML magazine."""

    title = magazine_data.get("magazine_title", "Morning Edition")
    tagline = magazine_data.get("edition_tagline", "Your daily tech briefing")
    seo_desc = magazine_data.get("seo_description", f"{title} — {tagline}. AI-curated tech news from {source_name}.")
    seo_keywords = magazine_data.get("seo_keywords", "tech news, AI, software engineering, developer tools, cybersecurity")
    stories = magazine_data.get("stories", [])
    now = datetime.now()
    date_str = now.strftime("%A, %B %d, %Y")
    iso_date = now.strftime("%Y-%m-%dT%H:%M:%S")

    spreads_html = ""
    for i, story in enumerate(stories):
        spreads_html += _render_spread(story, i)

    # Build Table of Contents
    toc_items = ""
    for i, story in enumerate(stories):
        cat = _esc(story.get("category_label", "TECH"))
        headline = _esc(story.get("headline", "Untitled"))
        numeral = _esc(story.get("numeral", f"{i+1:02d}"))
        style = story.get("spread_style", "editorial")
        style_colors = {
            "hero": "#6366f1", "midnight": "#818cf8", "rose_alert": "#e11d48",
            "terminal": "#4ade80", "academic": "#a16207", "big_stat": "#818cf8",
            "blueprint": "#2563eb", "neon": "#e879f9", "editorial": "#dc2626",
            "sunset": "#92400e",
        }
        accent = style_colors.get(style, "#6366f1")
        toc_items += f"""
      <a href="#story-{i}" class="toc-item">
        <span class="toc-numeral" style="color:{accent}">{numeral}</span>
        <span class="toc-text">
          <span class="toc-cat">{cat}</span>
          <span class="toc-headline">{headline}</span>
        </span>
        <span class="toc-arrow">→</span>
      </a>"""

    # Build JSON-LD structured data
    article_entries = []
    for i, story in enumerate(stories):
        article_entries.append({
            "@type": "Article",
            "headline": story.get("headline", "Untitled"),
            "description": story.get("deck", ""),
            "url": story.get("original_url", ""),
            "articleSection": story.get("category_label", "Technology"),
            "position": i + 1,
        })

    jsonld = json.dumps({
        "@context": "https://schema.org",
        "@type": "CollectionPage",
        "name": title,
        "description": seo_desc,
        "datePublished": iso_date,
        "dateModified": iso_date,
        "publisher": {
            "@type": "Organization",
            "name": "Morning Edition",
        },
        "about": {
            "@type": "Thing",
            "name": "Technology News"
        },
        "hasPart": article_entries,
    }, ensure_ascii=False)

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>{_esc(title)} — {date_str}</title>

<!-- SEO Meta -->
<meta name="description" content="{_esc_attr(seo_desc)}">
<meta name="keywords" content="{_esc_attr(seo_keywords)}">
<meta name="author" content="Morning Edition — AI Curated">
<meta name="robots" content="index, follow, max-snippet:-1, max-image-preview:large">
<meta name="generator" content="Morning Edition AI Magazine Generator">
<link rel="canonical" href="">

<!-- Open Graph / Facebook -->
<meta property="og:type" content="article">
<meta property="og:title" content="{_esc_attr(title)} — {date_str}">
<meta property="og:description" content="{_esc_attr(seo_desc)}">
<meta property="og:site_name" content="Morning Edition">
<meta property="og:locale" content="en_US">
<meta property="article:published_time" content="{iso_date}">
<meta property="article:section" content="Technology">
<meta property="article:tag" content="{_esc_attr(seo_keywords)}">

<!-- Twitter Card -->
<meta name="twitter:card" content="summary_large_image">
<meta name="twitter:title" content="{_esc_attr(title)} — {date_str}">
<meta name="twitter:description" content="{_esc_attr(seo_desc)}">

<!-- JSON-LD Structured Data -->
<script type="application/ld+json">
{jsonld}
</script>
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link href="https://fonts.googleapis.com/css2?family=Fraunces:ital,opsz,wght@0,9..144,100..900;1,9..144,100..900&family=Inter:wght@300;400;500;600;700;800;900&family=JetBrains+Mono:wght@400;700&display=swap" rel="stylesheet">
<style>
* {{ margin: 0; padding: 0; box-sizing: border-box; }}
html {{ scroll-behavior: smooth; font-size: 18px; }}
body {{ font-family: 'Inter', sans-serif; overflow-x: hidden; }}

.cover {{
  min-height: 100vh;
  display: flex;
  flex-direction: column;
  justify-content: center;
  align-items: center;
  background: #0a0a0a;
  color: #fff;
  text-align: center;
  padding: 4rem 2rem;
  position: relative;
  overflow: hidden;
}}
.cover::before {{
  content: '';
  position: absolute;
  top: -50%;
  left: -50%;
  width: 200%;
  height: 200%;
  background: radial-gradient(circle at 30% 40%, rgba(99,102,241,0.15), transparent 50%),
              radial-gradient(circle at 70% 60%, rgba(244,63,94,0.1), transparent 50%);
  animation: drift 20s ease-in-out infinite;
}}
@keyframes drift {{
  0%, 100% {{ transform: translate(0, 0) rotate(0deg); }}
  50% {{ transform: translate(2%, -2%) rotate(1deg); }}
}}
.cover-content {{ position: relative; z-index: 1; max-width: 900px; }}
.cover h1 {{
  font-family: 'Fraunces', serif;
  font-size: clamp(3rem, 8vw, 7rem);
  font-weight: 900;
  line-height: 1.05;
  letter-spacing: -0.03em;
  margin-bottom: 1rem;
}}
.cover .tagline {{
  font-size: clamp(1.2rem, 2.5vw, 1.8rem);
  opacity: 0.7;
  font-weight: 300;
  margin-bottom: 2rem;
}}
.cover .meta {{
  font-size: 1rem;
  opacity: 0.5;
  text-transform: uppercase;
  letter-spacing: 0.2em;
}}
.cover .source-badge {{
  display: inline-block;
  margin-top: 1.5rem;
  padding: 0.5rem 1.5rem;
  border: 1px solid rgba(255,255,255,0.3);
  border-radius: 100px;
  font-size: 0.9rem;
  letter-spacing: 0.1em;
  text-transform: uppercase;
}}

/* === SPREAD BASE === */
.spread {{
  min-height: 100vh;
  display: flex;
  flex-direction: column;
  justify-content: center;
  padding: 6rem 2rem;
  position: relative;
}}
.spread-inner {{
  max-width: 900px;
  margin: 0 auto;
  width: 100%;
}}
.category-label {{
  font-size: 0.85rem;
  font-weight: 700;
  text-transform: uppercase;
  letter-spacing: 0.25em;
  margin-bottom: 1.5rem;
}}
.numeral {{
  font-family: 'Fraunces', serif;
  font-size: clamp(4rem, 10vw, 8rem);
  font-weight: 900;
  opacity: 0.12;
  position: absolute;
  top: 2rem;
  right: 3rem;
  line-height: 1;
}}
.headline {{
  font-family: 'Fraunces', serif;
  font-size: clamp(2.2rem, 5vw, 4rem);
  font-weight: 800;
  line-height: 1.1;
  letter-spacing: -0.02em;
  margin-bottom: 0.8rem;
}}
.deck {{
  font-size: clamp(1.1rem, 2vw, 1.4rem);
  font-weight: 300;
  opacity: 0.75;
  margin-bottom: 2.5rem;
  line-height: 1.4;
}}
.body p {{
  font-size: clamp(1.05rem, 1.5vw, 1.2rem);
  line-height: 1.8;
  margin-bottom: 1.2rem;
}}
.pull-quote {{
  font-family: 'Fraunces', serif;
  font-size: clamp(1.4rem, 3vw, 2rem);
  font-style: italic;
  font-weight: 400;
  line-height: 1.4;
  padding: 2rem 0;
  margin: 2rem 0;
  border-top: 3px solid currentColor;
  border-bottom: 1px solid currentColor;
  opacity: 0.9;
}}
.read-more {{
  display: inline-block;
  margin-top: 1.5rem;
  font-weight: 600;
  font-size: 0.95rem;
  text-decoration: none;
  text-transform: uppercase;
  letter-spacing: 0.15em;
  padding: 0.7rem 1.5rem;
  border: 2px solid currentColor;
  transition: all 0.3s;
}}
.read-more:hover {{ opacity: 0.7; }}
.flag-badge {{
  display: inline-block;
  padding: 0.3rem 0.8rem;
  background: #f43f5e;
  color: white;
  font-size: 0.75rem;
  font-weight: 700;
  text-transform: uppercase;
  letter-spacing: 0.15em;
  border-radius: 3px;
  margin-bottom: 1rem;
  animation: pulse 2s ease-in-out infinite;
}}
@keyframes pulse {{
  0%, 100% {{ opacity: 1; }}
  50% {{ opacity: 0.7; }}
}}

/* === SPREAD STYLES === */
.spread-hero {{
  background: #fafaf9;
  color: #1a1a1a;
}}
.spread-hero .category-label {{ color: #6366f1; }}
.spread-hero .read-more {{ color: #1a1a1a; }}

.spread-midnight {{
  background: #0f172a;
  color: #e2e8f0;
}}
.spread-midnight .category-label {{ color: #818cf8; }}
.spread-midnight .numeral {{ color: #334155; opacity: 0.3; }}
.spread-midnight .read-more {{ color: #e2e8f0; }}

.spread-rose_alert {{
  background: #fff1f2;
  color: #1a1a1a;
  border-left: 8px solid #f43f5e;
}}
.spread-rose_alert .category-label {{ color: #e11d48; }}
.spread-rose_alert .pull-quote {{ border-color: #f43f5e; }}
.spread-rose_alert .numeral {{ color: #f43f5e; opacity: 0.15; }}
.spread-rose_alert .read-more {{ color: #e11d48; }}

.spread-terminal {{
  background: #0a0a0a;
  color: #4ade80;
  font-family: 'JetBrains Mono', monospace;
}}
.spread-terminal .headline {{
  font-family: 'JetBrains Mono', monospace;
  font-size: clamp(1.8rem, 4vw, 3rem);
}}
.spread-terminal .headline::before {{ content: '> '; opacity: 0.5; }}
.spread-terminal .body p {{ font-family: 'JetBrains Mono', monospace; font-size: 1rem; }}
.spread-terminal .pull-quote {{ border-color: #4ade80; font-family: 'JetBrains Mono', monospace; }}
.spread-terminal .category-label {{ color: #22d3ee; }}
.spread-terminal .numeral {{ color: #4ade80; }}
.spread-terminal .read-more {{ color: #4ade80; }}

.spread-academic {{
  background: #fef9ef;
  color: #292524;
}}
.spread-academic .body p:first-child::first-letter {{
  font-family: 'Fraunces', serif;
  font-size: 4.5rem;
  font-weight: 900;
  float: left;
  line-height: 0.8;
  margin-right: 0.5rem;
  margin-top: 0.1rem;
  color: #78716c;
}}
.spread-academic .category-label {{ color: #a16207; }}
.spread-academic .pull-quote {{ border-color: #d6d3d1; font-style: italic; }}
.spread-academic .read-more {{ color: #292524; }}

.spread-big_stat {{
  background: #1e1b4b;
  color: #e0e7ff;
  text-align: center;
}}
.spread-big_stat .spread-inner {{ text-align: center; }}
.spread-big_stat .headline {{ font-size: clamp(2.5rem, 6vw, 5rem); }}
.spread-big_stat .pull-quote {{
  font-size: clamp(3rem, 8vw, 6rem);
  font-weight: 900;
  font-style: normal;
  border: none;
  color: #a5b4fc;
}}
.spread-big_stat .body p {{ text-align: left; max-width: 700px; margin-left: auto; margin-right: auto; }}
.spread-big_stat .category-label {{ color: #818cf8; }}
.spread-big_stat .numeral {{ color: #312e81; opacity: 0.4; }}
.spread-big_stat .read-more {{ color: #e0e7ff; }}

.spread-blueprint {{
  background: #eff6ff;
  color: #1e3a5f;
  border: 2px dashed #93c5fd;
}}
.spread-blueprint .headline {{ color: #1e40af; }}
.spread-blueprint .category-label {{ color: #2563eb; }}
.spread-blueprint .pull-quote {{ border-color: #93c5fd; }}
.spread-blueprint .numeral {{ color: #3b82f6; opacity: 0.15; }}
.spread-blueprint .read-more {{ color: #1e40af; }}

.spread-neon {{
  background: #18181b;
  color: #fafafa;
}}
.spread-neon .headline {{ color: #f0abfc; text-shadow: 0 0 40px rgba(240,171,252,0.3); }}
.spread-neon .category-label {{ color: #22d3ee; text-shadow: 0 0 20px rgba(34,211,238,0.4); }}
.spread-neon .pull-quote {{ border-color: #a855f7; color: #e879f9; }}
.spread-neon .numeral {{ color: #a855f7; opacity: 0.25; }}
.spread-neon .read-more {{ color: #e879f9; }}

.spread-editorial {{
  background: #ffffff;
  color: #171717;
}}
.spread-editorial .pull-quote {{
  font-size: clamp(1.8rem, 4vw, 2.8rem);
  padding: 3rem 0;
  text-align: center;
}}
.spread-editorial .category-label {{ color: #dc2626; }}
.spread-editorial .read-more {{ color: #171717; }}

.spread-sunset {{
  background: linear-gradient(135deg, #fef3c7, #fde68a, #fbbf24, #f59e0b);
  color: #451a03;
}}
.spread-sunset .headline {{ color: #78350f; }}
.spread-sunset .category-label {{ color: #92400e; }}
.spread-sunset .pull-quote {{ border-color: #d97706; }}
.spread-sunset .numeral {{ color: #f59e0b; opacity: 0.2; }}
.spread-sunset .read-more {{ color: #78350f; }}

/* Footer */
.footer {{
  background: #0a0a0a;
  color: #737373;
  text-align: center;
  padding: 4rem 2rem;
  font-size: 0.9rem;
}}
.footer .logo {{ font-family: 'Fraunces', serif; font-size: 1.5rem; color: #fff; margin-bottom: 0.5rem; }}

/* === TABLE OF CONTENTS === */
.toc {{
  background: #fafaf9;
  padding: 5rem 2rem;
  position: relative;
}}
.toc-inner {{
  max-width: 800px;
  margin: 0 auto;
}}
.toc-heading {{
  font-family: 'Fraunces', serif;
  font-size: 1.2rem;
  font-weight: 700;
  text-transform: uppercase;
  letter-spacing: 0.25em;
  color: #a8a29e;
  margin-bottom: 2.5rem;
  padding-bottom: 1rem;
  border-bottom: 2px solid #e7e5e4;
}}
.toc-item {{
  display: flex;
  align-items: center;
  gap: 1.2rem;
  padding: 1rem 0;
  border-bottom: 1px solid #f5f5f4;
  text-decoration: none;
  color: inherit;
  transition: all 0.2s;
}}
.toc-item:hover {{
  padding-left: 0.5rem;
  background: #f5f5f4;
  border-radius: 0.5rem;
}}
.toc-numeral {{
  font-family: 'Fraunces', serif;
  font-size: 1.6rem;
  font-weight: 900;
  min-width: 3rem;
  text-align: center;
  opacity: 0.7;
}}
.toc-text {{
  flex: 1;
  min-width: 0;
}}
.toc-cat {{
  display: block;
  font-size: 0.7rem;
  font-weight: 700;
  text-transform: uppercase;
  letter-spacing: 0.2em;
  color: #a8a29e;
  margin-bottom: 0.2rem;
}}
.toc-headline {{
  display: block;
  font-family: 'Fraunces', serif;
  font-size: 1.15rem;
  font-weight: 700;
  color: #1c1917;
  line-height: 1.3;
}}
.toc-arrow {{
  font-size: 1.2rem;
  color: #d6d3d1;
  transition: transform 0.2s, color 0.2s;
}}
.toc-item:hover .toc-arrow {{
  transform: translateX(4px);
  color: #6366f1;
}}

/* === BACK TO TOP === */
.back-to-top {{
  position: fixed;
  bottom: 2rem;
  right: 2rem;
  width: 48px;
  height: 48px;
  border-radius: 50%;
  background: #0a0a0a;
  color: #fff;
  border: none;
  cursor: pointer;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 1.4rem;
  box-shadow: 0 4px 20px rgba(0,0,0,0.2);
  opacity: 0;
  transform: translateY(20px);
  transition: all 0.3s;
  z-index: 999;
}}
.back-to-top.visible {{
  opacity: 1;
  transform: translateY(0);
}}
.back-to-top:hover {{
  background: #6366f1;
  transform: translateY(-2px);
  box-shadow: 0 6px 25px rgba(99,102,241,0.4);
}}
</style>
</head>
<body>

<header>
<section class="cover" role="banner">
  <div class="cover-content">
    <time class="meta" datetime="{iso_date}">{_esc(date_str)}</time>
    <h1>{_esc(title)}</h1>
    <p class="tagline">{_esc(tagline)}</p>
    <div class="source-badge">Curated from {_esc(source_name)}</div>
  </div>
</section>
</header>

<nav class="toc" id="toc">
  <div class="toc-inner">
    <h2 class="toc-heading">In This Edition</h2>
    {toc_items}
  </div>
</nav>

<main>
{spreads_html}
</main>

<button class="back-to-top" id="backToTop" onclick="window.scrollTo({{top:0,behavior:'smooth'}})" aria-label="Back to top">↑</button>

<footer class="footer">
  <div class="logo">Morning Edition</div>
  <p>Generated with AI — Anthropic Claude &amp; Google Gemini</p>
  <p style="margin-top:0.5rem;"><time datetime="{iso_date}">{_esc(date_str)}</time></p>
</footer>

<script>
(function() {{
  var btn = document.getElementById('backToTop');
  window.addEventListener('scroll', function() {{
    if (window.scrollY > 600) {{
      btn.classList.add('visible');
    }} else {{
      btn.classList.remove('visible');
    }}
  }});
}})();
</script>

</body>
</html>"""


def _render_spread(story: dict, index: int) -> str:
    style = story.get("spread_style", "editorial")
    headline = _esc(story.get("headline", "Untitled"))
    deck = _esc(story.get("deck", ""))
    body = story.get("body", "")
    pull_quote = _esc(story.get("pull_quote", ""))
    category = _esc(story.get("category_label", "TECH"))
    numeral = _esc(story.get("numeral", f"{index+1:02d}"))
    url = story.get("original_url", "#")
    applies = story.get("applies_to_me", False)

    # Convert body paragraphs
    if isinstance(body, str):
        paragraphs = body.split("\n\n") if "\n\n" in body else body.split("\n")
        paragraphs = [p.strip() for p in paragraphs if p.strip()]
    else:
        paragraphs = [str(body)]

    body_html = "\n".join([f"      <p>{_esc(p)}</p>" for p in paragraphs])
    flag_html = '<div class="flag-badge">⚡ Applies to You</div>' if applies else ""

    return f"""
<article class="spread spread-{style}" id="story-{index}" itemscope itemtype="https://schema.org/Article">
  <div class="numeral" aria-hidden="true">{numeral}</div>
  <div class="spread-inner">
    {flag_html}
    <div class="category-label" itemprop="articleSection">{category}</div>
    <h2 class="headline" itemprop="headline">{headline}</h2>
    <p class="deck" itemprop="description">{deck}</p>
    <div class="body" itemprop="articleBody">
{body_html}
    </div>
    <blockquote class="pull-quote">"{pull_quote}"</blockquote>
    <a href="{_esc_attr(url)}" target="_blank" rel="noopener noreferrer" class="read-more" itemprop="url">Read Original →</a>
  </div>
</article>
"""


def _esc(text: str) -> str:
    """Escape HTML entities."""
    return (
        str(text)
        .replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace('"', "&quot;")
    )


def _esc_attr(text: str) -> str:
    """Escape for HTML attributes."""
    return _esc(text).replace("'", "&#39;")
