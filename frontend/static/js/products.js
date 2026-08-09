/**
 * products.js — drives the /products listing page: debounced search,
 * category/price filters, sorting, and pagination, all against
 * GET /api/v1/products.
 */
(function (global) {
  'use strict';

  const { productCardHtml, skeletonCards, debounce } = global.AppUI;

  const grid = document.getElementById('product-grid');
  if (!grid) return; // not on the listing page

  const searchInput = document.getElementById('product-search-input');
  const searchBarEl = document.getElementById('product-search-bar');
  const categoryChecks = () => Array.from(document.querySelectorAll('[name="category-filter"]'));
  const minPriceInput = document.getElementById('min-price');
  const maxPriceInput = document.getElementById('max-price');
  const sortSelect = document.getElementById('sort-select');
  const resultsCount = document.getElementById('results-count');
  const paginationEl = document.getElementById('pagination');
  const emptyStateTpl = document.getElementById('empty-state-template');
  const clearFiltersBtn = document.getElementById('clear-filters');

  const state = {
    page: 1,
    limit: 12,
    search: new URLSearchParams(location.search).get('search') || '',
    category: new URLSearchParams(location.search).get('category') || '',
    min_price: '',
    max_price: '',
    sort_by: 'created_at',
    sort_desc: true,
  };

  if (searchInput && state.search) searchInput.value = state.search;

  function syncUrl() {
    const params = new URLSearchParams();
    if (state.search) params.set('search', state.search);
    if (state.category) params.set('category', state.category);
    if (state.page > 1) params.set('page', state.page);
    const qs = params.toString();
    history.replaceState(null, '', qs ? `?${qs}` : location.pathname);
  }

  async function loadProducts() {
    grid.setAttribute('aria-busy', 'true');
    grid.innerHTML = skeletonCards(state.limit);
    if (searchBarEl) searchBarEl.classList.add('is-searching');

    try {
      const data = await global.Api.getProducts({
        page: state.page,
        limit: state.limit,
        search: state.search || undefined,
        category: state.category || undefined,
        min_price: state.min_price || undefined,
        max_price: state.max_price || undefined,
        sort_by: state.sort_by,
        sort_desc: state.sort_desc,
      });
      renderResults(data);
    } catch (err) {
      grid.innerHTML = '';
      global.Flash
        ? global.Flash.show('Could not load products right now. Please try again shortly.', 'error')
        : null;
      showEmptyState('Products are temporarily unavailable.', 'Please refresh the page in a moment.');
    } finally {
      grid.removeAttribute('aria-busy');
      if (searchBarEl) searchBarEl.classList.remove('is-searching');
    }
  }

  function renderResults(data) {
    const items = (data && data.items) || [];
    const meta = (data && data.meta) || { total: 0, page: 1, total_pages: 1 };

    if (resultsCount) {
      resultsCount.textContent = meta.total === 0
        ? 'No results'
        : `${meta.total} result${meta.total === 1 ? '' : 's'}`;
    }

    if (items.length === 0) {
      grid.innerHTML = '';
      showEmptyState('No products found.', 'Try another search term or category.');
      renderPagination(meta);
      return;
    }

    grid.innerHTML = items.map((p, i) => productCardHtml(p, { position: i, source: 'listing' })).join('');
    global.AppUI.revealGrid(grid);
    renderPagination(meta);
  }

  function showEmptyState(title, subtitle) {
    if (!emptyStateTpl) return;
    const clone = emptyStateTpl.content.cloneNode(true);
    clone.querySelector('h3').textContent = title;
    clone.querySelector('p').textContent = subtitle;
    grid.appendChild(clone);
  }

  function renderPagination(meta) {
    if (!paginationEl) return;
    const { page, total_pages } = meta;
    if (!total_pages || total_pages <= 1) {
      paginationEl.innerHTML = '';
      return;
    }

    let html = `<button data-page="${page - 1}" ${page <= 1 ? 'disabled' : ''} aria-label="Previous page">‹</button>`;
    const windowStart = Math.max(1, page - 2);
    const windowEnd = Math.min(total_pages, page + 2);
    if (windowStart > 1) html += `<button data-page="1">1</button>${windowStart > 2 ? '<span>…</span>' : ''}`;
    for (let p = windowStart; p <= windowEnd; p++) {
      html += `<button data-page="${p}" class="${p === page ? 'active' : ''}" aria-current="${p === page ? 'page' : 'false'}">${p}</button>`;
    }
    if (windowEnd < total_pages) html += `${windowEnd < total_pages - 1 ? '<span>…</span>' : ''}<button data-page="${total_pages}">${total_pages}</button>`;
    html += `<button data-page="${page + 1}" ${page >= total_pages ? 'disabled' : ''} aria-label="Next page">›</button>`;

    paginationEl.innerHTML = html;
    paginationEl.querySelectorAll('button[data-page]').forEach((btn) => {
      btn.addEventListener('click', () => {
        const p = Number(btn.dataset.page);
        if (!p || p === state.page) return;
        state.page = p;
        syncUrl();
        loadProducts();
        grid.scrollIntoView({ behavior: 'smooth', block: 'start' });
      });
    });
  }

  // ---- Search (debounced, never one request per keystroke) -----------
  const runSearch = debounce((value) => {
    state.search = value.trim();
    state.page = 1;
    syncUrl();
    loadProducts();
    if (state.search && global.EventTracker) {
      global.EventTracker.track({ event_type: 'search', search_query: state.search, metadata: { query: state.search } });
    }
  }, 400);

  if (searchInput) {
    searchInput.addEventListener('input', (e) => runSearch(e.target.value));
  }

  // ---- Filters ---------------------------------------------------------
  document.addEventListener('change', (e) => {
    if (e.target.name === 'category-filter') {
      const checked = categoryChecks().filter((c) => c.checked);
      state.category = checked.length ? checked[checked.length - 1].value : '';
      // Single-select behavior for simplicity/clarity — uncheck the rest.
      categoryChecks().forEach((c) => { if (c !== checked[checked.length - 1]) c.checked = false; });
      state.page = 1;
      syncUrl();
      if (state.category && global.EventTracker) {
        global.EventTracker.track({ event_type: 'category_view', metadata: { category: state.category } });
      }
      loadProducts();
    }
  });

  const applyPriceFilter = debounce(() => {
    state.min_price = minPriceInput ? minPriceInput.value : '';
    state.max_price = maxPriceInput ? maxPriceInput.value : '';
    state.page = 1;
    loadProducts();
  }, 500);

  if (minPriceInput) minPriceInput.addEventListener('input', applyPriceFilter);
  if (maxPriceInput) maxPriceInput.addEventListener('input', applyPriceFilter);

  if (sortSelect) {
    sortSelect.addEventListener('change', () => {
      const [sortBy, dir] = sortSelect.value.split(':');
      state.sort_by = sortBy;
      state.sort_desc = dir !== 'asc';
      state.page = 1;
      loadProducts();
    });
  }

  if (clearFiltersBtn) {
    clearFiltersBtn.addEventListener('click', () => {
      state.category = '';
      state.min_price = '';
      state.max_price = '';
      state.search = '';
      state.page = 1;
      if (searchInput) searchInput.value = '';
      if (minPriceInput) minPriceInput.value = '';
      if (maxPriceInput) maxPriceInput.value = '';
      categoryChecks().forEach((c) => (c.checked = false));
      syncUrl();
      loadProducts();
    });
  }

  loadProducts();
})(window);
