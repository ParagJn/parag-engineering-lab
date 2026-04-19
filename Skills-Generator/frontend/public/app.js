/* ==========================================================================
   Skills Generator — Frontend Application
   ========================================================================== */

// ---------------------------------------------------------------------------
// State
// ---------------------------------------------------------------------------
let currentSkillId = null;
let skills = [];

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
        label: "Anthropic",
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
        label: "GPT-5.4",
    },
};

// ---------------------------------------------------------------------------
// Init
// ---------------------------------------------------------------------------
document.addEventListener("DOMContentLoaded", () => {
    loadSkills();
});

// ---------------------------------------------------------------------------
// API helper
// ---------------------------------------------------------------------------
async function api(path, opts = {}) {
    const res = await fetch(`/api${path}`, {
        headers: { "Content-Type": "application/json" },
        ...opts,
    });
    if (!res.ok) {
        const err = await res.json().catch(() => ({ detail: res.statusText }));
        throw new Error(err.detail || "Request failed");
    }
    return res.json();
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
    const el = document.getElementById("skill-list");

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
            const p = PLATFORMS[s.platform] || PLATFORMS.anthropic;
            const active = s.id === currentSkillId;
            return `
            <button onclick="loadSkill('${s.id}')"
                class="w-full text-left px-3 py-2.5 rounded-lg transition-colors ${active ? "bg-gray-700/80" : "hover:bg-gray-800/60"} group">
                <div class="flex items-center gap-2.5">
                    <span class="material-symbols-outlined ${active ? "text-white" : "text-gray-400 group-hover:text-gray-300"}" style="font-size:18px">${p.icon}</span>
                    <div class="min-w-0">
                        <div class="text-[13px] font-medium truncate ${active ? "text-white" : "text-gray-300"}">${s.name}</div>
                        <div class="text-[11px] text-gray-500">${p.label} · ${new Date(s.created_at).toLocaleDateString()}</div>
                    </div>
                </div>
            </button>`;
        })
        .join("");
}

// ---------------------------------------------------------------------------
// Sidebar toggle (mobile / tablet)
// ---------------------------------------------------------------------------
function toggleSidebar() {
    document.getElementById("sidebar").classList.toggle("-translate-x-full");
    document.getElementById("sidebar-overlay").classList.toggle("hidden");
}

function closeMobileSidebar() {
    const sb = document.getElementById("sidebar");
    if (window.innerWidth < 1024 && !sb.classList.contains("-translate-x-full")) {
        toggleSidebar();
    }
}

// ---------------------------------------------------------------------------
// View switching
// ---------------------------------------------------------------------------
function showView(name) {
    ["create-view", "loading-view", "result-view"].forEach((id) => {
        document.getElementById(id).classList.toggle("hidden", id !== `${name}-view`);
    });
}

function showCreateView() {
    currentSkillId = null;
    showView("create");
    document.getElementById("thought-input").value = "";
    renderSidebar();
    closeMobileSidebar();
}

function showLoading(text) {
    showView("loading");
    document.getElementById("loading-text").textContent = text || "Generating your skill…";
}

function showResult(skill) {
    showView("result");
    _exitEditMode();
    _editOriginalContent = null;
    document.getElementById("test-results").classList.add("hidden");
    document.getElementById("usage-notes").classList.add("hidden");

    const p = PLATFORMS[skill.platform] || PLATFORMS.anthropic;

    // Card border
    const card = document.getElementById("skill-card");
    card.className = `bg-white rounded-2xl shadow-sm border-l-4 ${p.border} overflow-hidden`;

    // Title & badge
    document.getElementById("result-skill-name").textContent = skill.name;
    const icon = document.getElementById("result-platform-icon");
    icon.textContent = p.icon;
    icon.className = `material-symbols-outlined text-2xl ${p.iconColor} flex-shrink-0`;

    const badge = document.getElementById("result-platform-badge");
    badge.textContent = p.label;
    badge.className = `inline-block mt-0.5 px-2.5 py-0.5 text-[11px] font-semibold rounded-full ${p.badgeBg} ${p.badgeText}`;

    // Render markdown
    document.getElementById("skill-content").innerHTML = marked.parse(skill.content || "");

    // Render usage notes
    if (skill.usage_notes) {
        document.getElementById("usage-notes-content").innerHTML = marked.parse(skill.usage_notes);
        document.getElementById("usage-notes").classList.remove("hidden");
    }

    currentSkillId = skill.id;
    renderSidebar();
}

// ---------------------------------------------------------------------------
// Generate
// ---------------------------------------------------------------------------
async function generateSkill() {
    const thought = document.getElementById("thought-input").value.trim();
    if (!thought) {
        shakeElement(document.getElementById("thought-input"));
        return;
    }
    const platform = document.querySelector('input[name="platform"]:checked').value;

    showLoading("Generating your skill…");
    try {
        const result = await api("/generate", {
            method: "POST",
            body: JSON.stringify({ thought, platform }),
        });
        await loadSkills();
        showResult(result);
    } catch (e) {
        alert("Generation failed: " + e.message);
        showCreateView();
    }
}

// ---------------------------------------------------------------------------
// Load existing skill
// ---------------------------------------------------------------------------
async function loadSkill(id) {
    showLoading("Loading skill…");
    closeMobileSidebar();
    try {
        const skill = await api(`/skills/${id}`);
        showResult(skill);
    } catch (e) {
        alert("Failed to load skill: " + e.message);
        showCreateView();
    }
}

