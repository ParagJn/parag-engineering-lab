/* ==========================================================================
   Skills Generator — Frontend Application
   ========================================================================== */

import "./style.css";
import { api, streamSSE } from "./api.js";
import { escapeHtml, markdownHtml, renderMarkdown } from "./render.js";
import {
    bundleState, cancelEdit, editorValue, renderValidation, selectFile, setBundle, startEdit,
} from "./bundle-view.js";

// ---------------------------------------------------------------------------
// State
// ---------------------------------------------------------------------------
let currentSkill = null;
let skills = [];
let busy = false; // a generation/regeneration stream is running

const $ = (id) => document.getElementById(id);

// ---------------------------------------------------------------------------
// Platform theming
// ---------------------------------------------------------------------------
const PLATFORMS = {
    anthropic: {
        border: "border-l-google-red",
        badgeBg: "bg-red-50",
        badgeText: "text-red-700",
        iconColor: "text-google-red",
        icon: "auto_awesome",
        label: "Claude Code",
    },
    gemini: {
        border: "border-l-google-blue",
        badgeBg: "bg-blue-50",
        badgeText: "text-blue-700",
        iconColor: "text-google-blue",
        icon: "diamond",
        label: "Gemini",
    },
    chatgpt: {
        border: "border-l-google-green",
        badgeBg: "bg-green-50",
        badgeText: "text-green-700",
        iconColor: "text-google-green",
        icon: "smart_toy",
        label: "ChatGPT",
    },
};

const platformOf = (skill) => PLATFORMS[skill.platform] || PLATFORMS.anthropic;

const STAGES = [
    ["design", "Design", "Name, trigger description, invocation, file plan, eval scenarios"],
    ["write", "Write files", "SKILL.md, reference files, scripts, templates, evals"],
    ["validate", "Validate", "Spec rules, links, script syntax (never executed), evals"],
    ["repair", "Repair", "Send validation errors back to the model for fixes"],
    ["notes", "Usage guide", "How to install and invoke it"],
    ["save", "Save", "Write the folder and sync to .claude/skills"],
];

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------
function shakeElement(el) {
    el.classList.add("ring-2", "ring-google-red/50");
    el.classList.remove("shake");
    void el.offsetWidth; // restart animation
    el.classList.add("shake");
    setTimeout(() => el.classList.remove("ring-2", "ring-google-red/50", "shake"), 500);
}

function flashIcon(id, icon, original) {
    const el = $(id);
    el.textContent = icon;
    setTimeout(() => { el.textContent = original; }, 1500);
}

// ---------------------------------------------------------------------------
// Skills list
// ---------------------------------------------------------------------------
async function loadSkills() {
    try {
        skills = await api("/skills");
        renderSidebar();
    } catch (e) {
        console.error("Failed to load skills:", e);
    }
}

function renderSidebar() {
    const el = $("skill-list");

    if (skills.length === 0) {
        el.innerHTML = `
            <div class="flex flex-col items-center py-10 text-gray-500 opacity-60">
                <span class="material-symbols-outlined mb-2" style="font-size:36px">folder_open</span>
                <p class="text-xs">No skills generated yet</p>
            </div>`;
        return;
    }

    el.innerHTML = skills
        .map((s) => {
            const p = platformOf(s);
            const active = s.id === currentSkill?.id;
            const tag = s.format_version < 2
                ? `<span class="text-amber-400">single file</span>`
                : s.valid === false ? `<span class="text-red-400">has errors</span>` : "bundle";
            return `
            <button data-action="loadSkill" data-id="${escapeHtml(s.id)}"
                class="w-full text-left px-3 py-2.5 rounded-lg transition-colors ${active ? "bg-gray-700/80" : "hover:bg-gray-800/60"} group">
                <div class="flex items-center gap-2.5">
                    <span class="material-symbols-outlined ${active ? "text-white" : "text-gray-400 group-hover:text-gray-300"}" style="font-size:18px">${p.icon}</span>
                    <div class="min-w-0 flex-1">
                        <div class="text-[13px] font-medium truncate ${active ? "text-white" : "text-gray-300"}">${escapeHtml(s.name)}</div>
                        <div class="text-[11px] text-gray-500">${p.label} · ${tag}${s.installed_path ? " · installed" : ""}</div>
                    </div>
                </div>
            </button>`;
        })
        .join("");
}

async function loadModelLabels() {
    try {
        const models = await api("/models");
        document.querySelectorAll("[data-model-label]").forEach((el) => {
            const model = models[el.dataset.modelLabel];
            if (model) el.textContent = `${model} via IBM ICA`;
        });
    } catch {
        // Labels are cosmetic; keep the default text
    }
}

