/**
 * Live Telemetry Status Badges & Inspector Drawer
 * Handles PhysMath MCP verification, Win32 Job Object metrics, and RAG lesson citations.
 */

export class TelemetryManager {
  constructor() {
    this.activeDrawer = null;
  }

  /**
   * Creates a telemetry container for an assistant message row.
   */
  createTelemetryBar(messageRowEl) {
    const bar = document.createElement('div');
    bar.className = 'message-telemetry-bar';

    const pillGroup = document.createElement('div');
    pillGroup.className = 'telemetry-pill-group';

    const drawer = document.createElement('div');
    drawer.className = 'telemetry-drawer';
    drawer.style.display = 'none';

    bar.appendChild(pillGroup);
    bar.appendChild(drawer);
    messageRowEl.appendChild(bar);

    return { bar, pillGroup, drawer, data: { physmath: null, sandbox: null, rag: [] } };
  }

  /**
   * Updates or appends a telemetry pill when an SSE event arrives.
   */
  handleTelemetryEvent(telemetryState, eventType, data) {
    if (!telemetryState || !telemetryState.pillGroup || !data) return;

    if (eventType === 'telemetry') {
      if (data.elapsed_seconds !== undefined) {
        telemetryState.data.elapsed_seconds = data.elapsed_seconds;
      }
      if (data.physmath !== undefined) {
        telemetryState.data.physmath = data.physmath;
        if (data.physmath && data.physmath.status && data.physmath.status !== 'none') {
          this.renderPhysMathPill(telemetryState);
        }
      }
      if (data.citations || data.citations_count !== undefined) {
        telemetryState.data.citations_count = data.citations_count || 0;
        if (Array.isArray(data.citations)) {
          telemetryState.data.rag = data.citations;
        }
        if (telemetryState.data.rag.length > 0 || telemetryState.data.citations_count > 0) {
          this.renderRagPill(telemetryState);
        }
      }
    } else if (eventType === 'telemetry_physmath') {
      telemetryState.data.physmath = data;
      if (data && data.status !== 'none') {
        this.renderPhysMathPill(telemetryState);
      }
    } else if (eventType === 'telemetry_sandbox') {
      telemetryState.data.sandbox = data;
      this.renderSandboxPill(telemetryState);
    } else if (eventType === 'telemetry_rag') {
      if (Array.isArray(data.lessons)) {
        telemetryState.data.rag = data.lessons;
      } else if (data.lesson_id) {
        telemetryState.data.rag.push(data);
      }
      this.renderRagPill(telemetryState);
    }
  }

  renderPhysMathPill(state) {
    let pill = state.pillGroup.querySelector('.pill-physmath');
    if (!pill) {
      pill = document.createElement('button');
      pill.className = 'telemetry-pill pill-physmath';
      pill.innerHTML = `
        <span class="pill-dot blue"></span>
        <span class="pill-title">PhysMath</span>
        <span class="pill-badge">Pint & SymPy</span>
      `;
      pill.addEventListener('click', () => this.toggleDrawer(state, 'physmath'));
      state.pillGroup.appendChild(pill);
    }

    const d = state.data.physmath;
    if (d) {
      const badge = pill.querySelector('.pill-badge');
      if (d.summary) {
        badge.textContent = d.summary;
      } else if (d.status === 'verified') {
        badge.textContent = `${d.checks_run || 1} Verified`;
      } else if (d.status === 'detected') {
        badge.textContent = `${(d.units_detected || []).length} Units`;
      } else if (d.status && d.status !== 'none') {
        badge.textContent = d.status.toUpperCase();
      }
    }
  }

