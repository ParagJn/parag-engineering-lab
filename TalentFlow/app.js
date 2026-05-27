/* app.js — TalentFlow Application Logic */
(function () {
  'use strict';

  const CGI_BIN = './cgi-bin';

  // ============================================
  // STATE
  // ============================================
  const state = {
    currentView: 'search',
    jdText: '',
    parsedJD: null,
    candidates: [],
    pipelineData: [],
    selectedCandidate: null,
    outreachMessages: null,
    outreachCandidate: null,
    theme: 'light',
    loading: false,
    filters: {
      location: 'all',
      min_yoe: null,
      max_yoe: null,
      skills: [],
      open_to_work: false,
    },
    analytics: {
      messagesDrafted: 47,
      messagesSent: 32,
      responseRate: 28,
      avgTimeToResponse: '2.4d',
    },
  };

  // ============================================
  // ICONS (Lucide-style inline SVG)
  // ============================================
  const icons = {
    search: '<svg xmlns="http://www.w3.org/2000/svg" width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.75" stroke-linecap="round" stroke-linejoin="round"><circle cx="11" cy="11" r="8"/><path d="m21 21-4.3-4.3"/></svg>',
    kanban: '<svg xmlns="http://www.w3.org/2000/svg" width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.75" stroke-linecap="round" stroke-linejoin="round"><rect width="6" height="14" x="4" y="5" rx="2"/><rect width="6" height="10" x="14" y="7" rx="2"/></svg>',
    mail: '<svg xmlns="http://www.w3.org/2000/svg" width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.75" stroke-linecap="round" stroke-linejoin="round"><rect width="20" height="16" x="2" y="4" rx="2"/><path d="m22 7-8.97 5.7a1.94 1.94 0 0 1-2.06 0L2 7"/></svg>',
    chart: '<svg xmlns="http://www.w3.org/2000/svg" width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.75" stroke-linecap="round" stroke-linejoin="round"><path d="M3 3v18h18"/><path d="m19 9-5 5-4-4-3 3"/></svg>',
    mapPin: '<svg xmlns="http://www.w3.org/2000/svg" width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M20 10c0 6-8 12-8 12s-8-6-8-12a8 8 0 0 1 16 0Z"/><circle cx="12" cy="10" r="3"/></svg>',
    briefcase: '<svg xmlns="http://www.w3.org/2000/svg" width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M16 20V4a2 2 0 0 0-2-2h-4a2 2 0 0 0-2 2v16"/><rect width="20" height="14" x="2" y="6" rx="2"/></svg>',
    clock: '<svg xmlns="http://www.w3.org/2000/svg" width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="12" r="10"/><polyline points="12 6 12 12 16 14"/></svg>',
    check: '<svg xmlns="http://www.w3.org/2000/svg" width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M20 6 9 17l-5-5"/></svg>',
    checkCircle: '<svg xmlns="http://www.w3.org/2000/svg" width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M22 11.08V12a10 10 0 1 1-5.93-9.14"/><path d="m9 11 3 3L22 4"/></svg>',
    x: '<svg xmlns="http://www.w3.org/2000/svg" width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M18 6 6 18"/><path d="m6 6 12 12"/></svg>',
    sun: '<svg xmlns="http://www.w3.org/2000/svg" width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="12" r="5"/><path d="M12 1v2M12 21v2M4.22 4.22l1.42 1.42M18.36 18.36l1.42 1.42M1 12h2M21 12h2M4.22 19.78l1.42-1.42M18.36 5.64l1.42-1.42"/></svg>',
    moon: '<svg xmlns="http://www.w3.org/2000/svg" width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M21 12.79A9 9 0 1 1 11.21 3 7 7 0 0 0 21 12.79z"/></svg>',
    arrowUp: '<svg xmlns="http://www.w3.org/2000/svg" width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round"><path d="m5 12 7-7 7 7"/><path d="M12 19V5"/></svg>',
    arrowDown: '<svg xmlns="http://www.w3.org/2000/svg" width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round"><path d="m19 12-7 7-7-7"/><path d="M12 5v14"/></svg>',
    linkedin: '<svg xmlns="http://www.w3.org/2000/svg" width="14" height="14" viewBox="0 0 24 24" fill="currentColor"><path d="M20.447 20.452h-3.554v-5.569c0-1.328-.027-3.037-1.852-3.037-1.853 0-2.136 1.445-2.136 2.939v5.667H9.351V9h3.414v1.561h.046c.477-.9 1.637-1.85 3.37-1.85 3.601 0 4.267 2.37 4.267 5.455v6.286zM5.337 7.433c-1.144 0-2.063-.926-2.063-2.065 0-1.138.92-2.063 2.063-2.063 1.14 0 2.064.925 2.064 2.063 0 1.139-.925 2.065-2.064 2.065zm1.782 13.019H3.555V9h3.564v11.452zM22.225 0H1.771C.792 0 0 .774 0 1.729v20.542C0 23.227.792 24 1.771 24h20.451C23.2 24 24 23.227 24 22.271V1.729C24 .774 23.2 0 22.222 0h.003z"/></svg>',
    github: '<svg xmlns="http://www.w3.org/2000/svg" width="14" height="14" viewBox="0 0 24 24" fill="currentColor"><path d="M12 0c-6.626 0-12 5.373-12 12 0 5.302 3.438 9.8 8.207 11.387.599.111.793-.261.793-.577v-2.234c-3.338.726-4.033-1.416-4.033-1.416-.546-1.387-1.333-1.756-1.333-1.756-1.089-.745.083-.729.083-.729 1.205.084 1.839 1.237 1.839 1.237 1.07 1.834 2.807 1.304 3.492.997.107-.775.418-1.305.762-1.604-2.665-.305-5.467-1.334-5.467-5.931 0-1.311.469-2.381 1.236-3.221-.124-.303-.535-1.524.117-3.176 0 0 1.008-.322 3.301 1.23.957-.266 1.983-.399 3.003-.404 1.02.005 2.047.138 3.006.404 2.291-1.552 3.297-1.23 3.297-1.23.653 1.653.242 2.874.118 3.176.77.84 1.235 1.911 1.235 3.221 0 4.609-2.807 5.624-5.479 5.921.43.372.823 1.102.823 2.222v3.293c0 .319.192.694.801.576 4.765-1.589 8.199-6.086 8.199-11.386 0-6.627-5.373-12-12-12z"/></svg>',
    users: '<svg xmlns="http://www.w3.org/2000/svg" width="48" height="48" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"><path d="M16 21v-2a4 4 0 0 0-4-4H6a4 4 0 0 0-4 4v2"/><circle cx="9" cy="7" r="4"/><path d="M22 21v-2a4 4 0 0 0-3-3.87"/><path d="M16 3.13a4 4 0 0 1 0 7.75"/></svg>',
    send: '<svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="m22 2-7 20-4-9-9-4Z"/><path d="M22 2 11 13"/></svg>',
    copy: '<svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><rect width="14" height="14" x="8" y="8" rx="2" ry="2"/><path d="M4 16c-1.1 0-2-.9-2-2V4c0-1.1.9-2 2-2h10c1.1 0 2 .9 2 2"/></svg>',
    refresh: '<svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M21 12a9 9 0 0 0-9-9 9.75 9.75 0 0 0-6.74 2.74L3 8"/><path d="M3 3v5h5"/><path d="M3 12a9 9 0 0 0 9 9 9.75 9.75 0 0 0 6.74-2.74L21 16"/><path d="M16 16h5v5"/></svg>',
    fileText: '<svg xmlns="http://www.w3.org/2000/svg" width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M15 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V7Z"/><path d="M14 2v4a2 2 0 0 0 2 2h4"/><path d="M10 9H8"/><path d="M16 13H8"/><path d="M16 17H8"/></svg>',
    sparkles: '<svg xmlns="http://www.w3.org/2000/svg" width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="m12 3-1.912 5.813a2 2 0 0 1-1.275 1.275L3 12l5.813 1.912a2 2 0 0 1 1.275 1.275L12 21l1.912-5.813a2 2 0 0 1 1.275-1.275L21 12l-5.813-1.912a2 2 0 0 1-1.275-1.275L12 3Z"/><path d="M5 3v4"/><path d="M19 17v4"/><path d="M3 5h4"/><path d="M17 19h4"/></svg>',
    menu: '<svg xmlns="http://www.w3.org/2000/svg" width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><line x1="4" x2="20" y1="12" y2="12"/><line x1="4" x2="20" y1="6" y2="6"/><line x1="4" x2="20" y1="18" y2="18"/></svg>',
    userPlus: '<svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M16 21v-2a4 4 0 0 0-4-4H6a4 4 0 0 0-4 4v2"/><circle cx="9" cy="7" r="4"/><line x1="19" x2="19" y1="8" y2="14"/><line x1="22" x2="16" y1="11" y2="11"/></svg>',
    inbox: '<svg xmlns="http://www.w3.org/2000/svg" width="48" height="48" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"><polyline points="22 12 16 12 14 15 10 15 8 12 2 12"/><path d="M5.45 5.11 2 12v6a2 2 0 0 0 2 2h16a2 2 0 0 0 2-2v-6l-3.45-6.89A2 2 0 0 0 16.76 4H7.24a2 2 0 0 0-1.79 1.11z"/></svg>',
    trendUp: '<svg xmlns="http://www.w3.org/2000/svg" width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><polyline points="22 7 13.5 15.5 8.5 10.5 2 17"/><polyline points="16 7 22 7 22 13"/></svg>',
    star: '<svg xmlns="http://www.w3.org/2000/svg" width="12" height="12" viewBox="0 0 24 24" fill="currentColor" stroke="currentColor" stroke-width="1"><polygon points="12 2 15.09 8.26 22 9.27 17 14.14 18.18 21.02 12 17.77 5.82 21.02 7 14.14 2 9.27 8.91 8.26 12 2"/></svg>',
  };

  // ============================================
  // HELPERS
  // ============================================
  function $(sel, ctx) { return (ctx || document).querySelector(sel); }
  function $$(sel, ctx) { return Array.from((ctx || document).querySelectorAll(sel)); }

  function el(tag, attrs, children) {
    const e = document.createElement(tag);
    if (attrs) {
      Object.entries(attrs).forEach(([k, v]) => {
        if (k === 'className') e.className = v;
        else if (k === 'innerHTML') e.innerHTML = v;
        else if (k.startsWith('on')) e.addEventListener(k.slice(2).toLowerCase(), v);
        else if (k === 'dataset') Object.entries(v).forEach(([dk, dv]) => e.dataset[dk] = dv);
        else e.setAttribute(k, v);
      });
    }
    if (children) {
      if (typeof children === 'string') e.innerHTML = children;
      else if (Array.isArray(children)) children.forEach(c => { if (c) e.appendChild(c); });
      else e.appendChild(children);
    }
    return e;
  }

  async function api(path, method = 'GET', body = null) {
    const opts = { method, headers: {} };
    if (body) {
      opts.headers['Content-Type'] = 'application/json';
      opts.body = JSON.stringify(body);
    }
    try {
      const res = await fetch(`${CGI_BIN}/api.py${path}`, opts);
      return await res.json();
    } catch (err) {
      console.error('API Error:', err);
      showToast('Connection error', 'error');
      return null;
    }
  }

  function showToast(message, type = 'success') {
    const container = $('.toast-container');
    const icon = type === 'success' ? icons.checkCircle : icons.x;
    const toast = el('div', { className: `toast toast-${type}` }, `${icon}<span>${message}</span>`);
    container.appendChild(toast);
    setTimeout(() => {
      toast.style.animation = 'toastOut 300ms cubic-bezier(0.16, 1, 0.3, 1) forwards';
      setTimeout(() => toast.remove(), 300);
    }, 3000);
  }

  function getRelevanceColor(score) {
    if (score >= 80) return 'var(--color-success)';
    if (score >= 60) return 'var(--color-primary)';
    if (score >= 40) return 'var(--color-orange)';
    return 'var(--color-text-faint)';
  }

  // ============================================
  // THEME TOGGLE
  // ============================================
  function initTheme() {
    state.theme = window.matchMedia('(prefers-color-scheme: dark)').matches ? 'dark' : 'light';
    document.documentElement.setAttribute('data-theme', state.theme);
    updateThemeIcon();
  }

  function toggleTheme() {
    state.theme = state.theme === 'dark' ? 'light' : 'dark';
    document.documentElement.setAttribute('data-theme', state.theme);
    updateThemeIcon();
    // Redraw charts if they exist
    if (state.currentView === 'analytics') renderAnalyticsCharts();
  }

  function updateThemeIcon() {
    const btn = $('#theme-toggle');
    if (btn) btn.innerHTML = state.theme === 'dark' ? icons.sun : icons.moon;
  }

  // ============================================
  // NAVIGATION
  // ============================================
  function navigate(view) {
    state.currentView = view;
    window.location.hash = view;

    // Update nav
    $$('.nav-item').forEach(n => n.classList.toggle('active', n.dataset.view === view));

    // Update views
    $$('.view').forEach(v => v.classList.toggle('active', v.id === `view-${view}`));

    // Update header title
    const titles = { search: 'Candidate Search', pipeline: 'Pipeline', outreach: 'Outreach', analytics: 'Analytics' };
    $('#header-title').textContent = titles[view] || 'Search';

    // Load view-specific data
    if (view === 'pipeline') loadPipeline();
    if (view === 'analytics') renderAnalytics();
    if (view === 'outreach' && !state.outreachCandidate) renderOutreachEmpty();

    // Close mobile sidebar
    $('.sidebar').classList.remove('mobile-open');
  }

  // ============================================
  // SEARCH VIEW
  // ============================================
  async function parseJD() {
    const jdText = $('#jd-textarea').value.trim();
    if (!jdText) {
      showToast('Enter a job description', 'error');
      return;
    }
    state.jdText = jdText;
    state.loading = true;
    showSearchLoading();

    const result = await api('/parse-jd', 'POST', { jd: jdText });
    state.loading = false;

    if (result && !result.error) {
      state.parsedJD = result;
      renderParsedJD(result);
      showToast('Job description parsed');
    } else {
      showToast(result?.error || 'Failed to parse JD', 'error');
    }
  }

  function renderParsedJD(data) {
    const container = $('#parsed-jd');
    container.innerHTML = '';
    container.classList.add('visible');

    const header = el('div', { className: 'parsed-jd-header' });
    header.innerHTML = `<div class="parsed-jd-title">${icons.checkCircle} Requirements Extracted</div>`;
    container.appendChild(header);

    const grid = el('div', { className: 'parsed-jd-grid' });
    const fields = [
      { label: 'Role Type', value: data.role_type },
      { label: 'Seniority', value: data.seniority },
      { label: 'Experience', value: `${data.yoe_range[0]}-${data.yoe_range[1]} years` },
      { label: 'Location', value: data.locations.join(', ') },
      { label: 'Education', value: data.education },
    ];
    if (data.salary_range) fields.push({ label: 'Salary', value: data.salary_range });

    fields.forEach(f => {
      const field = el('div', { className: 'parsed-field' });
      field.innerHTML = `<span class="parsed-field-label">${f.label}</span><span class="parsed-field-value">${f.value}</span>`;
      grid.appendChild(field);
    });
    container.appendChild(grid);

    if (data.skills && data.skills.length) {
      const skillsSection = el('div', { className: 'parsed-skills' });
      skillsSection.innerHTML = '<div class="parsed-skills-label">Matched Skills</div>';
      const tagsWrap = el('div', { className: 'skills-tags' });
      data.skills.forEach(skill => {
        const tag = el('span', { className: 'skill-tag matched' });
        tag.textContent = skill;
        tagsWrap.appendChild(tag);
      });
      skillsSection.appendChild(tagsWrap);
      container.appendChild(skillsSection);
    }

    // Show filter bar
    $('#filter-bar').classList.add('visible');
  }

  async function searchCandidates() {
    if (!state.parsedJD) {
      await parseJD();
      if (!state.parsedJD) return;
    }

    state.loading = true;
    showCandidateSkeletons();

    const filters = {
      location: $('#filter-location')?.value || 'all',
      min_yoe: $('#filter-yoe-min')?.value ? parseInt($('#filter-yoe-min').value) : null,
      max_yoe: $('#filter-yoe-max')?.value ? parseInt($('#filter-yoe-max').value) : null,
      open_to_work: $('#filter-open')?.checked || false,
    };

    const result = await api('/search', 'POST', {
      parsed_jd: state.parsedJD,
      filters: filters,
      count: 12,
    });

    state.loading = false;

    if (result && result.candidates) {
      state.candidates = result.candidates;
      renderCandidates(result.candidates);
      showToast(`Found ${result.total} candidates`);
    } else {
      showToast('Search failed', 'error');
    }
  }

  function showSearchLoading() {
    const container = $('#candidates-grid');
    container.innerHTML = '';
    // Don't show skeletons during parse-only
  }

  function showCandidateSkeletons() {
    const container = $('#candidates-grid');
    container.innerHTML = '';
    for (let i = 0; i < 6; i++) {
      const card = el('div', { className: 'skeleton-card' });
      card.innerHTML = `
        <div style="display:flex;gap:16px;margin-bottom:16px">
          <div class="skeleton skeleton-circle"></div>
          <div style="flex:1;display:flex;flex-direction:column;gap:8px">
            <div class="skeleton skeleton-line w-60"></div>
            <div class="skeleton skeleton-line w-40"></div>
          </div>
        </div>
        <div style="display:flex;flex-wrap:wrap;gap:8px;margin-bottom:16px">
          <div class="skeleton skeleton-line" style="width:60px;height:20px;border-radius:9999px"></div>
          <div class="skeleton skeleton-line" style="width:80px;height:20px;border-radius:9999px"></div>
          <div class="skeleton skeleton-line" style="width:50px;height:20px;border-radius:9999px"></div>
        </div>
        <div style="display:flex;flex-wrap:wrap;gap:4px;margin-bottom:16px">
          <div class="skeleton skeleton-line" style="width:50px;height:18px;border-radius:9999px"></div>
          <div class="skeleton skeleton-line" style="width:70px;height:18px;border-radius:9999px"></div>
          <div class="skeleton skeleton-line" style="width:60px;height:18px;border-radius:9999px"></div>
          <div class="skeleton skeleton-line" style="width:45px;height:18px;border-radius:9999px"></div>
        </div>
        <div class="skeleton skeleton-line w-full" style="height:40px;margin-top:12px"></div>
      `;
      container.appendChild(card);
    }
    $('#results-header').classList.add('visible');
    $('#results-count').textContent = 'Searching...';
  }

  function renderCandidates(candidates) {
    const container = $('#candidates-grid');
    container.innerHTML = '';
    $('#results-header').classList.add('visible');
    $('#results-count').textContent = `${candidates.length} candidates found`;

    if (!candidates.length) {
      container.innerHTML = `<div class="empty-state" style="grid-column:1/-1">${icons.users}<h3>No candidates found</h3><p>Try adjusting your filters or broadening the job description.</p></div>`;
      return;
    }

    candidates.forEach((c, idx) => {
      const card = createCandidateCard(c, idx);
      container.appendChild(card);
    });
  }

  function createCandidateCard(c, idx) {
    const card = el('div', { className: 'candidate-card' });
    const circumference = 2 * Math.PI * 18;
    const dashOffset = circumference - (c.relevance_score / 100) * circumference;
    const color = getRelevanceColor(c.relevance_score);

    let githubHTML = '';
    if (c.github_data) {
      githubHTML = `
        <div class="github-activity">
          <div class="github-activity-header">${icons.github} Code Activity</div>
          <div class="github-stats">
            <div class="github-stat"><span class="github-stat-value">${c.github_data.repos}</span><span class="github-stat-label">Repos</span></div>
            <div class="github-stat"><span class="github-stat-value">${c.github_data.contributions.toLocaleString()}</span><span class="github-stat-label">Contrib</span></div>
            <div class="github-stat"><span class="github-stat-value">${c.github_data.stars}</span><span class="github-stat-label">Stars</span></div>
          </div>
          <div class="activity-bar"><div class="activity-bar-fill" style="width:${c.github_data.activity_score}%"></div></div>
        </div>`;
    }

    const matchedSet = new Set(c.matching_skills || []);
    const skillsHTML = c.skills.map(s =>
      `<span class="card-skill ${matchedSet.has(s) ? 'matched' : ''}">${s}</span>`
    ).join('');

    let linksHTML = `<a href="${c.linkedin_url}" target="_blank" rel="noopener noreferrer" class="card-link linkedin">${icons.linkedin} LinkedIn</a>`;
    if (c.github_url) {
      linksHTML += `<a href="${c.github_url}" target="_blank" rel="noopener noreferrer" class="card-link github">${icons.github} GitHub</a>`;
    }

    card.innerHTML = `
      <div class="card-top">
        <div class="card-avatar" style="background:${c.avatar_color}">${c.initials}</div>
        <div class="card-info">
          <div class="card-name">${c.name}</div>
          <div class="card-headline">${c.headline}</div>
        </div>
        <div class="card-relevance">
          <svg width="46" height="46" viewBox="0 0 46 46">
            <circle class="card-relevance-bg" cx="23" cy="23" r="18"/>
            <circle class="card-relevance-fill card-relevance-circle" cx="23" cy="23" r="18"
              stroke="${color}"
              stroke-dasharray="${circumference}"
              stroke-dashoffset="${dashOffset}"/>
            <text class="card-relevance-text" x="23" y="23">${c.relevance_score}%</text>
          </svg>
        </div>
      </div>
      <div class="card-meta">
        <span class="meta-badge">${icons.mapPin} ${c.location}</span>
        <span class="meta-badge">${icons.briefcase} ${c.yoe} yrs</span>
        <span class="meta-badge">${icons.clock} ${c.tenure_display}</span>
        ${c.open_to_work ? '<span class="meta-badge open-to-work">Open to Work</span>' : ''}
        <span class="meta-badge company-tier">${c.company_tier}</span>
      </div>
      <div class="card-skills">${skillsHTML}</div>
      ${githubHTML}
      <div class="card-links">${linksHTML}</div>
      <div class="card-actions">
        <button class="btn btn-primary btn-sm" style="flex:1" data-action="outreach" data-idx="${idx}">${icons.mail} Draft Outreach</button>
        <button class="btn btn-secondary btn-sm" style="flex:1" data-action="pipeline" data-idx="${idx}">${icons.userPlus} Add to Pipeline</button>
      </div>
    `;

    // Animate relevance circle on mount
    const fill = card.querySelector('.card-relevance-fill');
    if (fill) {
      fill.style.strokeDashoffset = circumference;
      requestAnimationFrame(() => {
        requestAnimationFrame(() => {
          fill.style.strokeDashoffset = dashOffset;
        });
      });
    }

    // Button handlers
    card.querySelector('[data-action="outreach"]').addEventListener('click', () => {
      startOutreach(c);
    });

    card.querySelector('[data-action="pipeline"]').addEventListener('click', async () => {
      const result = await api('/pipeline', 'POST', { action: 'add', candidate: c });
      if (result && result.success) {
        showToast(`${c.name} added to pipeline`);
        updatePipelineBadge();
      } else if (result && result.error) {
        showToast(result.error, 'error');
      }
    });

    return card;
  }

  // ============================================
  // PIPELINE VIEW
  // ============================================
  const STAGES = ['sourced', 'contacted', 'responded', 'interview', 'offer', 'hired'];
  const STAGE_LABELS = {
    sourced: 'Sourced', contacted: 'Contacted', responded: 'Responded',
    interview: 'Interview', offer: 'Offer', hired: 'Hired'
  };

  async function loadPipeline() {
    // Immediately render columns (even empty) so the board is visible
    renderPipeline(state.pipelineData || []);
    const result = await api('/pipeline');
    if (result && result.pipeline) {
      state.pipelineData = result.pipeline;
      renderPipeline(result.pipeline);
    }
  }

  function renderPipeline(data) {
    const board = $('#pipeline-board');
    board.innerHTML = '';

    STAGES.forEach(stage => {
      const items = data.filter(d => d.stage === stage);
      const col = el('div', { className: 'pipeline-column', dataset: { stage } });

      col.innerHTML = `
        <div class="pipeline-column-header">
          <span class="pipeline-column-title">${STAGE_LABELS[stage]}</span>
          <span class="pipeline-count">${items.length}</span>
        </div>`;

      const body = el('div', { className: 'pipeline-column-body' });

      if (items.length === 0) {
        body.innerHTML = `<div class="pipeline-empty">${icons.inbox}<p>No candidates</p></div>`;
      } else {
        items.forEach(item => {
          const card = createPipelineCard(item);
          body.appendChild(card);
        });
      }

      col.appendChild(body);

      // Drag and drop
      body.addEventListener('dragover', e => {
        e.preventDefault();
        col.classList.add('drag-over');
      });

      body.addEventListener('dragleave', () => {
        col.classList.remove('drag-over');
      });

      body.addEventListener('drop', async e => {
        e.preventDefault();
        col.classList.remove('drag-over');
        const candidateId = e.dataTransfer.getData('text/plain');
        if (candidateId) {
          await api('/pipeline', 'POST', { action: 'move', id: candidateId, stage });
          await loadPipeline();
          showToast(`Moved to ${STAGE_LABELS[stage]}`);
        }
      });

      board.appendChild(col);
    });
  }

  function createPipelineCard(item) {
    const card = el('div', {
      className: 'pipeline-card',
      draggable: 'true',
      dataset: { id: item.id || item.pipeline_id },
    });

    const tags = (item.tags || []).map(t => `<span class="pipeline-card-tag">${t}</span>`).join('');
    const hasNotes = item.notes && item.notes.trim();

    card.innerHTML = `
      <div class="pipeline-card-name">${item.name}</div>
      <div class="pipeline-card-role">${item.title || item.headline || ''} · ${item.company || ''}</div>
      <div class="pipeline-card-meta">
        ${tags}
        ${hasNotes ? `<span class="pipeline-card-notes-icon">${icons.fileText}</span>` : ''}
      </div>
    `;

    card.addEventListener('dragstart', e => {
      e.dataTransfer.setData('text/plain', item.id || item.pipeline_id);
      card.classList.add('dragging');
    });

    card.addEventListener('dragend', () => {
      card.classList.remove('dragging');
    });

    card.addEventListener('click', () => {
      openCandidateModal(item);
    });

    return card;
  }

  // ============================================
  // CANDIDATE DETAIL MODAL
  // ============================================
  function openCandidateModal(candidate) {
    state.selectedCandidate = candidate;
    const overlay = $('#modal-overlay');
    overlay.classList.add('visible');

    const modal = $('#modal');
    const title = modal.querySelector('.modal-title');
    title.textContent = candidate.name;

    // Stage select
    const stageSelect = $('#modal-stage-select');
    stageSelect.value = candidate.stage || 'sourced';

    // Notes
    const notesArea = $('#modal-notes');
    notesArea.value = candidate.notes || '';

    // Tags
    renderModalTags(candidate.tags || []);

    // Outreach history
    const historyContainer = $('#modal-outreach-history');
    const history = candidate.outreach_history || [];
    if (history.length) {
      historyContainer.innerHTML = history.map(h =>
        `<div style="padding:8px 0;border-bottom:1px solid var(--color-divider);font-size:13px">
          <strong>${h.type || 'Email'}</strong> — ${h.subject || 'No subject'}<br>
          <span style="color:var(--color-text-muted)">${h.date || 'Unknown date'}</span>
        </div>`
      ).join('');
    } else {
      historyContainer.innerHTML = '<p style="color:var(--color-text-faint);font-size:13px">No outreach history</p>';
    }
  }

  function renderModalTags(tags) {
    const container = $('#modal-tags-container');
    container.innerHTML = '';
    tags.forEach(tag => {
      const tagEl = el('span', { className: 'modal-tag' });
      tagEl.innerHTML = `${tag}<span class="modal-tag-remove" data-tag="${tag}">${icons.x}</span>`;
      tagEl.querySelector('.modal-tag-remove').addEventListener('click', (e) => {
        e.stopPropagation();
        const updated = tags.filter(t => t !== tag);
        if (state.selectedCandidate) state.selectedCandidate.tags = updated;
        renderModalTags(updated);
      });
      container.appendChild(tagEl);
    });

    // Add input
    const input = el('input', {
      className: 'modal-tag-input',
      placeholder: 'Add tag...',
      type: 'text',
    });
    input.addEventListener('keydown', e => {
      if (e.key === 'Enter' && input.value.trim()) {
        const newTag = input.value.trim();
        tags.push(newTag);
        if (state.selectedCandidate) state.selectedCandidate.tags = tags;
        renderModalTags(tags);
      }
    });
    container.appendChild(input);
  }

  async function saveModalChanges() {
    if (!state.selectedCandidate) return;
    const cid = state.selectedCandidate.id || state.selectedCandidate.pipeline_id;
    const stage = $('#modal-stage-select').value;
    const notes = $('#modal-notes').value;
    const tags = state.selectedCandidate.tags || [];

    await api('/pipeline', 'POST', { action: 'move', id: cid, stage });
    await api('/pipeline', 'POST', { action: 'update_notes', id: cid, notes });
    await api('/pipeline', 'POST', { action: 'update_tags', id: cid, tags });

    showToast('Changes saved');
    closeModal();
    if (state.currentView === 'pipeline') loadPipeline();
  }

  function closeModal() {
    $('#modal-overlay').classList.remove('visible');
    state.selectedCandidate = null;
  }

  // ============================================
  // OUTREACH VIEW
  // ============================================
  function startOutreach(candidate) {
    state.outreachCandidate = candidate;
    navigate('outreach');
    renderOutreachForm(candidate);
    generateOutreach();
  }

  function renderOutreachEmpty() {
    const main = $('#outreach-main');
    if (!state.outreachCandidate) {
      main.innerHTML = `<div class="outreach-empty">${icons.mail}<h3>No candidate selected</h3><p>Select a candidate from Search or Pipeline to draft outreach.</p></div>`;
    }
  }

  function renderOutreachForm(candidate) {
    // Update candidate selector display
    const selector = $('#outreach-candidate-select');
    selector.innerHTML = `<option value="${candidate.id}" selected>${candidate.name} — ${candidate.title} at ${candidate.company}</option>`;

    // Add pipeline candidates
    state.pipelineData.forEach(p => {
      if (p.id !== candidate.id) {
        const opt = el('option', { value: p.id });
        opt.textContent = `${p.name} — ${p.title || ''} at ${p.company || ''}`;
        selector.appendChild(opt);
      }
    });
  }

  async function generateOutreach() {
    if (!state.outreachCandidate) return;

    const tone = getToneFromSlider();
    const length = getSelectedLength();
    const msgType = getSelectedMsgType();

    const main = $('#outreach-main');
    main.innerHTML = `
      <div class="outreach-tabs">
        <button class="outreach-tab active" data-tab="initial">Initial Message</button>
        <button class="outreach-tab" data-tab="followup1">Follow-up 1 (3d)</button>
        <button class="outreach-tab" data-tab="followup2">Follow-up 2 (7d)</button>
      </div>
      <div class="outreach-composer" id="outreach-composer">
        <div style="display:flex;align-items:center;gap:8px;color:var(--color-text-faint)">
          ${icons.sparkles} <span style="font-size:13px">Generating outreach...</span>
        </div>
      </div>
      <div class="outreach-actions">
        <button class="btn btn-primary" id="outreach-send">${icons.send} Send</button>
        <button class="btn btn-secondary" id="outreach-copy">${icons.copy} Copy</button>
        <button class="btn btn-ghost" id="outreach-regen">${icons.refresh} Regenerate</button>
      </div>
    `;

    const result = await api('/draft-outreach', 'POST', {
      candidate: state.outreachCandidate,
      tone,
      length,
      type: msgType,
      jd_text: state.jdText,
    });

    if (result && !result.error) {
      state.outreachMessages = result;
      renderOutreachMessage('initial');

      // Tab handlers
      main.querySelectorAll('.outreach-tab').forEach(tab => {
        tab.addEventListener('click', () => {
          main.querySelectorAll('.outreach-tab').forEach(t => t.classList.remove('active'));
          tab.classList.add('active');
          renderOutreachMessage(tab.dataset.tab);
        });
      });

      // Action handlers
      main.querySelector('#outreach-send').addEventListener('click', () => {
        showToast('Message sent!');
      });

      main.querySelector('#outreach-copy').addEventListener('click', () => {
        const body = $('#outreach-body-text');
        if (body) {
          navigator.clipboard.writeText(body.value).catch(() => {});
          showToast('Copied to clipboard');
        }
      });

      main.querySelector('#outreach-regen').addEventListener('click', () => {
        generateOutreach();
      });
    }
  }

  function renderOutreachMessage(tab) {
    if (!state.outreachMessages) return;
    const composer = $('#outreach-composer');
    const m = state.outreachMessages;

    let subject = m.subject;
    let body = m.body;

    if (tab === 'followup1') {
      subject = `Re: ${m.subject}`;
      body = m.followup_1;
    } else if (tab === 'followup2') {
      subject = `Re: ${m.subject}`;
      body = m.followup_2;
    }

    composer.innerHTML = `
      <input class="outreach-subject" id="outreach-subject-text" value="${subject.replace(/"/g, '&quot;')}" placeholder="Subject line">
      <textarea class="outreach-body" id="outreach-body-text" placeholder="Message body">${body}</textarea>
    `;
  }

  function getToneFromSlider() {
    const val = parseInt($('#tone-slider')?.value || '50');
    if (val <= 33) return 'casual';
    if (val <= 66) return 'professional';
    return 'formal';
  }

  function getSelectedLength() {
    const active = $('.toggle-group.length-group .toggle-btn.active');
    return active ? active.dataset.value : 'medium';
  }

  function getSelectedMsgType() {
    const active = $('.toggle-group.type-group .toggle-btn.active');
    return active ? active.dataset.value : 'email';
  }

  // ============================================
  // ANALYTICS VIEW
  // ============================================
  function renderAnalytics() {
    const a = state.analytics;

    // KPI values
    $('#kpi-drafted').textContent = a.messagesDrafted;
    $('#kpi-sent').textContent = a.messagesSent;
    $('#kpi-response').textContent = a.responseRate + '%';
    $('#kpi-time').textContent = a.avgTimeToResponse;

    renderAnalyticsCharts();
  }

  function renderAnalyticsCharts() {
    if (typeof Chart === 'undefined') return;

    const textColor = getComputedStyle(document.documentElement).getPropertyValue('--color-text').trim();
    const mutedColor = getComputedStyle(document.documentElement).getPropertyValue('--color-text-muted').trim();
    const borderColor = getComputedStyle(document.documentElement).getPropertyValue('--color-divider').trim();

    Chart.defaults.color = mutedColor;
    Chart.defaults.borderColor = borderColor;
    Chart.defaults.font.family = "'DM Sans', sans-serif";

    // Destroy existing charts
    Chart.helpers.each(Chart.instances, (instance) => { instance.destroy(); });

    // Funnel Chart
    const funnelCtx = document.getElementById('chart-funnel');
    if (funnelCtx) {
      new Chart(funnelCtx, {
        type: 'bar',
        data: {
          labels: ['Drafted', 'Sent', 'Opened', 'Replied'],
          datasets: [{
            data: [47, 32, 21, 9],
            backgroundColor: [
              getComputedStyle(document.documentElement).getPropertyValue('--color-blue').trim(),
              getComputedStyle(document.documentElement).getPropertyValue('--color-primary').trim(),
              getComputedStyle(document.documentElement).getPropertyValue('--color-orange').trim(),
              getComputedStyle(document.documentElement).getPropertyValue('--color-success').trim(),
            ],
            borderRadius: 6,
            barPercentage: 0.6,
          }],
        },
        options: {
          responsive: true,
          maintainAspectRatio: false,
          plugins: { legend: { display: false } },
          scales: {
            y: { beginAtZero: true, grid: { display: true, color: borderColor } },
            x: { grid: { display: false } },
          },
        },
      });
    }

    // Pipeline Doughnut
    const pipeCtx = document.getElementById('chart-pipeline');
    if (pipeCtx) {
      const stageCounts = {};
      STAGES.forEach(s => stageCounts[s] = 0);
      state.pipelineData.forEach(p => { if (stageCounts[p.stage] !== undefined) stageCounts[p.stage]++; });

      new Chart(pipeCtx, {
        type: 'doughnut',
        data: {
          labels: STAGES.map(s => STAGE_LABELS[s]),
          datasets: [{
            data: STAGES.map(s => stageCounts[s] || Math.floor(Math.random() * 8) + 1),
            backgroundColor: [
              getComputedStyle(document.documentElement).getPropertyValue('--color-blue').trim(),
              getComputedStyle(document.documentElement).getPropertyValue('--color-orange').trim(),
              getComputedStyle(document.documentElement).getPropertyValue('--color-purple').trim(),
              getComputedStyle(document.documentElement).getPropertyValue('--color-gold').trim(),
              getComputedStyle(document.documentElement).getPropertyValue('--color-primary').trim(),
              getComputedStyle(document.documentElement).getPropertyValue('--color-success').trim(),
            ],
            borderWidth: 0,
            cutout: '65%',
          }],
        },
        options: {
          responsive: true,
          maintainAspectRatio: false,
          plugins: {
            legend: {
              position: 'right',
              labels: { usePointStyle: true, pointStyle: 'circle', padding: 12, font: { size: 12 } },
            },
          },
        },
      });
    }

    // Activity Over Time
    const actCtx = document.getElementById('chart-activity');
    if (actCtx) {
      new Chart(actCtx, {
        type: 'line',
        data: {
          labels: ['Week 1', 'Week 2', 'Week 3', 'Week 4', 'Week 5', 'Week 6', 'Week 7', 'Week 8'],
          datasets: [{
            label: 'Messages Sent',
            data: [3, 5, 4, 8, 6, 9, 7, 11],
            borderColor: getComputedStyle(document.documentElement).getPropertyValue('--color-primary').trim(),
            backgroundColor: 'transparent',
            tension: 0.4,
            pointRadius: 4,
            pointHoverRadius: 6,
            borderWidth: 2,
          }, {
            label: 'Replies',
            data: [1, 2, 1, 3, 2, 4, 2, 3],
            borderColor: getComputedStyle(document.documentElement).getPropertyValue('--color-success').trim(),
            backgroundColor: 'transparent',
            tension: 0.4,
            pointRadius: 4,
            pointHoverRadius: 6,
            borderWidth: 2,
          }],
        },
        options: {
          responsive: true,
          maintainAspectRatio: false,
          plugins: {
            legend: {
              labels: { usePointStyle: true, pointStyle: 'circle', padding: 12, font: { size: 12 } },
            },
          },
          scales: {
            y: { beginAtZero: true, grid: { color: borderColor } },
            x: { grid: { display: false } },
          },
        },
      });
    }
  }

  // ============================================
  // PIPELINE BADGE
  // ============================================
  async function updatePipelineBadge() {
    const result = await api('/pipeline');
    if (result && result.pipeline) {
      state.pipelineData = result.pipeline;
      const badge = $('#pipeline-badge');
      if (badge) badge.textContent = result.pipeline.length;
    }
  }

  // ============================================
  // INIT
  // ============================================
  function init() {
    initTheme();

    // Hash routing
    const hash = window.location.hash.replace('#', '') || 'search';
    navigate(hash);

    // Nav clicks
    $$('.nav-item[data-view]').forEach(item => {
      item.addEventListener('click', () => navigate(item.dataset.view));
    });

    // Theme toggle
    $('#theme-toggle').addEventListener('click', toggleTheme);

    // Mobile menu
    const mobileBtn = $('#mobile-menu-btn');
    if (mobileBtn) {
      mobileBtn.addEventListener('click', () => {
        $('.sidebar').classList.toggle('mobile-open');
      });
    }

    // Search button
    $('#search-btn').addEventListener('click', async () => {
      await parseJD();
      if (state.parsedJD) await searchCandidates();
    });

    // Filter apply (on change)
    $$('.filter-select, .filter-input, #filter-open').forEach(el => {
      el.addEventListener('change', () => {
        if (state.parsedJD && state.candidates.length > 0) {
          searchCandidates();
        }
      });
    });

    // Modal close
    $('#modal-close').addEventListener('click', closeModal);
    $('#modal-overlay').addEventListener('click', e => {
      if (e.target === e.currentTarget) closeModal();
    });
    $('#modal-save').addEventListener('click', saveModalChanges);

    // Outreach controls
    const toneSlider = $('#tone-slider');
    if (toneSlider) {
      let debounce;
      toneSlider.addEventListener('input', () => {
        clearTimeout(debounce);
        debounce = setTimeout(() => {
          if (state.outreachCandidate) generateOutreach();
        }, 500);
      });
    }

    // Length toggles
    $$('.length-group .toggle-btn').forEach(btn => {
      btn.addEventListener('click', () => {
        $$('.length-group .toggle-btn').forEach(b => b.classList.remove('active'));
        btn.classList.add('active');
        if (state.outreachCandidate) generateOutreach();
      });
    });

    // Type toggles
    $$('.type-group .toggle-btn').forEach(btn => {
      btn.addEventListener('click', () => {
        $$('.type-group .toggle-btn').forEach(b => b.classList.remove('active'));
        btn.classList.add('active');
        if (state.outreachCandidate) generateOutreach();
      });
    });

    // Hash change
    window.addEventListener('hashchange', () => {
      const h = window.location.hash.replace('#', '') || 'search';
      navigate(h);
    });

    // Load pipeline count
    updatePipelineBadge();

    // Pre-fill JD for demo
    const demoJD = `Senior Full-Stack Engineer — Remote

We're looking for a Senior Full-Stack Engineer to join our growing team. You'll work on building and scaling our cloud-native platform using modern technologies.

Requirements:
- 5+ years of experience in software development
- Strong proficiency in React, TypeScript, and Node.js
- Experience with Python, PostgreSQL, and Redis
- Familiarity with AWS, Docker, and Kubernetes
- Experience with CI/CD pipelines and microservices architecture
- Bachelor's degree in Computer Science or equivalent

Nice to have:
- Experience with GraphQL
- Contributions to open source projects
- Experience at a high-growth startup

Location: Remote (US preferred)
Compensation: $160k - $220k`;

    const textarea = $('#jd-textarea');
    if (textarea && !textarea.value) {
      textarea.value = demoJD;
    }
  }

  // Run on DOM ready
  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', init);
  } else {
    init();
  }
})();
