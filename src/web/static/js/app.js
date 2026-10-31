/**
 * Application Orchestrator & UI Controller
 * Integrates theme, sidebar history, Markdown/KaTeX pipeline, code runner, and SSE streaming.
 */

import { ThemeManager } from './theme.js';
import { SidebarManager } from './sidebar.js';
import { MarkdownRenderer } from './markdown.js';
import { enhanceCodeBlocks } from './code_runner.js';
import { TelemetryManager } from './telemetry.js';
import { streamChatCompletion } from './sse_client.js';

class App {
  constructor() {
    this.themeManager = new ThemeManager();
    this.markdownRenderer = new MarkdownRenderer();
    this.telemetryManager = new TelemetryManager();

    this.activeConversationId = this.generateId();
    this.activeAbortController = null;
    this.isGenerating = false;
    this.conversationMessages = [];

    // DOM Elements
    this.messageStreamEl = document.getElementById('message-stream') || document.getElementById('chat-messages');
    this.welcomeScreenEl = document.getElementById('welcome-screen');
    this.textareaEl = document.getElementById('chat-textarea') || document.getElementById('user-input');
    this.sendBtn = document.getElementById('send-button');
    this.clearChatBtn = document.getElementById('clear-chat-btn');
    this.exportChatBtn = document.getElementById('export-chat-btn');
    this.systemStatusEl = document.getElementById('system-status');

    this.sidebarManager = new SidebarManager({
      onSelectConversation: (conv) => this.loadConversation(conv),
      onNewChat: () => this.startNewChat(),
    });

    this.initEventListeners();
    this.checkSystemHealth();
  }

  generateId() {
    return 'conv_' + Date.now() + '_' + Math.random().toString(36).substr(2, 6);
  }

  initEventListeners() {
    // Textarea input auto-expansion & Send button toggling
    if (this.textareaEl) {
      this.textareaEl.addEventListener('input', () => {
        this.adjustTextareaHeight();
        this.updateSendButtonState();
      });

      this.textareaEl.addEventListener('keydown', (e) => {
        if (e.key === 'Enter' && !e.shiftKey) {
          e.preventDefault();
          this.handleSend();
        }
      });
    }

    // Send / Stop button click
    if (this.sendBtn) {
      this.sendBtn.addEventListener('click', () => {
        if (this.isGenerating) {
          this.stopGeneration();
        } else {
          this.handleSend();
        }
      });
    }

    // Starter Prompt Chips
    document.querySelectorAll('.prompt-chip').forEach((chip) => {
      chip.addEventListener('click', () => {
        const prompt = chip.dataset.prompt;
        if (prompt && this.textareaEl) {
          this.textareaEl.value = prompt;
          this.adjustTextareaHeight();
          this.updateSendButtonState();
          this.handleSend();
        }
      });
    });

    // Clear Chat
    if (this.clearChatBtn) {
      this.clearChatBtn.addEventListener('click', () => {
        if (this.isGenerating) this.stopGeneration();
        this.clearMessages();
      });
    }

    // Export Chat
    if (this.exportChatBtn) {
      this.exportChatBtn.addEventListener('click', () => {
        this.exportConversation();
      });
    }
  }

  adjustTextareaHeight() {
    if (!this.textareaEl) return;
    this.textareaEl.style.height = 'auto';
    const newHeight = Math.min(this.textareaEl.scrollHeight, 200);
    this.textareaEl.style.height = newHeight + 'px';
  }

  updateSendButtonState() {
    if (!this.sendBtn) return;
    if (this.isGenerating) {
      this.sendBtn.disabled = false;
      this.sendBtn.innerHTML = `
        <svg viewBox="0 0 24 24" width="16" height="16" fill="currentColor">
          <rect x="6" y="6" width="12" height="12" rx="2"></rect>
        </svg>
      `;
      this.sendBtn.title = 'Stop generating';
    } else {
      const hasText = this.textareaEl && this.textareaEl.value.trim().length > 0;
      this.sendBtn.disabled = !hasText;
      this.sendBtn.innerHTML = `
        <svg viewBox="0 0 24 24" fill="none" stroke="currentColor">
          <path d="M5 12h14M12 5l7 7-7 7" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round"/>
        </svg>
      `;
      this.sendBtn.title = 'Send message (Enter)';
    }
  }

