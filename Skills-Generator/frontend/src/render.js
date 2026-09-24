/* ==========================================================================
   Rendering helpers — markdown, code highlighting, escaping
   ========================================================================== */

import { marked } from "marked";
import DOMPurify from "dompurify";
import hljs from "highlight.js/lib/core";
import python from "highlight.js/lib/languages/python";
import bash from "highlight.js/lib/languages/bash";
import javascript from "highlight.js/lib/languages/javascript";
import typescript from "highlight.js/lib/languages/typescript";
import json from "highlight.js/lib/languages/json";
import yaml from "highlight.js/lib/languages/yaml";
import markdown from "highlight.js/lib/languages/markdown";
import xml from "highlight.js/lib/languages/xml";
import css from "highlight.js/lib/languages/css";
import sql from "highlight.js/lib/languages/sql";
import "highlight.js/styles/github-dark.css";

hljs.registerLanguage("python", python);
hljs.registerLanguage("bash", bash);
hljs.registerLanguage("javascript", javascript);
hljs.registerLanguage("typescript", typescript);
hljs.registerLanguage("json", json);
hljs.registerLanguage("yaml", yaml);
hljs.registerLanguage("markdown", markdown);
hljs.registerLanguage("xml", xml);
hljs.registerLanguage("css", css);
hljs.registerLanguage("sql", sql);

const EXT_LANG = {
    py: "python", sh: "bash", bash: "bash", js: "javascript", mjs: "javascript", cjs: "javascript",
    ts: "typescript", json: "json", yaml: "yaml", yml: "yaml", md: "markdown", html: "xml",
    xml: "xml", css: "css", sql: "sql",
};

export function langOf(path) {
    return EXT_LANG[path.split(".").pop().toLowerCase()] || null;
}

export function escapeHtml(s) {
    return String(s ?? "").replace(/[&<>"']/g, (c) => (
        { "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]
    ));
}

export function highlight(code, lang) {
    if (lang && hljs.getLanguage(lang)) {
        return hljs.highlight(code, { language: lang, ignoreIllegals: true }).value;
    }
    return escapeHtml(code);
}

// Fenced code blocks inside markdown get highlighted too
marked.use({
    renderer: {
        code({ text, lang }) {
            const language = (lang || "").split(/\s/)[0];
            return `<pre><code class="hljs">${highlight(text, hljs.getLanguage(language) ? language : null)}</code></pre>`;
        },
    },
});

export function markdownHtml(text) {
    return DOMPurify.sanitize(marked.parse(text || ""));
}

export function renderMarkdown(el, text) {
    el.innerHTML = markdownHtml(text);
}

export function codeBlockHtml(code, lang) {
    // highlight() output is escaped by hljs; no user HTML survives
    return `<pre class="code-view"><code class="hljs">${highlight(code, lang)}</code></pre>`;
}

/** Split SKILL.md-style content into [frontmatterYaml|null, body]. */
export function splitFrontmatter(content) {
    const m = /^---\r?\n([\s\S]*?)\r?\n---\r?\n?([\s\S]*)$/.exec(content || "");
    return m ? [m[1], m[2]] : [null, content || ""];
}