  renderSandboxPill(state) {
    let pill = state.pillGroup.querySelector('.pill-sandbox');
    const d = state.data.sandbox;
    if (!pill) {
      pill = document.createElement('button');
      pill.className = 'telemetry-pill pill-sandbox';
      pill.innerHTML = `
        <span class="pill-dot green"></span>
        <span class="pill-title">Win32 Sandbox</span>
        <span class="pill-badge">Executed</span>
      `;
      pill.addEventListener('click', () => this.toggleDrawer(state, 'sandbox'));
      state.pillGroup.appendChild(pill);
    }

    if (d) {
      const dot = pill.querySelector('.pill-dot');
      const badge = pill.querySelector('.pill-badge');
      const dur = d.duration_seconds !== undefined ? `${d.duration_seconds.toFixed(2)}s` : '0.00s';
      const mem = d.memory_used_mb !== undefined ? `${d.memory_used_mb}MB` : (d.peak_memory_mb !== undefined ? `${d.peak_memory_mb}MB` : '0MB');
      if (d.exit_code === 0 && !d.memory_breached) {
        dot.className = 'pill-dot green';
        badge.textContent = `${dur} · ${mem}`;
      } else {
        dot.className = 'pill-dot red';
        pill.classList.add('breached');
        badge.textContent = d.memory_breached ? 'RAM Limit Breached' : `Exit ${d.exit_code !== undefined ? d.exit_code : 1}`;
      }
    }
  }

  renderRagPill(state) {
    let pill = state.pillGroup.querySelector('.pill-rag');
    const lessons = state.data.rag || [];
    const count = state.data.citations_count !== undefined ? state.data.citations_count : lessons.length;
    if (!pill) {
      pill = document.createElement('button');
      pill.className = 'telemetry-pill pill-rag';
      pill.innerHTML = `
        <span class="pill-dot purple"></span>
        <span class="pill-title">RAG Lessons</span>
        <span class="pill-badge">${count} Cited</span>
      `;
      pill.addEventListener('click', () => this.toggleDrawer(state, 'rag'));
      state.pillGroup.appendChild(pill);
    }

    if (count > 0) {
      const badge = pill.querySelector('.pill-badge');
      if (lessons.length > 0 && lessons[0].confidence !== undefined) {
        const conf = `${Math.round(lessons[0].confidence * 100)}%`;
        badge.textContent = `${count} Cited (${conf})`;
      } else {
        badge.textContent = `${count} Cited`;
      }
    }
  }

  toggleDrawer(state, type) {
    const { drawer, pillGroup } = state;
    const isCurrentlyOpen = drawer.style.display !== 'none' && drawer.dataset.activeType === type;

    // Reset active pill highlights
    pillGroup.querySelectorAll('.telemetry-pill').forEach((p) => p.classList.remove('active'));

    if (isCurrentlyOpen) {
      drawer.style.display = 'none';
      drawer.dataset.activeType = '';
      return;
    }

    // Mark clicked pill active
    const activePill = pillGroup.querySelector(`.pill-${type}`);
    if (activePill) activePill.classList.add('active');

    drawer.dataset.activeType = type;
    drawer.style.display = 'block';

    if (type === 'physmath') {
      this.populatePhysMathDrawer(drawer, state.data.physmath);
    } else if (type === 'sandbox') {
      this.populateSandboxDrawer(drawer, state.data.sandbox);
    } else if (type === 'rag') {
      this.populateRagDrawer(drawer, state.data.rag);
    }
  }