// ---------------------------------------------------------------------------
// Sidebar toggle (mobile / tablet)
// ---------------------------------------------------------------------------
function toggleSidebar() {
    $("sidebar").classList.toggle("-translate-x-full");
    $("sidebar-overlay").classList.toggle("hidden");
}

function closeMobileSidebar() {
    if (window.innerWidth < 1024 && !$("sidebar").classList.contains("-translate-x-full")) {
        toggleSidebar();
    }
}

// ---------------------------------------------------------------------------
// View switching
// ---------------------------------------------------------------------------
function showView(name) {
    ["create-view", "loading-view", "result-view"].forEach((id) => {
        $(id).classList.toggle("hidden", id !== `${name}-view`);
    });
}

function showCreateView({ keepInput = false } = {}) {
    if (busy) return;
    currentSkill = null;
    showView("create");
    if (!keepInput) $("thought-input").value = "";
    renderSidebar();
    closeMobileSidebar();
}

function showLoading(text, { stages = false } = {}) {
    showView("loading");
    $("loading-text").textContent = text || "Loading…";
    $("progress-steps").classList.toggle("hidden", !stages);
    $("progress-hint").classList.toggle("hidden", !stages);
    if (stages) {
        $("progress-steps").innerHTML = STAGES.map(([key, label, hint]) => `
            <li id="stage-${key}" data-state="pending" class="stage flex items-start gap-3 px-4 py-2.5 rounded-lg bg-white border border-gray-100 ${key === "repair" ? "hidden" : ""}">
                <span class="stage-icon material-symbols-outlined text-gray-300 flex-shrink-0" style="font-size:20px">radio_button_unchecked</span>
                <div class="min-w-0">
                    <div class="text-sm font-semibold text-gray-700">${label}</div>
                    <div class="stage-msg text-xs text-gray-400 truncate">${hint}</div>
                </div>
            </li>`).join("");
    }
}

function updateStage(event) {
    const li = $(`stage-${event.stage}`);
    if (!li) return;
    li.classList.remove("hidden");
    const icon = li.querySelector(".stage-icon");
    // Earlier stages are complete once a later one starts
    const idx = STAGES.findIndex(([k]) => k === event.stage);
    STAGES.slice(0, idx).forEach(([k]) => {
        const prev = $(`stage-${k}`);
        if (prev?.dataset.state === "active") setStageState(prev, "done");
    });
    setStageState(li, event.done ? "done" : "active");
    if (event.done && event.report && !event.report.ok) {
        icon.textContent = "error";
        icon.className = "stage-icon material-symbols-outlined text-google-red flex-shrink-0";
    }
    li.querySelector(".stage-msg").textContent = event.message;
    $("loading-text").textContent = event.done ? "Working…" : event.message;
}

function setStageState(li, state) {
    li.dataset.state = state;
    const icon = li.querySelector(".stage-icon");
    if (state === "done") {
        icon.textContent = "check_circle";
        icon.className = "stage-icon material-symbols-outlined text-google-green flex-shrink-0";
    } else if (state === "active") {
        icon.textContent = "progress_activity";
        icon.className = "stage-icon material-symbols-outlined text-google-blue animate-spin flex-shrink-0";
    }
}

function showResult(skill, { keepFile = false } = {}) {
    currentSkill = skill;
    showView("result");
    $("test-results").classList.add("hidden");
    $("usage-notes").classList.add("hidden");

    const p = platformOf(skill);
    const v2 = (skill.format_version || 1) >= 2;
    $("skill-card").className = `bg-white rounded-2xl shadow-sm border-l-4 ${p.border} overflow-hidden`;
    $("result-skill-name").textContent = skill.skill_dir || skill.name;

    const icon = $("result-platform-icon");
    icon.textContent = p.icon;
    icon.className = `material-symbols-outlined text-2xl ${p.iconColor} flex-shrink-0`;

    const badge = $("result-platform-badge");
    badge.textContent = p.label;
    badge.className = `inline-block px-2.5 py-0.5 text-[11px] font-semibold rounded-full ${p.badgeBg} ${p.badgeText}`;

    const fmt = $("result-format-badge");
    fmt.textContent = v2 ? `Skill bundle · ${skill.files.length} files` : "Single file (legacy)";
    fmt.className = `inline-block px-2.5 py-0.5 text-[11px] font-semibold rounded-full ${v2 ? "bg-gray-100 text-gray-600" : "bg-amber-50 text-amber-700"}`;

    // Upgrade only makes sense for the old single-file skills on bundle platforms
    $("upgrade-banner").classList.toggle("hidden", v2 || skill.platform === "chatgpt");

    const canInstall = skill.platform === "anthropic";
    $("install-btn").classList.toggle("hidden", !canInstall);
    $("install-btn").classList.toggle("flex", canInstall);
    $("install-label").textContent = skill.installed_path ? "Uninstall from ~/.claude/skills" : "Install to ~/.claude/skills";
    $("installed-badge").classList.toggle("hidden", !skill.installed_path);
    $("installed-badge").textContent = skill.installed_path ? `Installed: ${skill.installed_path.replace(/^.*\/\.claude\//, "~/.claude/")}` : "";

    setBundle(skill, keepFile);
    renderValidation(skill.validation, skill.format_version || 1);

    if (skill.usage_notes) {
        renderMarkdown($("usage-notes-content"), skill.usage_notes);
        $("usage-notes").classList.remove("hidden");
    }
    if (skill.evals_last_run?.evals?.length) renderEvalResults(skill.evals_last_run, { lastRun: true });

    renderSidebar();
}