  startNewChat() {
    if (this.isGenerating) this.stopGeneration();
    this.activeConversationId = this.generateId();
    this.conversationMessages = [];
    this.clearMessages();
    this.sidebarManager.setActive(null);
    if (this.textareaEl) {
      this.textareaEl.value = '';
      this.adjustTextareaHeight();
      this.updateSendButtonState();
      this.textareaEl.focus();
    }
  }

  clearMessages() {
    if (this.messageStreamEl) {
      this.messageStreamEl.querySelectorAll('.message-row').forEach((el) => el.remove());
    }
    if (this.welcomeScreenEl) {
      this.welcomeScreenEl.style.display = 'flex';
    }
  }

  async loadConversation(conv) {
    if (this.isGenerating) this.stopGeneration();
    this.activeConversationId = conv.id;
    this.clearMessages();

    if (this.welcomeScreenEl) {
      this.welcomeScreenEl.style.display = 'none';
    }

    try {
      const res = await fetch(`/api/conversations/${conv.id}`);
      if (res.ok) {
        const data = await res.json();
        const messages = data.messages || [];
        this.conversationMessages = messages;
        messages.forEach((msg) => {
          if (msg.role === 'user') {
            this.appendUserMessage(msg.content);
          } else {
            const assistantRow = this.appendAssistantMessage();
            assistantRow.contentEl.innerHTML = this.markdownRenderer.render(msg.content);
            enhanceCodeBlocks(assistantRow.contentEl);
            if (msg.telemetry) {
              const telState = this.telemetryManager.createTelemetryBar(assistantRow.row);
              if (msg.telemetry.physmath) this.telemetryManager.handleTelemetryEvent(telState, 'telemetry_physmath', msg.telemetry.physmath);
              if (msg.telemetry.sandbox) this.telemetryManager.handleTelemetryEvent(telState, 'telemetry_sandbox', msg.telemetry.sandbox);
              if (msg.telemetry.rag) this.telemetryManager.handleTelemetryEvent(telState, 'telemetry_rag', msg.telemetry.rag);
            }
          }
        });
      }
    } catch (err) {
      console.warn('Could not load remote conversation details:', err);
    }
  }