  populatePhysMathDrawer(drawer, data) {
    const hasChecks = data && Array.isArray(data.checks) && data.checks.length > 0;
    const hasUnits = data && Array.isArray(data.units_detected) && data.units_detected.length > 0;
    const hasPint = data && (data.pint_units || data.dimensions || data.symbolic_verification);

    if (!data || data.status === 'none' || (!hasChecks && !hasUnits && !hasPint)) {
      drawer.innerHTML = `
        <div class="telemetry-drawer-header">
          <span>⚡ PhysMath Verification Metrics</span>
          <button class="telemetry-drawer-close">&times;</button>
        </div>
        <div class="telemetry-drawer-body">
          <div class="telemetry-empty-state">
            <span class="empty-icon">ℹ️</span>
            <span class="empty-text">No PhysMath equations or physical units detected in this turn.</span>
          </div>
        </div>
      `;
      drawer.querySelector('.telemetry-drawer-close').addEventListener('click', () => {
        drawer.style.display = 'none';
        drawer.dataset.activeType = '';
      });
      return;
    }

    let rowsHtml = '';
    if (hasChecks) {
      rowsHtml += data.checks.map((c) => {
        const eqName = escapeHtml(c.test || c.equation || 'Equation Check');
        const isValid = c.result && c.result.valid;
        const dims = c.result && c.result.dims ? ` (${escapeHtml(c.result.dims)})` : '';
        const statusText = isValid ? '✓ Verified Dimensional Consistency' : '✗ Dimensional Inconsistency';
        return `
          <div class="physmath-check-row">
            <span class="physmath-label">${eqName}:</span>
            <span class="physmath-val">${statusText}${dims}</span>
          </div>
        `;
      }).join('');
    }

    if (hasUnits) {
      rowsHtml += `
        <div class="physmath-check-row">
          <span class="physmath-label">Detected Units:</span>
          <span class="physmath-val">${escapeHtml(data.units_detected.join(', '))}</span>
        </div>
      `;
    }

    if (data.pint_units) {
      rowsHtml += `
        <div class="physmath-check-row">
          <span class="physmath-label">Pint Units:</span>
          <span class="physmath-val">${escapeHtml(data.pint_units)}${data.dimensions ? ` (Dimension: ${escapeHtml(data.dimensions)})` : ''}</span>
        </div>
      `;
    }

    if (data.symbolic_verification) {
      rowsHtml += `
        <div class="physmath-check-row">
          <span class="physmath-label">SymPy Symbolic Equivalence:</span>
          <span class="physmath-val">${escapeHtml(data.symbolic_verification)}</span>
        </div>
      `;
    }

    if (Array.isArray(data.tool_calls) && data.tool_calls.length > 0) {
      rowsHtml += `
        <div class="physmath-check-row">
          <span class="physmath-label">MCP Tools Invoked:</span>
          <span class="physmath-val">${escapeHtml(data.tool_calls.join(', '))}</span>
        </div>
      `;
    }

    const statusBadge = data.status ? ` (${escapeHtml(data.status.toUpperCase())})` : '';

    drawer.innerHTML = `
      <div class="telemetry-drawer-header">
        <span>⚡ PhysMath Verification Metrics${statusBadge}</span>
        <button class="telemetry-drawer-close">&times;</button>
      </div>
      <div class="telemetry-drawer-body">
        ${rowsHtml}
      </div>
    `;

    drawer.querySelector('.telemetry-drawer-close').addEventListener('click', () => {
      drawer.style.display = 'none';
      drawer.dataset.activeType = '';
    });
  }

  populateSandboxDrawer(drawer, data) {
    if (!data) {
      drawer.innerHTML = `
        <div class="telemetry-drawer-header">
          <span>🛡️ Win32 Job Object Sandbox Telemetry</span>
          <button class="telemetry-drawer-close">&times;</button>
        </div>
        <div class="telemetry-drawer-body">
          <div class="telemetry-empty-state">
            <span class="empty-icon">ℹ️</span>
            <span class="empty-text">No sandboxed code was executed during this turn. Click 'Run' on a code block to execute in sandbox.</span>
          </div>
        </div>
      `;
      drawer.querySelector('.telemetry-drawer-close').addEventListener('click', () => {
        drawer.style.display = 'none';
        drawer.dataset.activeType = '';
      });
      return;
    }

    const sb = data;
    const durSec = sb.duration_seconds !== undefined ? sb.duration_seconds : 0;
    const memVal = sb.memory_used_mb !== undefined ? sb.memory_used_mb : (sb.peak_memory_mb !== undefined ? sb.peak_memory_mb : '0.0');
    const exitVal = sb.exit_code !== undefined ? sb.exit_code : 0;
    const secStatus = sb.security_status || 'clean';

    drawer.innerHTML = `
      <div class="telemetry-drawer-header">
        <span>🛡️ Win32 Job Object Sandbox Telemetry</span>
        <button class="telemetry-drawer-close">&times;</button>
      </div>
      <div class="telemetry-drawer-body">
        <div class="sandbox-detail-grid">
          <div class="sandbox-metric-box">
            <span class="metric-title">Duration</span>
            <span class="metric-val">${durSec.toFixed(3)}s</span>
          </div>
          <div class="sandbox-metric-box">
            <span class="metric-title">Job Memory</span>
            <span class="metric-val">${memVal} MB / 256 MB</span>
          </div>
          <div class="sandbox-metric-box">
            <span class="metric-title">Exit Code</span>
            <span class="metric-val">${exitVal}</span>
          </div>
          <div class="sandbox-metric-box">
            <span class="metric-title">Security Filter</span>
            <span class="metric-val">${escapeHtml(secStatus)}</span>
          </div>
        </div>
        ${sb.error_message ? `<div class="sandbox-error-notice" style="color: var(--accent-danger); font-size: 11.5px; margin-top: 4px;">${escapeHtml(sb.error_message)}</div>` : ''}
      </div>
    `;

    drawer.querySelector('.telemetry-drawer-close').addEventListener('click', () => {
      drawer.style.display = 'none';
      drawer.dataset.activeType = '';
    });
  }