// ---------------------------------------------------------------------------
// Generation (streamed)
// ---------------------------------------------------------------------------
function generationOptions() {
    return {
        invocation: $("opt-invocation").value,
        scripts: $("opt-scripts").value,
        script_language: $("opt-language").value,
    };
}

async function runPipeline(path, body, loadingText) {
    busy = true;
    showLoading(loadingText, { stages: true });
    try {
        const done = await streamSSE(path, body, (event) => {
            if (event.type === "stage") updateStage(event);
        });
        return done.skill;
    } finally {
        busy = false;
    }
}

async function generateSkill() {
    if (busy) return;
    const input = $("thought-input");
    const thought = input.value.trim();
    if (!thought) {
        shakeElement(input);
        return;
    }
    const platform = document.querySelector('input[name="platform"]:checked').value;

    try {
        const skill = await runPipeline(
            "/generate", { thought, platform, options: generationOptions() }, "Generating your skill…",
        );
        await loadSkills();
        showResult(skill);
    } catch (e) {
        alert("Generation failed: " + e.message);
        showCreateView({ keepInput: true });
    }
}

async function regenerateSkill({ upgrade = false } = {}) {
    if (!currentSkill || busy) return;
    const question = upgrade
        ? "Upgrade this skill to a full bundle? It is regenerated from the original idea (same id)."
        : "Regenerate this skill from the original idea? The current version will be replaced.";
    if (!confirm(question)) return;
    const previous = currentSkill;
    try {
        const skill = await runPipeline(
            `/skills/${previous.id}/regenerate`, {}, upgrade ? "Upgrading to a full bundle…" : "Regenerating skill…",
        );
        await loadSkills();
        showResult(skill);
    } catch (e) {
        alert((upgrade ? "Upgrade" : "Regeneration") + " failed: " + e.message);
        showResult(previous); // old version is untouched on failure
    }
}

async function loadSkill(id) {
    if (busy) return;
    if (bundleState.editing && !confirm("Discard unsaved changes?")) return;
    showLoading("Loading skill…");
    closeMobileSidebar();
    try {
        showResult(await api(`/skills/${encodeURIComponent(id)}`));
    } catch (e) {
        alert("Failed to load skill: " + e.message);
        showCreateView();
    }
}

// ---------------------------------------------------------------------------
// Skill actions
// ---------------------------------------------------------------------------
async function deleteSkill() {
    if (!currentSkill) return;
    const extra = currentSkill.installed_path ? "\n\nIts copy in ~/.claude/skills will be removed too." : "";
    if (!confirm("Delete this skill permanently?" + extra)) return;
    try {
        await api(`/skills/${currentSkill.id}`, { method: "DELETE" });
        await loadSkills();
        showCreateView();
    } catch (e) {
        alert("Delete failed: " + e.message);
    }
}

async function archiveSkill() {
    if (!currentSkill) return;
    const extra = currentSkill.installed_path ? "\n\nIts copy in ~/.claude/skills will be removed." : "";
    if (!confirm("Archive this skill?" + extra)) return;
    try {
        await api(`/skills/${currentSkill.id}/archive`, { method: "POST" });
        await loadSkills();
        showCreateView();
    } catch (e) {
        alert("Archive failed: " + e.message);
    }
}

function downloadSkill() {
    if (!currentSkill) return;
    const a = document.createElement("a");
    a.href = `/api/skills/${currentSkill.id}/download`;
    a.download = `${currentSkill.skill_dir || currentSkill.name}.zip`;
    a.click();
}

