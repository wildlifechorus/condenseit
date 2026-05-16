/**
 * Client-side digest item filters (localhost UI and static PWA).
 * Expects JSON in #condenseit-digest-items-data and DOM hooks in #digest-browse-root.
 */
(function () {
  'use strict';

  const root = document.getElementById('digest-browse-root');
  const dataEl = document.getElementById('condenseit-digest-items-data');
  const listEl = document.getElementById('digest-item-list');
  const emptyEl = document.getElementById('digest-filter-empty');
  const countEl = document.getElementById('digest-filter-count');
  const searchEl = document.getElementById('digest-filter-search');
  const catEl = document.getElementById('digest-filter-category');
  const srcEl = document.getElementById('digest-filter-source');
  const kindEl = document.getElementById('digest-filter-kind');
  const fromEl = document.getElementById('digest-filter-date-from');
  const toEl = document.getElementById('digest-filter-date-to');
  const resetBtn = document.getElementById('digest-filter-reset');

  if (!root || !dataEl || !listEl || !emptyEl || !countEl) {
    return;
  }

  let items = [];
  try {
    items = JSON.parse(dataEl.textContent || '[]');
  } catch (_err) {
    root.classList.add('is-hidden');
    return;
  }

  if (!Array.isArray(items) || items.length === 0) {
    root.classList.add('is-hidden');
    return;
  }

  /**
   * @param {string} iso
   * @returns {string}
   */
  function datePart(iso) {
    if (!iso || typeof iso !== 'string') {
      return '';
    }
    return iso.slice(0, 10);
  }

  /**
   * @param {Record<string, unknown>} it
   * @returns {string}
   */
  function haystack(it) {
    const parts = [
      it.title,
      it.summary,
      it.source,
      it.category,
      it.url,
      it.kind,
    ];
    return parts
      .filter((p) => typeof p === 'string' && p.length > 0)
      .join(' ')
      .toLowerCase();
  }

  /**
   * @param {Record<string, unknown>} it
   * @returns {boolean}
   */
  function passesDate(it) {
    const from = fromEl && fromEl.value ? fromEl.value : '';
    const to = toEl && toEl.value ? toEl.value : '';
    if (!from && !to) {
      return true;
    }
    const d = datePart(String(it.published_at || ''));
    if (!d) {
      return false;
    }
    if (from && d < from) {
      return false;
    }
    if (to && d > to) {
      return false;
    }
    return true;
  }

  /**
   * @param {Record<string, unknown>} it
   * @returns {boolean}
   */
  function passes(it) {
    const q = (searchEl && searchEl.value ? searchEl.value : '').trim().toLowerCase();
    if (q && !haystack(it).includes(q)) {
      return false;
    }
    const cat = catEl && catEl.value ? catEl.value : '';
    if (cat && String(it.category || '') !== cat) {
      return false;
    }
    const src = srcEl && srcEl.value ? srcEl.value : '';
    if (src && String(it.source || '') !== src) {
      return false;
    }
    const kind = kindEl && kindEl.value ? kindEl.value : '';
    if (kind && String(it.kind || '') !== kind) {
      return false;
    }
    if (!passesDate(it)) {
      return false;
    }
    return true;
  }

  /**
   * @param {Record<string, unknown>} it
   * @returns {HTMLElement}
   */
  function renderCard(it) {
    const li = document.createElement('li');
    li.className = 'digest-item-card';
    // data-url lets pwa-ratings.js inject inline star widgets into each card.
    const itemUrl = String(it.url || '').trim();
    if (itemUrl) {
      li.setAttribute('data-url', itemUrl);
    }
    const kind = String(it.kind || 'article');
    const badge = document.createElement('span');
    badge.className = 'digest-item-kind';
    badge.setAttribute('aria-hidden', 'true');
    badge.textContent = kind;

    const title = document.createElement('h3');
    title.className = 'digest-item-title';
    const link = document.createElement('a');
    link.href = String(it.url || '#');
    link.rel = 'noopener noreferrer';
    link.target = '_blank';
    link.textContent = String(it.title || 'Untitled');
    title.appendChild(link);

    const meta = document.createElement('p');
    meta.className = 'digest-item-meta';
    const cat = String(it.category || '');
    const src = String(it.source || '');
    const when = datePart(String(it.published_at || ''));
    const bits = [];
    if (cat) {
      bits.push(cat);
    }
    if (src) {
      bits.push(src);
    }
    if (when) {
      bits.push(when);
    }
    meta.textContent = bits.join(' · ');

    const body = document.createElement('p');
    body.className = 'digest-item-summary';
    const sum = String(it.summary || '').trim();
    body.textContent = sum || 'No summary for this item.';

    li.appendChild(badge);
    li.appendChild(title);
    li.appendChild(meta);
    li.appendChild(body);
    return li;
  }

  function fillSelect(select, values) {
    if (!select) {
      return;
    }
    const cur = select.value;
    while (select.options.length > 1) {
      select.remove(1);
    }
    values.forEach((v) => {
      const opt = document.createElement('option');
      opt.value = v;
      opt.textContent = v;
      select.appendChild(opt);
    });
    if (values.includes(cur)) {
      select.value = cur;
    } else {
      select.selectedIndex = 0;
    }
  }

  function uniqueSorted(getter) {
    const set = new Set();
    items.forEach((it) => {
      const v = getter(it);
      if (v) {
        set.add(v);
      }
    });
    return Array.from(set).sort((a, b) => a.localeCompare(b));
  }

  function applyFilters() {
    const matched = items.filter((it) => passes(it));
    listEl.innerHTML = '';
    matched.forEach((it) => {
      listEl.appendChild(renderCard(it));
    });
    const n = matched.length;
    countEl.textContent =
      n === items.length
        ? `Showing all ${n} item${n === 1 ? '' : 's'}`
        : `Showing ${n} of ${items.length} item${items.length === 1 ? '' : 's'}`;
    emptyEl.classList.toggle('is-hidden', n > 0);
    listEl.classList.toggle('is-hidden', n === 0);
  }

  function wire() {
    fillSelect(catEl, uniqueSorted((it) => String(it.category || '')));
    fillSelect(srcEl, uniqueSorted((it) => String(it.source || '')));
    if (resetBtn) {
      resetBtn.addEventListener('click', () => {
        if (searchEl) {
          searchEl.value = '';
        }
        if (catEl) {
          catEl.selectedIndex = 0;
        }
        if (srcEl) {
          srcEl.selectedIndex = 0;
        }
        if (kindEl) {
          kindEl.selectedIndex = 0;
        }
        if (fromEl) {
          fromEl.value = '';
        }
        if (toEl) {
          toEl.value = '';
        }
        applyFilters();
        if (searchEl) {
          searchEl.focus();
        }
      });
    }
    const rerender = () => {
      applyFilters();
    };
    if (searchEl) {
      let t = null;
      searchEl.addEventListener('input', () => {
        if (t) {
          clearTimeout(t);
        }
        t = setTimeout(rerender, 160);
      });
    }
    [catEl, srcEl, kindEl, fromEl, toEl].forEach((el) => {
      if (el) {
        el.addEventListener('change', rerender);
      }
    });
  }

  wire();
  applyFilters();
})();
