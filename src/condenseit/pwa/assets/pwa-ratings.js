/* global window, document, fetch, Blob, URL, MutationObserver */
/**
 * Inline star-rating for the static PWA.
 *
 * Ratings are persisted to localStorage. After all page scripts run,
 * this script injects a 1-5 star widget at the bottom of every item card
 * rendered by digest-filter.js (which attaches data-url on each card).
 * A small download-bar appears at the bottom of the page once one item
 * has been rated.
 */
(function () {
  'use strict';

  const cfgEl = document.getElementById('condenseit-pwa-ratings-cfg');
  if (!cfgEl) {
    return;
  }

  let cfg = { mergeUrl: '', digestId: 0 };
  try {
    cfg = JSON.parse(cfgEl.textContent || '{}');
  } catch (_e) {
    return;
  }

  const LS_KEY = 'condenseit_pwa_ratings_v1';

  /** @returns {{ v: number, byUrl: Record<string, number> }} */
  function readStore() {
    try {
      const raw = window.localStorage.getItem(LS_KEY);
      if (!raw) {
        return { v: 1, byUrl: {} };
      }
      const o = JSON.parse(raw);
      if (!o || typeof o !== 'object' || typeof o.byUrl !== 'object') {
        return { v: 1, byUrl: {} };
      }
      return { v: 1, byUrl: o.byUrl };
    } catch (_e2) {
      return { v: 1, byUrl: {} };
    }
  }

  /** @param {{ v: number, byUrl: Record<string, number> }} st */
  function writeStore(st) {
    window.localStorage.setItem(LS_KEY, JSON.stringify(st));
  }

  /**
   * @param {unknown} data
   * @returns {Record<string, number>}
   */
  function normalizeRemoteRatings(data) {
    const out = {};
    if (!data || typeof data !== 'object') {
      return out;
    }
    const list = Array.isArray(data.ratings)
      ? data.ratings
      : Array.isArray(data.entries)
        ? data.entries
        : Array.isArray(data)
          ? data
          : [];
    for (let i = 0; i < list.length; i += 1) {
      const row = list[i];
      if (!row || typeof row !== 'object') {
        continue;
      }
      const u = String(row.url || '').trim();
      const r = parseInt(String(row.rating), 10);
      if (!u || r < 1 || r > 5) {
        continue;
      }
      out[u] = r;
    }
    return out;
  }

  /**
   * @param {{ byUrl: Record<string, number> }} st
   * @param {Record<string, number>} remoteMap
   */
  function mergeRemoteIntoLocal(st, remoteMap) {
    const keys = Object.keys(remoteMap);
    for (let i = 0; i < keys.length; i += 1) {
      const u = keys[i];
      if (!Object.prototype.hasOwnProperty.call(st.byUrl, u)) {
        st.byUrl[u] = remoteMap[u];
      }
    }
  }

  /** @param {{ byUrl: Record<string, number> }} st */
  function exportPayload(st) {
    const ratings = [];
    const keys = Object.keys(st.byUrl);
    for (let i = 0; i < keys.length; i += 1) {
      const u = keys[i];
      ratings.push({ url: u, rating: st.byUrl[u] });
    }
    return {
      version: 1,
      digest_id: cfg.digestId,
      exported_at: new Date().toISOString(),
      source: 'condenseit-pwa',
      ratings: ratings,
    };
  }

  /**
   * Build a star-row element for one item URL.
   * @param {string} url
   * @param {{ byUrl: Record<string, number> }} st
   * @param {function(): void} onAfterRate - called after a star click to refresh download bar
   * @returns {HTMLElement}
   */
  function buildStars(url, st, onAfterRate) {
    const wrap = document.createElement('div');
    wrap.className = 'pwa-stars-row';

    const LABELS = ['Terrible', 'Poor', 'OK', 'Good', 'Excellent'];
    const cur = st.byUrl[url] || 0;

    for (let s = 1; s <= 5; s += 1) {
      const b = document.createElement('button');
      b.type = 'button';
      b.className = 'pwa-star' + (cur >= s ? ' pwa-star--on' : '');
      b.textContent = String(s);
      b.title = LABELS[s - 1];
      b.setAttribute('aria-label', 'Rate ' + s + ' star' + (s !== 1 ? 's' : ''));

      b.addEventListener('click', function () {
        st.byUrl[url] = s;
        writeStore(st);
        // Refresh active state on all buttons in this row.
        const siblings = wrap.querySelectorAll('.pwa-star');
        for (let i = 0; i < siblings.length; i += 1) {
          siblings[i].classList.toggle('pwa-star--on', i < s);
        }
        onAfterRate();
      });

      wrap.appendChild(b);
    }

    // Flash indicator that appears briefly after rating.
    const flash = document.createElement('span');
    flash.className = 'pwa-star-saved';
    flash.textContent = 'Saved';
    wrap.appendChild(flash);

    wrap.addEventListener('click', function (ev) {
      if (ev.target && ev.target.classList && ev.target.classList.contains('pwa-star')) {
        flash.classList.add('pwa-star-saved--visible');
        setTimeout(function () {
          flash.classList.remove('pwa-star-saved--visible');
        }, 2000);
      }
    });

    return wrap;
  }

  /**
   * Inject a star row into each digest card that has a data-url attribute.
   * @param {{ byUrl: Record<string, number> }} st
   * @param {function(): void} onAfterRate
   */
  function injectStarsIntoCards(st, onAfterRate) {
    const cards = document.querySelectorAll('[data-url]');
    for (let i = 0; i < cards.length; i += 1) {
      const card = cards[i];
      const url = card.getAttribute('data-url');
      if (!url) {
        continue;
      }
      // Avoid double-injecting on re-renders triggered by filter changes.
      if (card.querySelector('.pwa-stars-row')) {
        continue;
      }
      const divider = document.createElement('div');
      divider.className = 'pwa-stars-divider';
      card.appendChild(divider);
      card.appendChild(buildStars(url, st, onAfterRate));
    }
  }

  /** Show/hide the download toolbar based on how many items are rated. */
  function refreshDownloadBar(st, bar) {
    const count = Object.keys(st.byUrl).length;
    if (count === 0) {
      bar.classList.add('pwa-dl-bar--hidden');
    } else {
      bar.classList.remove('pwa-dl-bar--hidden');
      const countEl = bar.querySelector('.pwa-dl-bar-count');
      if (countEl) {
        countEl.textContent =
          count + ' item' + (count !== 1 ? 's' : '') + ' rated.';
      }
    }
  }

  /**
   * Append the download-bar below the digest list.
   * @param {{ byUrl: Record<string, number> }} st
   * @returns {HTMLElement} the bar element
   */
  function buildDownloadBar(st) {
    const bar = document.createElement('div');
    bar.className =
      'pwa-dl-bar' + (Object.keys(st.byUrl).length === 0 ? ' pwa-dl-bar--hidden' : '');

    const hint = document.createElement('p');
    hint.className = 'pwa-dl-bar-hint';

    const countEl = document.createElement('span');
    countEl.className = 'pwa-dl-bar-count';
    hint.appendChild(countEl);

    const hintText = document.createTextNode(
      ' Export and run condenseit ratings-import before the next digest.',
    );
    hint.appendChild(hintText);
    bar.appendChild(hint);

    const btn = document.createElement('button');
    btn.type = 'button';
    btn.className = 'btn btn-sm';
    btn.textContent = 'Download ratings JSON';
    btn.addEventListener('click', function () {
      const body = JSON.stringify(exportPayload(st), null, 2);
      const blob = new Blob([body], { type: 'application/json' });
      const a = document.createElement('a');
      a.href = URL.createObjectURL(blob);
      a.download = 'condenseit-ratings.json';
      a.click();
      URL.revokeObjectURL(a.href);
    });
    bar.appendChild(btn);

    refreshDownloadBar(st, bar);
    return bar;
  }

  const root = document.getElementById('pwa-ratings-root');
  if (!root) {
    return;
  }

  // Fetch remote ratings (optional), then inject stars and download bar.
  Promise.resolve()
    .then(function () {
      const mu = String(cfg.mergeUrl || '').trim();
      if (!mu) {
        return null;
      }
      return fetch(mu, { cache: 'no-store' }).then(function (res) {
        return res.ok ? res.json() : null;
      });
    })
    .then(function (remoteDoc) {
      const st = readStore();
      if (remoteDoc) {
        mergeRemoteIntoLocal(st, normalizeRemoteRatings(remoteDoc));
        writeStore(st);
      }

      // Build the download bar and attach it to the root placeholder.
      const bar = buildDownloadBar(st);
      root.appendChild(bar);

      function onAfterRate() {
        refreshDownloadBar(st, bar);
      }

      // Inject stars into cards already in the DOM.
      injectStarsIntoCards(st, onAfterRate);

      // Watch for new cards injected by digest-filter.js when filters change.
      const observer = new MutationObserver(function () {
        injectStarsIntoCards(st, onAfterRate);
      });
      const listEl = document.getElementById('digest-item-list');
      if (listEl) {
        observer.observe(listEl, { childList: true, subtree: false });
      }
    })
    .catch(function () {
      /* silently fail — ratings are best-effort */
    });
})();
