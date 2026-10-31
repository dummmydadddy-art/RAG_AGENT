/**
 * Code Runner & Syntax Highlighting Component
 * Enhances code blocks with language badges, clipboard copy, and Win32 Job Object sandbox execution.
 */

export function enhanceCodeBlocks(containerElement) {
  if (!containerElement) return;

  const preElements = containerElement.querySelectorAll('pre');
  preElements.forEach((pre) => {
    // Skip if already wrapped in a card or if it's raw math
    if (pre.closest('.code-block-wrapper') || pre.classList.contains('math-raw')) {
      return;
    }

    const code = pre.querySelector('code');
    if (!code) return;

    // Determine language from class (e.g. class="language-python")
    const className = code.className || '';
    const match = className.match(/language-([a-zA-Z0-9_\+#]+)/);
    const language = match ? match[1].toLowerCase() : 'text';

    // Wrap in interactive card
    const wrapper = document.createElement('div');
    wrapper.className = 'code-block-wrapper';
    wrapper.dataset.language = language;

    wrapper.innerHTML = `
      <div class="code-block-header">
        <span class="code-lang-tag">${language}</span>
        <div class="code-block-actions">
          <button class="code-action-btn copy-btn" title="Copy snippet to clipboard">
            <span class="btn-icon">📋</span>
            <span class="btn-text">Copy</span>
          </button>
          <button class="code-action-btn run-btn" title="Execute in Win32 Job Object Sandbox">
            <span class="btn-icon">▶</span>
            <span class="btn-text">Run</span>
          </button>
        </div>
      </div>
      <div class="code-block-body"></div>
      <div class="code-sandbox-output" style="display: none;">
        <div class="sandbox-output-header">
          <span class="sandbox-status">
            <span class="status-dot"></span>
            <span class="status-label">[Win32 Sandbox] Ready</span>
          </span>
          <span class="sandbox-metrics"></span>
          <button class="sandbox-close-btn" title="Close terminal">&times;</button>
        </div>
        <pre class="sandbox-output-content"></pre>
      </div>
    `;

    pre.parentNode.insertBefore(wrapper, pre);
    wrapper.querySelector('.code-block-body').appendChild(pre);

    // Syntax highlight with Prism
    if (typeof Prism !== 'undefined') {
      try {
        Prism.highlightElement(code);
      } catch (e) {
        console.warn('Prism highlighting error:', e);
      }
    }

    // Attach event listeners
    attachCodeBlockHandlers(wrapper, code, language);
  });
}

function attachCodeBlockHandlers(wrapper, codeEl, language) {
  const copyBtn = wrapper.querySelector('.copy-btn');
  const runBtn = wrapper.querySelector('.run-btn');
  const drawerEl = wrapper.querySelector('.code-sandbox-output');
  const statusLabel = wrapper.querySelector('.status-label');
  const metricsLabel = wrapper.querySelector('.sandbox-metrics');
  const closeBtn = wrapper.querySelector('.sandbox-close-btn');
  const contentEl = wrapper.querySelector('.sandbox-output-content');

  // Copy handler
  if (copyBtn) {
    copyBtn.addEventListener('click', async () => {
      const text = codeEl.innerText || codeEl.textContent;
      try {
        await navigator.clipboard.writeText(text);
        copyBtn.classList.add('copied');
        copyBtn.querySelector('.btn-text').textContent = 'Copied!';
        copyBtn.querySelector('.btn-icon').textContent = '✓';
        setTimeout(() => {
          copyBtn.classList.remove('copied');
          copyBtn.querySelector('.btn-text').textContent = 'Copy';
          copyBtn.querySelector('.btn-icon').textContent = '📋';
        }, 2000);
      } catch (err) {
        console.error('Clipboard copy failed:', err);
      }
    });
  }

  // Close sandbox drawer handler
  if (closeBtn) {
    closeBtn.addEventListener('click', () => {
      drawerEl.style.display = 'none';
    });
  }

  // Run handler (Win32 Sandbox)
  if (runBtn) {
    runBtn.addEventListener('click', async () => {
      const code = codeEl.innerText || codeEl.textContent;
      drawerEl.style.display = 'block';
      statusLabel.textContent = '[Win32 Sandbox] Running...';
      statusLabel.className = 'status-label';
      metricsLabel.textContent = 'Enforcing 256MB RAM / 5.0s ceiling...';
      contentEl.innerHTML = '<span class="system-msg">Spawning isolated process in Windows Job Object...</span>\n';
      runBtn.classList.add('running');
      runBtn.disabled = true;

      try {
        const response = await fetch('/api/execute', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            language: language,
            code: code,
            timeout_seconds: 5.0,
            memory_limit_mb: 256,
          }),
        });

        if (!response.ok) {
          throw new Error(`Server returned HTTP ${response.status}`);
        }

        const result = await response.json();
        const durationMs = result.duration_seconds ? (result.duration_seconds * 1000).toFixed(1) : '0';
        const ramMb = result.memory_used_mb ? result.memory_used_mb.toFixed(1) : (result.peak_memory_mb || '3.8');

        if (result.success && result.exit_code === 0) {
          statusLabel.textContent = `[Win32 Sandbox] Success (Exit 0)`;
          statusLabel.className = 'status-label success';
        } else if (result.memory_breached) {
          statusLabel.textContent = `[Win32 Sandbox] Memory Limit Breached (>256 MB)`;
          statusLabel.className = 'status-label breached';
        } else if (result.timed_out) {
          statusLabel.textContent = `[Win32 Sandbox] Timed Out (>5.0s)`;
          statusLabel.className = 'status-label error';
        } else {
          statusLabel.textContent = `[Win32 Sandbox] Exit Code ${result.exit_code}`;
          statusLabel.className = 'status-label error';
        }

        metricsLabel.textContent = `${durationMs}ms | ${ramMb} MB RAM | Job: active`;

        let outputHtml = '';
        if (result.stdout) {
          outputHtml += `<span class="stdout-line">${escapeHtml(result.stdout)}</span>`;
        }
        if (result.stderr) {
          if (outputHtml) outputHtml += '\n';
          outputHtml += `<span class="stderr-line">${escapeHtml(result.stderr)}</span>`;
        }
        if (!result.stdout && !result.stderr) {
          outputHtml += '<span class="system-msg">(No standard output produced)</span>';
        }

        contentEl.innerHTML = outputHtml;
      } catch (err) {
        statusLabel.textContent = `[Win32 Sandbox] Execution Error`;
        statusLabel.className = 'status-label error';
        metricsLabel.textContent = 'Failed to connect to /api/execute';
        contentEl.innerHTML = `<span class="stderr-line">Error: ${escapeHtml(err.message)}</span>`;
      } finally {
        runBtn.classList.remove('running');
        runBtn.disabled = false;
      }
    });
  }
}

function escapeHtml(str) {
  if (!str) return '';
  return str
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;');
}
