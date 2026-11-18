(() => {
  const base = window.FIELDNOTES_BASE || '.';
  const root = document.documentElement;
  const theme = document.querySelector('.theme-trigger');
  function reflectTheme() {
    const night = root.dataset.theme === 'night';
    theme.setAttribute('aria-pressed', String(night));
    theme.setAttribute('aria-label', night ? 'Switch to paper mode' : 'Switch to night ink');
    theme.querySelector('span').textContent = night ? 'Paper mode' : 'Night ink';
  }
  reflectTheme();
  theme.addEventListener('click', () => {
    root.dataset.theme = root.dataset.theme === 'night' ? 'paper' : 'night';
    try { localStorage.setItem('dg-docs-theme', root.dataset.theme); } catch (_) {}
    reflectTheme();
  });
  const menu = document.querySelector('.menu-trigger');
  menu.addEventListener('click', () => {
    const open = document.body.classList.toggle('nav-open');
    menu.setAttribute('aria-expanded', String(open));
    menu.textContent = open ? 'Close' : 'Contents';
  });
  document.querySelectorAll('.prose pre').forEach(pre => {
    const shell = document.createElement('div'); shell.className = 'code-shell';
    const meta = document.createElement('div'); meta.className = 'code-meta';
    const label = document.createElement('span');
    const code = pre.querySelector('code');
    label.textContent = code?.className.replace('language-', '').toUpperCase() || 'EXAMPLE';
    const button = document.createElement('button'); button.type = 'button'; button.className = 'copy-code'; button.textContent = 'Copy';
    button.setAttribute('aria-label', `Copy ${label.textContent.toLowerCase()} example`);
    button.addEventListener('click', async () => {
      try { await navigator.clipboard.writeText(code ? code.textContent : pre.textContent); button.textContent = 'Copied'; }
      catch (_) { button.textContent = 'Select text'; const range = document.createRange(); range.selectNodeContents(code || pre); const selection = window.getSelection(); selection.removeAllRanges(); selection.addRange(range); }
      setTimeout(() => { button.textContent = 'Copy'; }, 1800);
    });
    meta.append(label, button); pre.before(shell); shell.append(meta, pre);
  });
  document.querySelectorAll('.prose table:not(.delivery-calendar)').forEach(table => {
    const wrapper = document.createElement('div'); wrapper.className = 'table-wrap'; wrapper.tabIndex = 0;
    wrapper.setAttribute('role', 'region'); wrapper.setAttribute('aria-label', 'Scrollable documentation table');
    table.before(wrapper); wrapper.append(table);
  });
  const dialog = document.querySelector('.search-dialog');
  const input = document.querySelector('#fieldnotes-search');
  const results = document.querySelector('.search-results');
  let docs, indexRequest;
  async function loadIndex() {
    if (docs) return docs;
    if (!indexRequest) indexRequest = fetch(`${base}/search/search_index.json`).then(response => { if (!response.ok) throw new Error('Search unavailable'); return response.json(); }).then(index => docs = index.docs);
    return indexRequest;
  }
  function openSearch() { dialog.showModal(); input.focus(); loadIndex().catch(() => {}); }
  document.querySelector('[data-open-search]').addEventListener('click', openSearch);
  document.querySelector('.close-search').addEventListener('click', () => dialog.close());
  dialog.addEventListener('click', event => { if (event.target === dialog) { const box = dialog.getBoundingClientRect(); if (event.clientX < box.left || event.clientX > box.right || event.clientY < box.top || event.clientY > box.bottom) dialog.close(); } });
  document.addEventListener('keydown', event => {
    if (event.key === '/' && !['INPUT', 'TEXTAREA'].includes(document.activeElement.tagName)) { event.preventDefault(); openSearch(); }
    if (event.key === 'Escape') { document.body.classList.remove('nav-open'); menu.setAttribute('aria-expanded', 'false'); menu.textContent = 'Contents'; }
  });
  input.addEventListener('input', async () => {
    const query = input.value.trim().toLowerCase(); results.replaceChildren();
    if (!query) { const p = document.createElement('p'); p.textContent = 'Search the guide, configuration and recorded proof.'; results.append(p); return; }
    try {
      const pages = await loadIndex();
      if (input.value.trim().toLowerCase() !== query) return;
      const terms = query.split(/\s+/);
      const matches = pages.map(doc => ({ ...doc, score: terms.reduce((n, term) => n + (doc.title.toLowerCase().includes(term) ? 6 : 0) + (doc.text.toLowerCase().includes(term) ? 1 : 0), 0) })).filter(doc => terms.every(term => `${doc.title} ${doc.text}`.toLowerCase().includes(term))).sort((a, b) => b.score - a.score).slice(0, 8);
      if (!matches.length) { const p = document.createElement('p'); p.textContent = 'No matches. Try an endpoint, policy name or a shorter term.'; results.append(p); }
      matches.forEach(doc => { const a = document.createElement('a'); a.className = 'search-result'; a.href = `${base}/${doc.location}`; const title = document.createElement('strong'); title.textContent = doc.title; const snippet = document.createElement('p'); const where = Math.max(0, doc.text.toLowerCase().indexOf(terms[0]) - 50); snippet.textContent = doc.text.slice(where, where + 145) + '…'; a.append(title, snippet); results.append(a); });
    } catch (_) { const p = document.createElement('p'); p.textContent = 'Search needs the local preview server. The contents and all document pages remain available.'; results.append(p); }
  });
})();
