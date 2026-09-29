import time

import streamlit as st
from scrapling.fetchers import DynamicFetcher, Fetcher, StealthyFetcher

st.set_page_config(page_title="Web Scraper", page_icon="🕸️", layout="wide")

MODES = {
    "Fast (static HTTP)": "fast",
    "Stealth (anti-bot bypass)": "stealth",
    "Dynamic (JS-rendered browser)": "dynamic",
}

st.title("🕸️ Web Scraper")
st.caption("Powered by Scrapling")

with st.sidebar:
    st.header("Fetch mode")
    st.markdown(
        "- **Fast** — plain HTTP request with browser-like headers. "
        "Quickest, works on most sites.\n"
        "- **Stealth** — headless browser with anti-bot bypass "
        "(Cloudflare, etc). Slower, use when Fast is blocked.\n"
        "- **Dynamic** — full browser render, waits for JavaScript. "
        "Use for sites whose content loads client-side."
    )

with st.form("scrape_form"):
    url = st.text_input("URL to scrape", placeholder="https://example.com")
    mode_label = st.selectbox("Fetch mode", list(MODES.keys()))
    submitted = st.form_submit_button("Scrape", type="primary")

if submitted:
    url = url.strip()
    if not url:
        st.warning("Enter a URL first.")
        st.stop()
    if not url.startswith(("http://", "https://")):
        url = "https://" + url

    mode = MODES[mode_label]

    with st.spinner(f"Fetching {url} ..."):
        try:
            start = time.time()
            if mode == "fast":
                page = Fetcher.get(url, stealthy_headers=True)
            elif mode == "stealth":
                page = StealthyFetcher.fetch(url, headless=True)
            else:
                page = DynamicFetcher.fetch(url, headless=True)
            elapsed = time.time() - start
        except Exception as e:
            st.error(f"Failed to fetch **{url}**: {e}")
            st.stop()

    if page.status >= 400:
        st.error(f"Server returned status {page.status} for {url}")
        st.stop()

    title = (page.css("title::text").get(default="") or "").strip()
    meta_desc = (
        page.css('meta[name="description"]::attr(content)').get(default="") or ""
    ).strip()
    headings = [h.text.strip() for h in page.css("h1, h2, h3") if h.text and h.text.strip()]
    links = [
        {"text": (a.text or "").strip(), "href": a.attrib.get("href", "")}
        for a in page.css("a")
        if a.attrib.get("href")
    ]
    images = [img.attrib.get("src", "") for img in page.css("img") if img.attrib.get("src")]
    word_count = len(page.get_all_text().split())

    st.success(f"Fetched **{url}** in {elapsed:.2f}s — status {page.status}")

    col1, col2, col3, col4 = st.columns(4)
    col1.metric("Status", page.status)
    col2.metric("Words", word_count)
    col3.metric("Links", len(links))
    col4.metric("Images", len(images))

    tab_overview, tab_content, tab_links, tab_images, tab_raw = st.tabs(
        ["Overview", "Content", "Links", "Images", "Raw HTML"]
    )

    with tab_overview:
        st.subheader(title or "(no title found)")
        if meta_desc:
            st.write(meta_desc)
        if headings:
            st.markdown("**Headings on page**")
            for h in headings[:30]:
                st.markdown(f"- {h}")

    with tab_content:
        markdown_content = page.markdown()
        if markdown_content:
            st.markdown(markdown_content)
        else:
            st.info("No readable text content found.")

    with tab_links:
        if links:
            st.dataframe(links, use_container_width=True, hide_index=True)
        else:
            st.info("No links found.")

    with tab_images:
        if images:
            st.dataframe(
                [{"src": src} for src in images], use_container_width=True, hide_index=True
            )
        else:
            st.info("No images found.")

    with tab_raw:
        html_content = page.html_content
        st.download_button(
            "Download full HTML",
            data=html_content,
            file_name="page.html",
            mime="text/html",
        )
        preview_limit = 20000
        st.code(html_content[:preview_limit], language="html")
        if len(html_content) > preview_limit:
            st.caption(f"Showing first {preview_limit:,} of {len(html_content):,} characters.")