  populateRagDrawer(drawer, lessons) {
    const list = Array.isArray(lessons) ? lessons : [];

    if (list.length === 0) {
      drawer.innerHTML = `
        <div class="telemetry-drawer-header">
          <span>📚 RAG Cited Lessons (0)</span>
          <button class="telemetry-drawer-close">&times;</button>
        </div>
        <div class="telemetry-drawer-body">
          <div class="telemetry-empty-state">
            <span class="empty-icon">ℹ️</span>
            <span class="empty-text">No RAG lessons were retrieved or cited for this turn.</span>
          </div>
        </div>
      `;
      drawer.querySelector('.telemetry-drawer-close').addEventListener('click', () => {
        drawer.style.display = 'none';
        drawer.dataset.activeType = '';
      });
      return;
    }

    let lessonsHtml = list.map((l) => `
      <div class="rag-lesson-card" data-id="${escapeHtml(l.id || '')}">
        <div class="lesson-card-header">
          <span class="lesson-id-tag">#${escapeHtml(l.id || 'lesson')}</span>
          <span class="lesson-status-tag">${escapeHtml(l.status || 'VERIFIED')}</span>
        </div>
        <div class="lesson-rule-text">${escapeHtml(l.rule || l.text || '')}</div>
        <div class="lesson-feedback-bar">
          <button class="feedback-btn like-btn" title="Mark this lesson helpful">👍 Helpful</button>
          <button class="feedback-btn dislike-btn" title="Mark this lesson unhelpful">👎 Not Helpful</button>
        </div>
      </div>
    `).join('');

    drawer.innerHTML = `
      <div class="telemetry-drawer-header">
        <span>📚 RAG Cited Lessons (${list.length})</span>
        <button class="telemetry-drawer-close">&times;</button>
      </div>
      <div class="telemetry-drawer-body">
        ${lessonsHtml}
      </div>
    `;

    // Attach feedback handlers
    drawer.querySelectorAll('.rag-lesson-card').forEach((card) => {
      const lessonId = card.dataset.id;
      const likeBtn = card.querySelector('.like-btn');
      const dislikeBtn = card.querySelector('.dislike-btn');

      if (likeBtn) {
        likeBtn.addEventListener('click', async () => {
          likeBtn.classList.toggle('active');
          if (dislikeBtn) dislikeBtn.classList.remove('active');
          await this.sendFeedback(lessonId, true);
        });
      }

      if (dislikeBtn) {
        dislikeBtn.addEventListener('click', async () => {
          dislikeBtn.classList.toggle('active');
          if (likeBtn) likeBtn.classList.remove('active');
          await this.sendFeedback(lessonId, false);
        });
      }
    });

    drawer.querySelector('.telemetry-drawer-close').addEventListener('click', () => {
      drawer.style.display = 'none';
      drawer.dataset.activeType = '';
    });
  }

  async sendFeedback(lessonId, isHelpful) {
    try {
      await fetch(`/api/lessons/${lessonId}/feedback`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ helpful: isHelpful }),
      });
    } catch (e) {
      console.warn('Feedback submission error:', e);
    }
  }
}