async function installSkill() {
    if (!currentSkill) return;
    const id = currentSkill.id;
    try {
        if (currentSkill.installed_path) {
            if (!confirm(`Remove ${currentSkill.installed_path}?`)) return;
            showResult(await api(`/skills/${id}/install`, { method: "DELETE" }), { keepFile: true });
        } else {
            try {
                showResult(await api(`/skills/${id}/install`, { method: "POST", body: "{}" }), { keepFile: true });
            } catch (e) {
                if (e.status !== 409 || !confirm(e.message)) throw e;
                showResult(await api(`/skills/${id}/install`, {
                    method: "POST", body: JSON.stringify({ overwrite: true }),
                }), { keepFile: true });
            }
            alert(`Installed. In Claude Code, run /${currentSkill.skill_dir} (restart Claude Code if it was already open).`);
        }
        await loadSkills();
    } catch (e) {
        alert("Install failed: " + e.message);
    }
}

async function revalidateSkill() {
    if (!currentSkill) return;
    try {
        showResult(await api(`/skills/${currentSkill.id}/validate`, { method: "POST" }), { keepFile: true });
        await loadSkills();
    } catch (e) {
        alert("Validation failed: " + e.message);
    }
}

// ---------------------------------------------------------------------------
// File actions
// ---------------------------------------------------------------------------
async function copyFile() {
    const f = bundleState.selectedFile();
    if (!f) return;
    try {
        await navigator.clipboard.writeText(f.content);
        flashIcon("copy-icon", "check", "content_copy");
    } catch (e) {
        alert("Copy failed: " + e.message);
    }
}

async function saveFile() {
    const f = bundleState.selectedFile();
    if (!currentSkill || !f) return;
    const content = editorValue();
    if (!content.trim()) {
        shakeElement($("file-editor"));
        return;
    }
    try {
        const updated = await api(`/skills/${currentSkill.id}/files/${encodePath(f.path)}`, {
            method: "PUT",
            body: JSON.stringify({ content }),
        });
        await loadSkills(); // name may have changed
        showResult(updated, { keepFile: true });
    } catch (e) {
        alert("Save failed: " + e.message);
    }
}

async function deleteFile() {
    const f = bundleState.selectedFile();
    if (!currentSkill || !f || f.path === "SKILL.md") return;
    if (!confirm(`Delete ${f.path} from this skill?`)) return;
    try {
        showResult(await api(`/skills/${currentSkill.id}/files/${encodePath(f.path)}`, { method: "DELETE" }));
        await loadSkills();
    } catch (e) {
        alert("Delete failed: " + e.message);
    }
}

const encodePath = (path) => path.split("/").map(encodeURIComponent).join("/");

// ---------------------------------------------------------------------------
// Evals
// ---------------------------------------------------------------------------
const TEST_BTN_IDLE = `<span class="material-symbols-outlined" style="font-size:20px">science</span> Run Evals`;
const TEST_BTN_BUSY = `
    <svg class="animate-spin h-5 w-5" xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24">
        <circle class="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" stroke-width="4"></circle>
        <path class="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z"></path>
    </svg>
    <span>Running evals…</span>`;

function evalCardHtml(ev) {
    const pass = ev.overall_pass;
    const rows = (ev.results || []).map((r) => `
        <li class="flex items-start gap-2 py-1">
            <span class="material-symbols-outlined ${r.pass ? "text-google-green" : "text-google-red"} flex-shrink-0" style="font-size:18px">${r.pass ? "check_circle" : "cancel"}</span>
            <div class="text-sm">
                <div class="text-gray-800">${escapeHtml(r.behavior)}</div>
                ${r.reason ? `<div class="text-xs text-gray-500">${escapeHtml(r.reason)}</div>` : ""}
            </div>
        </li>`).join("");
    const suggestions = (ev.suggestions || []).length
        ? `<div class="mt-2 text-xs text-gray-600"><span class="font-semibold">Suggestions:</span>
            <ul class="list-disc pl-5">${ev.suggestions.map((s) => `<li>${escapeHtml(s)}</li>`).join("")}</ul></div>`
        : "";
    return `
        <div class="border ${pass ? "border-green-200" : "border-red-200"} rounded-xl p-4">
            <div class="flex items-start justify-between gap-3 mb-2">
                <div class="text-sm font-semibold text-gray-900">#${ev.index} · ${escapeHtml(ev.query)}</div>
                <span class="px-2 py-0.5 text-[11px] font-bold rounded-full flex-shrink-0 ${pass ? "bg-green-50 text-green-700" : "bg-red-50 text-red-700"}">
                    ${pass ? "PASS" : "FAIL"} ${ev.passed}/${ev.total}
                </span>
            </div>
            <ul>${rows}</ul>
            ${suggestions}
            ${ev.response ? `
                <details class="mt-2">
                    <summary class="text-xs text-gray-500 cursor-pointer select-none">Show the response</summary>
                    <div class="prose max-w-none text-gray-700 text-sm mt-2 border-t border-gray-100 pt-2">${markdownHtml(ev.response)}</div>
                </details>` : ""}
        </div>`;
}

