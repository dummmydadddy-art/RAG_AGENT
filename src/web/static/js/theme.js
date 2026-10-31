/**
 * Theme Manager for ChatGPT Web Interface
 * Handles Dark / Light mode switching, persistence, and OS preference detection.
 */

export class ThemeManager {
  constructor() {
    this.STORAGE_KEY = 'rag_agent_theme';
    const savedTheme = localStorage.getItem(this.STORAGE_KEY);
    
    if (savedTheme) {
      this.currentTheme = savedTheme;
    } else if (window.matchMedia && window.matchMedia('(prefers-color-scheme: light)').matches) {
      this.currentTheme = 'light';
    } else {
      this.currentTheme = 'dark';
    }

    this.applyTheme(this.currentTheme);
    this.initListeners();
  }

  toggle() {
    this.currentTheme = this.currentTheme === 'dark' ? 'light' : 'dark';
    this.applyTheme(this.currentTheme);
    localStorage.setItem(this.STORAGE_KEY, this.currentTheme);
    return this.currentTheme;
  }

  applyTheme(theme) {
    document.documentElement.setAttribute('data-theme', theme);
    const toggleBtn = document.getElementById('theme-toggle-btn');
    if (toggleBtn) {
      toggleBtn.innerHTML = theme === 'dark' ? '🌙' : '☀️';
      toggleBtn.title = `Switch to ${theme === 'dark' ? 'Light' : 'Dark'} mode`;
    }
  }

  initListeners() {
    const toggleBtn = document.getElementById('theme-toggle-btn');
    if (toggleBtn) {
      toggleBtn.addEventListener('click', () => this.toggle());
    }

    if (window.matchMedia) {
      window.matchMedia('(prefers-color-scheme: light)').addEventListener('change', (e) => {
        if (!localStorage.getItem(this.STORAGE_KEY)) {
          this.currentTheme = e.matches ? 'light' : 'dark';
          this.applyTheme(this.currentTheme);
        }
      });
    }
  }
}