function escapeHtml(str) {
  if (!str) return '';
  return String(str)
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;');
}

/**
 * Controller for Autonomous Self-Learning Header Widget.
 * Handles polling /api/learning/status every 3s, optimistic toggles, and state sync.
 */
export class LearningWidgetController {
  constructor() {
    this.widgetEl = document.getElementById('learning-widget');
    this.dotEl = document.getElementById('learning-dot');
    this.labelEl = document.getElementById('learning-status-label');
    this.cyclesEl = document.getElementById('learning-cycles-pill');
    this.lessonsEl = document.getElementById('learning-lessons-pill');
    this.toggleBtn = document.getElementById('learning-toggle-btn');
    this.btnIcon = document.getElementById('learning-btn-icon');
    this.btnText = document.getElementById('learning-btn-text');

    this.isRunning = false;
    this.pollInterval = null;

    this.init();
  }

  init() {
    if (!this.toggleBtn) return;
    this.toggleBtn.addEventListener('click', () => this.handleToggle());
    this.pollStatus();
    this.pollInterval = setInterval(() => this.pollStatus(), 3000);
  }

  async pollStatus() {
    try {
      const res = await fetch('/api/learning/status');
      if (res.ok) {
        const data = await res.json();
        this.renderState(data);
      }
    } catch (err) {
      console.warn('Learning status poll failed:', err);
    }
  }

  renderState(data) {
    this.isRunning = data.status === 'Running';

    if (this.dotEl) {
      this.dotEl.className = `learning-dot ${(data.status || 'idle').toLowerCase()}`;
      this.dotEl.title = `Autonomous Self-Learning: ${data.status}${data.pid ? ` (PID: ${data.pid})` : ''}`;
    }
    if (this.labelEl) {
      this.labelEl.textContent = `Learning: ${data.status}`;
    }
    if (this.cyclesEl) {
      this.cyclesEl.textContent = `#${data.cycle_count || 0}`;
      this.cyclesEl.title = `Completed cycles: ${data.cycle_count || 0}`;
    }
    if (this.lessonsEl) {
      this.lessonsEl.textContent = `${data.total_lessons || 0} Lessons`;
      this.lessonsEl.title = `Total harvested lessons: ${data.total_lessons || 0}`;
    }

    if (this.toggleBtn) {
      this.toggleBtn.disabled = false;
      if (this.isRunning) {
        this.toggleBtn.className = 'learning-toggle-btn stop';
        if (this.btnIcon) this.btnIcon.textContent = '⏹';
        if (this.btnText) this.btnText.textContent = 'Stop';
        this.toggleBtn.title = 'Stop Autonomous Self-Learning Daemon';
      } else {
        this.toggleBtn.className = 'learning-toggle-btn start';
        if (this.btnIcon) this.btnIcon.textContent = '▶';
        if (this.btnText) this.btnText.textContent = 'Start';
        this.toggleBtn.title = 'Start Autonomous Self-Learning Daemon';
      }
    }
  }

  async handleToggle() {
    if (!this.toggleBtn || this.toggleBtn.disabled) return;
    this.toggleBtn.disabled = true;
    const targetAction = this.isRunning ? 'stop' : 'start';
    if (this.btnText) {
      this.btnText.textContent = this.isRunning ? 'Stopping...' : 'Starting...';
    }

    try {
      const res = await fetch(`/api/learning/${targetAction}`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: targetAction === 'start' ? JSON.stringify({ interval_seconds: 15.0 }) : JSON.stringify({}),
      });
      if (!res.ok) {
        const errData = await res.json().catch(() => ({}));
        throw new Error(errData.detail || errData.message || `HTTP ${res.status}`);
      }
      await this.pollStatus();
    } catch (err) {
      console.error(`Failed to ${targetAction} learning loop:`, err);
      alert(`Could not ${targetAction} self-learning loop: ${err.message}`);
      await this.pollStatus();
    } finally {
      if (this.toggleBtn) this.toggleBtn.disabled = false;
    }
  }
}
