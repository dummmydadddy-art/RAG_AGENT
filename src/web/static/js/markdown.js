/**
 * 3-Stage KaTeX + Marked.js Markdown Pipeline
 * Extracts LaTeX formulas prior to markdown compilation to protect underscores and asterisks from mangling,
 * then compiles Markdown, and hydrates KaTeX mathematical formulas into SVG/HTML.
 */

export class MarkdownRenderer {
  constructor() {
    if (typeof marked !== 'undefined') {
      marked.setOptions({
        gfm: true,
        breaks: true,
        headerIds: false,
        mangle: false,
      });
    }
  }

  render(rawMarkdown) {
    if (!rawMarkdown) return '';

    const mathBlocks = [];
    const mathInlines = [];

    // Stage 1: Protect Block Math ($$ ... $$)
    let processed = rawMarkdown.replace(/\$\$([\s\S]+?)\$\$/g, (match, formula) => {
      const idx = mathBlocks.length;
      mathBlocks.push(formula.trim());
      return `%%%KATEX_BLOCK_${idx}%%%`;
    });

    // Stage 2: Protect Inline Math ($ ... $)
    // We enforce non-space boundary right after opening $ and right before closing $,
    // and exclude pure currency figures like "$100" by checking if it matches isolated currency
    processed = processed.replace(/(?<!\\|\$)\$([^\s\$][^\$\n]*?[^\s\\\$])\$(?!\$)/g, (match, formula) => {
      // Check if formula is merely an ordinary number/currency (e.g., "100" or "50.00")
      if (/^\d+(?:,\d{3})*(?:\.\d+)?$/.test(formula.trim())) {
        return match; // Keep as plain currency
      }
      const idx = mathInlines.length;
      mathInlines.push(formula.trim());
      return `%%%KATEX_INLINE_${idx}%%%`;
    });

    // Also support single-character variables like $x$ or $v$
    processed = processed.replace(/(?<!\\|\$)\$([a-zA-Z0-9])\$(?!\$)/g, (match, formula) => {
      const idx = mathInlines.length;
      mathInlines.push(formula.trim());
      return `%%%KATEX_INLINE_${idx}%%%`;
    });

    // Stage 3: Parse Markdown with Marked.js
    let html = '';
    if (typeof marked !== 'undefined') {
      html = marked.parse(processed);
    } else {
      // Fallback simple line breaker if Marked fails to load
      html = processed.replace(/\n/g, '<br>');
    }

    // Stage 4: Hydrate Block Math with KaTeX
    html = html.replace(/%%%KATEX_BLOCK_(\d+)%%%/g, (match, idxStr) => {
      const idx = Number(idxStr);
      const formula = mathBlocks[idx] || '';
      try {
        if (typeof katex !== 'undefined') {
          return `<div class="math-block">${katex.renderToString(formula, { displayMode: true, throwOnError: false })}</div>`;
        }
      } catch (e) {
        console.warn('KaTeX block rendering error:', e);
      }
      return `<pre class="math-raw">$$${this.escapeHtml(formula)}$$</pre>`;
    });

    // Stage 5: Hydrate Inline Math with KaTeX
    html = html.replace(/%%%KATEX_INLINE_(\d+)%%%/g, (match, idxStr) => {
      const idx = Number(idxStr);
      const formula = mathInlines[idx] || '';
      try {
        if (typeof katex !== 'undefined') {
          return `<span class="math-inline">${katex.renderToString(formula, { displayMode: false, throwOnError: false })}</span>`;
        }
      } catch (e) {
        console.warn('KaTeX inline rendering error:', e);
      }
      return `<code class="math-raw">$${this.escapeHtml(formula)}</code>`;
    });

    return html;
  }

  escapeHtml(str) {
    return str
      .replace(/&/g, '&amp;')
      .replace(/</g, '&lt;')
      .replace(/>/g, '&gt;')
      .replace(/"/g, '&quot;')
      .replace(/'/g, '&#039;');
  }
}