function renderEvalResults(result, { lastRun = false } = {}) {
    const evals = [...(result.evals || [])].sort((a, b) => a.index - b.index);
    $("test-summary").textContent = (lastRun ? "Last run: " : "") + (result.summary || "");
    const staticNote = result.static
        ? `<p class="text-xs text-gray-500">Static checks: ${result.static.ok ? "passed" : `${result.static.errors.length} error(s)`}, ${result.static.warnings.length} warning(s). Scripts are syntax-checked only, never executed.</p>`
        : "";
    $("test-content").innerHTML = staticNote + evals.map(evalCardHtml).join("");
    $("test-results").classList.remove("hidden");
}

async function testSkill() {
    if (!currentSkill) return;
    const skillId = currentSkill.id;
    const btn = $("test-btn");
    btn.disabled = true;
    btn.innerHTML = TEST_BTN_BUSY;
    const partial = { evals: [], summary: "Running…" };
    $("test-content").innerHTML = "";
    $("test-summary").textContent = "";

    try {
        const done = await streamSSE(`/skills/${skillId}/test`, {}, (event) => {
            if (currentSkill?.id !== skillId) return; // user navigated away
            if (event.type === "stage" && event.stage === "static") partial.static = event.report;
            if (event.type === "stage") partial.summary = event.message;
            if (event.type === "eval") partial.evals.push(event.eval);
            if (event.type !== "done") renderEvalResults(partial);
        });
        if (currentSkill?.id !== skillId) return;
        renderEvalResults(done.result);
        if (currentSkill.validation !== undefined && done.result.static) {
            renderValidation(done.result.static, currentSkill.format_version || 1);
        }
        $("test-results").scrollIntoView({ behavior: "smooth", block: "start" });
    } catch (e) {
        alert("Evals failed: " + e.message);
    } finally {
        btn.disabled = false;
        btn.innerHTML = TEST_BTN_IDLE;
    }
}

// ---------------------------------------------------------------------------
// Event wiring
// ---------------------------------------------------------------------------
const ACTIONS = {
    toggleSidebar,
    showCreateView: () => showCreateView(),
    generateSkill,
    loadSkill: (el) => loadSkill(el.dataset.id),
    downloadSkill,
    regenerateSkill: () => regenerateSkill(),
    upgradeSkill: () => regenerateSkill({ upgrade: true }),
    archiveSkill,
    deleteSkill,
    installSkill,
    revalidateSkill,
    selectFile: (el) => selectFile(el.dataset.path),
    editFile: startEdit,
    cancelFileEdit: cancelEdit,
    saveFile,
    deleteFile,
    copyFile,
    testSkill,
};

document.addEventListener("click", (e) => {
    const el = e.target.closest("[data-action]");
    if (!el || el.disabled) return;
    ACTIONS[el.dataset.action]?.(el);
});

// Ctrl/Cmd + Enter in the idea box generates; Ctrl/Cmd + S saves a file being edited
$("thought-input").addEventListener("keydown", (e) => {
    if (e.key === "Enter" && (e.metaKey || e.ctrlKey)) generateSkill();
});
$("file-editor").addEventListener("keydown", (e) => {
    if (e.key === "s" && (e.metaKey || e.ctrlKey)) {
        e.preventDefault();
        saveFile();
    }
});

// Invocation / script options only apply to bundle platforms
document.querySelectorAll('input[name="platform"]').forEach((radio) => {
    radio.addEventListener("change", () => {
        const platform = document.querySelector('input[name="platform"]:checked').value;
        $("opt-invocation").disabled = platform !== "anthropic";
        $("opt-scripts").disabled = platform === "chatgpt";
        $("opt-language").disabled = platform === "chatgpt";
    });
});

window.addEventListener("beforeunload", (e) => {
    if (busy || bundleState.editing) e.preventDefault();
});

loadSkills();
loadModelLabels();