  async handleSend() {
    const text = this.textareaEl ? this.textareaEl.value.trim() : '';
    if (!text || this.isGenerating) return;

    // Hide welcome screen
    if (this.welcomeScreenEl) {
      this.welcomeScreenEl.style.display = 'none';
    }

    // Reset textarea
    this.textareaEl.value = '';
    this.adjustTextareaHeight();

    // Append User Message to UI
    this.appendUserMessage(text);
    this.conversationMessages.push({ role: 'user', content: text });

    // Update conversation sidebar title if first message
    const title = text.slice(0, 36) + (text.length > 36 ? '...' : '');
    this.sidebarManager.addOrUpdateConversation({
      id: this.activeConversationId,
      title: title,
      updated_at: new Date().toISOString(),
    });
    this.sidebarManager.setActive(this.activeConversationId);

    // Prepare Assistant Streaming Row
    const assistantRow = this.appendAssistantMessage();
    let accumulatedText = '';
    const cursorEl = document.createElement('span');
    cursorEl.className = 'streaming-cursor';
    assistantRow.contentEl.appendChild(cursorEl);

    // Telemetry state container
    const telemetryState = this.telemetryManager.createTelemetryBar(assistantRow.row);

    // Setup AbortController
    this.activeAbortController = new AbortController();
    this.isGenerating = true;
    this.updateSendButtonState();

    await streamChatCompletion({
      message: text,
      conversationId: this.activeConversationId,
      abortSignal: this.activeAbortController.signal,
      onToken: (chunk) => {
        accumulatedText += chunk;
        assistantRow.contentEl.innerHTML = this.markdownRenderer.render(accumulatedText);
        assistantRow.contentEl.appendChild(cursorEl);
        this.scrollToBottom();
      },
      onTelemetry: (eventType, data) => {
        this.telemetryManager.handleTelemetryEvent(telemetryState, eventType, data);
      },
      onDone: (data) => {
        cursorEl.remove();
        assistantRow.contentEl.innerHTML = this.markdownRenderer.render(accumulatedText);
        enhanceCodeBlocks(assistantRow.contentEl);
        this.conversationMessages.push({ role: 'assistant', content: accumulatedText });
        this.isGenerating = false;
        this.updateSendButtonState();
        this.scrollToBottom();
      },
      onError: (errMsg) => {
        cursorEl.remove();
        const errDiv = document.createElement('div');
        errDiv.style.color = 'var(--accent-danger)';
        errDiv.style.marginTop = '8px';
        errDiv.textContent = `[Error]: ${errMsg}`;
        assistantRow.contentEl.appendChild(errDiv);
        this.isGenerating = false;
        this.updateSendButtonState();
      },
    });
  }

  stopGeneration() {
    if (this.activeAbortController) {
      this.activeAbortController.abort();
      this.activeAbortController = null;
    }
    this.isGenerating = false;
    this.updateSendButtonState();
  }

  appendUserMessage(text) {
    const row = document.createElement('div');
    row.className = 'message-row user-row';
    row.innerHTML = `
      <div class="message-header">
        <div class="message-avatar">U</div>
        <span class="message-sender">You</span>
      </div>
      <div class="message-content"></div>
    `;
    row.querySelector('.message-content').textContent = text;
    this.messageStreamEl.appendChild(row);
    this.scrollToBottom();
  }

  appendAssistantMessage() {
    const row = document.createElement('div');
    row.className = 'message-row assistant-row';
    row.innerHTML = `
      <div class="message-header">
        <div class="message-avatar">⚡</div>
        <span class="message-sender">STEM Coder Expert</span>
      </div>
      <div class="message-content"></div>
    `;
    this.messageStreamEl.appendChild(row);
    this.scrollToBottom();
    return { row, contentEl: row.querySelector('.message-content') };
  }

  scrollToBottom() {
    if (this.messageStreamEl) {
      this.messageStreamEl.scrollTop = this.messageStreamEl.scrollHeight;
    }
  }

  exportConversation() {
    if (this.conversationMessages.length === 0) {
      alert('Conversation is empty.');
      return;
    }

    let md = `# Conversation Export — ${new Date().toLocaleString()}\n\n`;
    this.conversationMessages.forEach((msg) => {
      md += `### ${msg.role === 'user' ? 'User' : 'STEM Coder Expert'}\n\n${msg.content}\n\n---\n\n`;
    });

    const blob = new Blob([md], { type: 'text/markdown;charset=utf-8;' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `chat_export_${this.activeConversationId}.md`;
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
    URL.revokeObjectURL(url);
  }

  async checkSystemHealth() {
    try {
      const res = await fetch('/api/health');
      if (res.ok) {
        const data = await res.json();
        if (this.systemStatusEl) {
          const ind = this.systemStatusEl.querySelector('.status-indicator');
          const txt = this.systemStatusEl.querySelector('.status-text');
          if (ind) ind.className = 'status-indicator online';
          if (txt) txt.textContent = data.model || 'stem-coder-expert:latest';
        }
      }
    } catch (_) {
      // Offline fallback state
    }
  }
}

// Bootstrap on DOM ready
document.addEventListener('DOMContentLoaded', () => {
  window.ragApp = new App();
});
