/**
 * Sidebar & Conversation History Manager
 * Supports conversation CRUD, date grouping, search filter, and responsive drawer toggling.
 */

export class SidebarManager {
  constructor({ onSelectConversation, onNewChat }) {
    this.onSelectConversation = onSelectConversation;
    this.onNewChat = onNewChat;
    this.conversations = [];
    this.activeConversationId = null;

    this.sidebarEl = document.getElementById('sidebar');
    this.conversationListEl = document.getElementById('conversation-list');
    this.searchInputEl = document.getElementById('conversation-search');
    this.backdropEl = document.getElementById('sidebar-backdrop');
    this.toggleBtn = document.getElementById('sidebar-toggle-btn');
    this.mobileToggleBtn = document.getElementById('mobile-sidebar-toggle');
    this.newChatBtn = document.getElementById('new-chat-btn');

    this.initEventListeners();
    this.loadConversations();
  }

  initEventListeners() {
    // Desktop collapse toggle
    if (this.toggleBtn) {
      this.toggleBtn.addEventListener('click', () => {
        this.sidebarEl.classList.toggle('collapsed');
      });
    }

    // Mobile drawer toggle
    if (this.mobileToggleBtn) {
      this.mobileToggleBtn.addEventListener('click', () => {
        this.openMobileSidebar();
      });
    }

    // Backdrop click
    if (this.backdropEl) {
      this.backdropEl.addEventListener('click', () => {
        this.closeMobileSidebar();
      });
    }

    // New Chat Button
    if (this.newChatBtn) {
      this.newChatBtn.addEventListener('click', () => {
        this.closeMobileSidebar();
        if (this.onNewChat) {
          this.onNewChat();
        }
      });
    }

    // Search filter
    if (this.searchInputEl) {
      this.searchInputEl.addEventListener('input', (e) => {
        const query = e.target.value.toLowerCase().trim();
        this.renderConversations(query);
      });
    }
  }

  openMobileSidebar() {
    this.sidebarEl.classList.add('mobile-open');
    if (this.backdropEl) {
      this.backdropEl.classList.add('active');
    }
  }

  closeMobileSidebar() {
    this.sidebarEl.classList.remove('mobile-open');
    if (this.backdropEl) {
      this.backdropEl.classList.remove('active');
    }
  }

  async loadConversations() {
    try {
      const res = await fetch('/api/conversations');
      if (res.ok) {
        this.conversations = await res.json();
      } else {
        this.conversations = this.getLocalConversations();
      }
    } catch (err) {
      console.warn('Backend conversations unavailable, using local cache:', err);
      this.conversations = this.getLocalConversations();
    }
    this.renderConversations();
  }

  getLocalConversations() {
    try {
      const data = localStorage.getItem('rag_agent_conversations');
      return data ? JSON.parse(data) : [];
    } catch {
      return [];
    }
  }

  saveLocalConversations() {
    try {
      localStorage.setItem('rag_agent_conversations', JSON.stringify(this.conversations));
    } catch (e) {
      console.error('Failed to save conversations locally:', e);
    }
  }

  addOrUpdateConversation(conversation) {
    const idx = this.conversations.findIndex((c) => c.id === conversation.id);
    if (idx >= 0) {
      this.conversations[idx] = { ...this.conversations[idx], ...conversation };
    } else {
      this.conversations.unshift(conversation);
    }
    this.saveLocalConversations();
    this.renderConversations();
  }

  setActive(conversationId) {
    this.activeConversationId = conversationId;
    const items = this.conversationListEl.querySelectorAll('.conversation-item');
    items.forEach((item) => {
      if (item.dataset.id === conversationId) {
        item.classList.add('active');
      } else {
        item.classList.remove('active');
      }
    });
  }

  async deleteConversation(id, event) {
    if (event) event.stopPropagation();

    if (!confirm('Are you sure you want to delete this conversation?')) {
      return;
    }

    try {
      await fetch(`/api/conversations/${id}`, { method: 'DELETE' });
    } catch (e) {
      console.warn('API delete failed, removing locally:', e);
    }

    this.conversations = this.conversations.filter((c) => c.id !== id);
    this.saveLocalConversations();
    this.renderConversations();

    if (this.activeConversationId === id) {
      if (this.onNewChat) this.onNewChat();
    }
  }

  renderConversations(filterQuery = '') {
    if (!this.conversationListEl) return;

    this.conversationListEl.innerHTML = '';

    const filtered = this.conversations.filter((c) => {
      if (!filterQuery) return true;
      const title = (c.title || 'New Chat').toLowerCase();
      return title.includes(filterQuery);
    });

    if (filtered.length === 0) {
      this.conversationListEl.innerHTML = `
        <div style="padding: 16px; font-size: 13px; color: var(--text-muted); text-align: center;">
          ${filterQuery ? 'No matching chats' : 'No previous conversations'}
        </div>
      `;
      return;
    }

    // Grouping by date
    const groups = this.groupByDate(filtered);

    for (const [groupName, convs] of Object.entries(groups)) {
      if (convs.length === 0) continue;

      const groupHeader = document.createElement('div');
      groupHeader.className = 'history-group-title';
      groupHeader.textContent = groupName;
      this.conversationListEl.appendChild(groupHeader);

      convs.forEach((conv) => {
        const item = document.createElement('div');
        item.className = 'conversation-item';
        item.dataset.id = conv.id;
        if (conv.id === this.activeConversationId) {
          item.classList.add('active');
        }

        const titleSpan = document.createElement('span');
        titleSpan.className = 'conversation-item-title';
        titleSpan.textContent = conv.title || 'New Chat';
        titleSpan.title = conv.title || 'New Chat';

        const actions = document.createElement('div');
        actions.className = 'conversation-item-actions';

        const deleteBtn = document.createElement('button');
        deleteBtn.className = 'conversation-action-btn delete-btn';
        deleteBtn.innerHTML = '🗑️';
        deleteBtn.title = 'Delete chat';
        deleteBtn.addEventListener('click', (e) => this.deleteConversation(conv.id, e));

        actions.appendChild(deleteBtn);
        item.appendChild(titleSpan);
        item.appendChild(actions);

        item.addEventListener('click', () => {
          this.setActive(conv.id);
          this.closeMobileSidebar();
          if (this.onSelectConversation) {
            this.onSelectConversation(conv);
          }
        });

        this.conversationListEl.appendChild(item);
      });
    }
  }

  groupByDate(conversations) {
    const now = new Date();
    const today = new Date(now.getFullYear(), now.getMonth(), now.getDate()).getTime();
    const yesterday = today - 86400000;
    const sevenDaysAgo = today - 7 * 86400000;

    const groups = {
      Today: [],
      Yesterday: [],
      'Previous 7 Days': [],
      Older: [],
    };

    conversations.forEach((conv) => {
      const date = conv.updated_at ? new Date(conv.updated_at).getTime() : Date.now();
      if (date >= today) {
        groups.Today.push(conv);
      } else if (date >= yesterday) {
        groups.Yesterday.push(conv);
      } else if (date >= sevenDaysAgo) {
        groups['Previous 7 Days'].push(conv);
      } else {
        groups.Older.push(conv);
      }
    });

    return groups;
  }
}