// ---------------------------------------------------------------------------
// Regenerate
// ---------------------------------------------------------------------------
async function regenerateSkill() {
    if (!currentSkillId || !confirm("Regenerate this skill? The current version will be replaced.")) return;
    showLoading("Regenerating skill…");
    try {
        const result = await api(`/skills/${currentSkillId}/regenerate`, { method: "POST" });
        await loadSkills();
        showResult(result);
    } catch (e) {
        alert("Regeneration failed: " + e.message);
    }
}

// ---------------------------------------------------------------------------
// Delete
// ---------------------------------------------------------------------------
async function deleteSkill() {
    if (!currentSkillId || !confirm("Delete this skill permanently?")) return;
    try {
        await api(`/skills/${currentSkillId}`, { method: "DELETE" });
        await loadSkills();
        showCreateView();
    } catch (e) {
        alert("Delete failed: " + e.message);
    }
}

// ---------------------------------------------------------------------------
// Copy to Clipboard (for Gemini / OpenAI paste workflows)
// ---------------------------------------------------------------------------
async function copySkillContent() {
    if (!currentSkillId) return;
    try {
        const skill = await api(`/skills/${currentSkillId}`);
        await navigator.clipboard.writeText(skill.content || "");
        const icon = document.getElementById("copy-icon");
        icon.textContent = "check";
        setTimeout(() => { icon.textContent = "content_copy"; }, 1500);
    } catch (e) {
        alert("Copy failed: " + e.message);
    }
}

// ---------------------------------------------------------------------------
// Download
// ---------------------------------------------------------------------------
function downloadSkill() {
    if (!currentSkillId) return;
    window.open(`/api/skills/${currentSkillId}/download`, "_blank");
}

// ---------------------------------------------------------------------------
// Edit
// ---------------------------------------------------------------------------
let _editOriginalContent = null;

function editSkill() {
    if (!currentSkillId) return;
    const skill = skills.find(s => s.id === currentSkillId);
    if (!skill) return;

    _editOriginalContent = skill.content;

    const editor = document.getElementById("skill-editor");
    editor.value = skill.content;
    // Auto-size rows to content
    editor.rows = Math.max(20, skill.content.split("\n").length + 2);

    document.getElementById("skill-content").classList.add("hidden");
    editor.classList.remove("hidden");
    document.getElementById("skill-actions").classList.add("hidden");
    document.getElementById("edit-actions").classList.remove("hidden");
    document.getElementById("edit-actions").classList.add("flex");
    editor.focus();
}

async function saveSkill() {
    if (!currentSkillId) return;
    const content = document.getElementById("skill-editor").value;
    try {
        const updated = await api(`/skills/${currentSkillId}`, {
            method: "PUT",
            body: JSON.stringify({ content }),
        });
        // Patch local cache
        const idx = skills.findIndex(s => s.id === currentSkillId);
        if (idx !== -1) skills[idx].content = content;
        _editOriginalContent = null;
        _exitEditMode();
        document.getElementById("skill-content").innerHTML = marked.parse(content);
    } catch (e) {
        alert("Save failed: " + e.message);
    }
}

function cancelEdit() {
    _exitEditMode();
    if (_editOriginalContent !== null) {
        document.getElementById("skill-content").innerHTML = marked.parse(_editOriginalContent);
        _editOriginalContent = null;
    }
}

function _exitEditMode() {
    document.getElementById("skill-editor").classList.add("hidden");
    document.getElementById("skill-content").classList.remove("hidden");
    document.getElementById("edit-actions").classList.add("hidden");
    document.getElementById("edit-actions").classList.remove("flex");
    document.getElementById("skill-actions").classList.remove("hidden");
}

// ---------------------------------------------------------------------------
// Archive
// ---------------------------------------------------------------------------
async function archiveSkill() {
    if (!currentSkillId || !confirm("Archive this skill?")) return;
    try {
        await api(`/skills/${currentSkillId}/archive`, { method: "POST" });
        await loadSkills();
        showCreateView();
    } catch (e) {
        alert("Archive failed: " + e.message);
    }
}

// ---------------------------------------------------------------------------
// Test
// ---------------------------------------------------------------------------
async function testSkill() {
    if (!currentSkillId) return;
    const btn = document.getElementById("test-btn");
    btn.disabled = true;
    btn.innerHTML = `
        <svg class="animate-spin h-5 w-5" xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24">
            <circle class="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" stroke-width="4"></circle>
            <path class="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z"></path>
        </svg>
        <span>Testing…</span>`;

    try {
        const result = await api(`/skills/${currentSkillId}/test`, { method: "POST" });
        document.getElementById("test-content").innerHTML = marked.parse(result.test_result || "");
        document.getElementById("test-results").classList.remove("hidden");
        document.getElementById("test-results").scrollIntoView({ behavior: "smooth", block: "start" });
    } catch (e) {
        alert("Test failed: " + e.message);
    } finally {
        btn.disabled = false;
        btn.innerHTML = `<span class="material-symbols-outlined" style="font-size:20px">science</span> Test Skill`;
    }
}

// ---------------------------------------------------------------------------
// Utility — shake animation for empty input
// ---------------------------------------------------------------------------
function shakeElement(el) {
    el.classList.add("ring-2", "ring-google-red/50");
    el.style.animation = "none";
    el.offsetHeight; // reflow
    el.style.animation = "shake 0.4s ease-in-out";
    setTimeout(() => {
        el.classList.remove("ring-2", "ring-google-red/50");
        el.style.animation = "";
    }, 500);
}

// Inject shake keyframes
const style = document.createElement("style");
style.textContent = `@keyframes shake{0%,100%{transform:translateX(0)}25%{transform:translateX(-6px)}50%{transform:translateX(6px)}75%{transform:translateX(-4px)}}`;
document.head.appendChild(style);
