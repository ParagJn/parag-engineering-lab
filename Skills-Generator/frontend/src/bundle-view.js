/* ==========================================================================
   Bundle view — file tree, file viewer/editor, validation panel
   ========================================================================== */

import { codeBlockHtml, escapeHtml, langOf, markdownHtml, splitFrontmatter } from "./render.js";

const $ = (id) => document.getElementById(id);

const FILE_ICONS = {
    "SKILL.md": "star",
    reference: "menu_book",
    references: "menu_book",
    scripts: "terminal",
    templates: "description",
    assets: "image",
    examples: "lightbulb",
    evals: "fact_check",
};

let files = [];
let selectedPath = null;
let editing = false;

export const bundleState = {
    get selectedPath() { return selectedPath; },
    get editing() { return editing; },
    selectedFile: () => files.find((f) => f.path === selectedPath) || null,
};

function iconFor(path) {
    if (path === "SKILL.md") return FILE_ICONS["SKILL.md"];
    const top = path.includes("/") ? path.split("/")[0] : null;
    return FILE_ICONS[top] || "article";
}

function formatSize(bytes) {
    return bytes < 1024 ? `${bytes} B` : `${(bytes / 1024).toFixed(1)} KB`;
}

/** Group files by top-level folder (root files first). */
function groupFiles(list) {
    const groups = new Map([["", []]]);
    for (const f of list) {
        const folder = f.path.includes("/") ? f.path.slice(0, f.path.indexOf("/")) : "";
        if (!groups.has(folder)) groups.set(folder, []);
        groups.get(folder).push(f);
    }
    return groups;
}

export function setBundle(skill, keepSelection = false) {
    files = skill.files || [];
    if (!keepSelection || !files.some((f) => f.path === selectedPath)) {
        selectedPath = files[0]?.path || null;
    }
    editing = false;
    renderTree();
    renderFile();
    $("file-count").textContent = `${files.length} file${files.length === 1 ? "" : "s"}`;
}

export function selectFile(path) {
    if (editing && !confirm("Discard unsaved changes to this file?")) return;
    selectedPath = path;
    editing = false;
    renderTree();
    renderFile();
}

function renderTree() {
    const html = [];
    for (const [folder, items] of groupFiles(files)) {
        if (!items.length) continue;
        if (folder) {
            html.push(`
                <div class="flex items-center gap-1.5 px-2 pt-3 pb-1 text-[11px] font-semibold uppercase tracking-wider text-gray-400">
                    <span class="material-symbols-outlined" style="font-size:15px">folder</span>${escapeHtml(folder)}/
                </div>`);
        }
        for (const f of items) {
            const active = f.path === selectedPath;
            const label = folder ? f.path.slice(folder.length + 1) : f.path;
            html.push(`
                <button data-action="selectFile" data-path="${escapeHtml(f.path)}"
                    class="w-full flex items-center gap-2 ${folder ? "pl-5" : "pl-2"} pr-2 py-1.5 rounded-md text-left text-[13px] transition-colors
                    ${active ? "bg-gray-900 text-white" : "text-gray-700 hover:bg-gray-100"}">
                    <span class="material-symbols-outlined ${active ? "text-white" : "text-gray-400"}" style="font-size:16px">${iconFor(f.path)}</span>
                    <span class="truncate flex-1 font-mono">${escapeHtml(label)}</span>
                    <span class="text-[10px] ${active ? "text-gray-300" : "text-gray-400"}">${formatSize(f.size)}</span>
                </button>`);
        }
    }
    $("file-tree").innerHTML = html.join("") || `<p class="text-xs text-gray-400 p-2">No files</p>`;
}

function renderFile() {
    const f = bundleState.selectedFile();
    $("file-path").textContent = f ? f.path : "";
    $("file-lang").textContent = f ? (langOf(f.path) || "text") : "";
    $("delete-file-btn").classList.toggle("hidden", !f || f.path === "SKILL.md");
    $("file-view").classList.toggle("hidden", editing);
    $("file-editor").classList.toggle("hidden", !editing);
    $("file-actions").classList.toggle("hidden", editing);
    $("file-edit-actions").classList.toggle("hidden", !editing);
    $("file-edit-actions").classList.toggle("flex", editing);
    if (!f) {
        $("file-view").innerHTML = "";
        return;
    }

    const lang = langOf(f.path);
    if (lang === "markdown") {
        const [frontmatter, body] = splitFrontmatter(f.content);
        $("file-view").innerHTML = `
            ${frontmatter !== null ? `
                <div class="mb-4">
                    <div class="text-[11px] font-semibold uppercase tracking-wider text-gray-400 mb-1">Frontmatter</div>
                    ${codeBlockHtml(frontmatter, "yaml")}
                </div>` : ""}
            <div class="prose max-w-none text-gray-700 text-sm leading-relaxed">${markdownHtml(body)}</div>`;
    } else {
        $("file-view").innerHTML = codeBlockHtml(f.content, lang);
    }
}

export function startEdit() {
    const f = bundleState.selectedFile();
    if (!f) return;
    editing = true;
    const editor = $("file-editor");
    editor.value = f.content;
    editor.rows = Math.min(40, Math.max(16, f.content.split("\n").length + 2));
    renderFile();
    editor.focus();
}

export function cancelEdit() {
    editing = false;
    renderFile();
}

export function editorValue() {
    return $("file-editor").value;
}

// ---------------------------------------------------------------------------
// Validation panel
// ---------------------------------------------------------------------------

export function renderValidation(report, formatVersion) {
    const panel = $("validation-panel");
    const badge = $("validation-badge");
    if (!report) {
        badge.className = "px-2.5 py-0.5 text-[11px] font-semibold rounded-full bg-gray-100 text-gray-600";
        badge.textContent = "Not validated";
        $("validation-content").innerHTML = `<p class="text-sm text-gray-500">
            ${formatVersion < 2 ? "This skill was created by the older single-file generator." : ""}
            Click <strong>Re-validate</strong> to run the static checks.</p>`;
        panel.classList.remove("hidden");
        return;
    }
    const { errors = [], warnings = [], passed = [] } = report;
    badge.className = `px-2.5 py-0.5 text-[11px] font-semibold rounded-full ${
        errors.length ? "bg-red-50 text-red-700" : "bg-green-50 text-green-700"}`;
    badge.textContent = errors.length
        ? `${errors.length} error${errors.length === 1 ? "" : "s"}`
        : "Valid";

    const list = (items, icon, color) => items.map((t) => `
        <li class="flex items-start gap-2 py-1">
            <span class="material-symbols-outlined ${color} flex-shrink-0" style="font-size:18px">${icon}</span>
            <span class="text-sm text-gray-700">${escapeHtml(t)}</span>
        </li>`).join("");

    $("validation-content").innerHTML = `
        ${errors.length ? `<ul class="mb-2">${list(errors, "error", "text-google-red")}</ul>` : ""}
        ${warnings.length ? `<ul class="mb-2">${list(warnings, "warning", "text-google-yellow")}</ul>` : ""}
        <details class="mt-1">
            <summary class="text-xs text-gray-500 cursor-pointer select-none">${passed.length} check${passed.length === 1 ? "" : "s"} passed</summary>
            <ul class="mt-1">${list(passed, "check_circle", "text-google-green")}</ul>
        </details>`;
    panel.classList.remove("hidden");
}
