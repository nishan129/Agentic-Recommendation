/**
 * app.js — shared UI glue used across every page: flash messages, the
 * mobile nav toggle, and small render helpers reused by products.js,
 * recommendations.js, and the homepage inline script.
 */
(function (global) {
  'use strict';

  // ---- Flash / toast messages -----------------------------------------
  const Flash = {
    show(message, type = 'info', timeout = 4500) {
      const stack = document.getElementById('flash-stack');
      if (!stack) return;
      const el = document.createElement('div');
      el.className = `flash flash-${type}`;
      el.setAttribute('role', 'status');
      el.innerHTML = `<span>${escapeHtml(message)}</span><button aria-label="Dismiss">&times;</button>`;
      el.querySelector('button').addEventListener('click', () => el.remove());
      stack.appendChild(el);
      if (timeout) setTimeout(() => el.remove(), timeout);
    },
  };

  function escapeHtml(str) {
    const div = document.createElement('div');
    div.textContent = str == null ? '' : String(str);
    return div.innerHTML;
  }

  function formatPrice(value) {
    const n = Number(value || 0);
    return '₹' + n.toLocaleString('en-IN', { maximumFractionDigits: 0 });
  }

  function ratingStars(rating) {
    if (rating === null || rating === undefined) return '';
    return `★ ${Number(rating).toFixed(1)}`;
  }

  /** Shared product card markup, used by products.js, home, recommendations. */
  function productCardHtml(product, options = {}) {
    const { position, source } = options;
    const img = product.image_url
      ? `<img src="${escapeHtml(product.image_url)}" alt="" loading="lazy">`
      : `<div class="placeholder">${escapeHtml((product.title || '?').charAt(0))}</div>`;
    return `
      <article class="product-card" data-product-id="${escapeHtml(product.id)}" data-position="${position ?? ''}" data-source="${escapeHtml(source || '')}">
        <a href="/products/${encodeURIComponent(product.id)}" class="product-card-media-link" data-track-click>
          <div class="product-card-media">
            ${img}
            <span class="product-card-type">${escapeHtml(product.product_type || 'product')}</span>
          </div>
        </a>
        <div class="product-card-body">
          <span class="badge badge-category">${escapeHtml(product.category || '')}</span>
          <h3 class="product-card-title">
            <a href="/products/${encodeURIComponent(product.id)}" data-track-click>${escapeHtml(product.title)}</a>
          </h3>
          <p class="product-card-desc">${escapeHtml(product.description || '')}</p>
          <div class="product-card-meta">
            <span class="rating">${ratingStars(product.rating)}</span>
            <span class="product-card-price">${formatPrice(product.price)}</span>
          </div>
        </div>
      </article>
    `;
  }

  function skeletonCards(count) {
    return Array.from({ length: count })
      .map(() => '<div class="skeleton skeleton-card"></div>')
      .join('');
  }

  function debounce(fn, wait) {
    let t;
    return (...args) => {
      clearTimeout(t);
      t = setTimeout(() => fn(...args), wait);
    };
  }

  function throttle(fn, wait) {
    let last = 0;
    let timer = null;
    return (...args) => {
      const now = Date.now();
      const remaining = wait - (now - last);
      if (remaining <= 0) {
        last = now;
        fn(...args);
      } else {
        clearTimeout(timer);
        timer = setTimeout(() => {
          last = Date.now();
          fn(...args);
        }, remaining);
      }
    };
  }

  function bindMobileNav() {
    const toggle = document.querySelector('.nav-toggle');
    const navbar = document.querySelector('.navbar');
    if (!toggle || !navbar) return;
    toggle.addEventListener('click', () => {
      const isOpen = navbar.classList.toggle('is-open');
      toggle.setAttribute('aria-expanded', String(isOpen));
    });
  }

  /**
   * Delegate clicks on any [data-track-click] product link to a
   * product_click event, tagged with position/source when the ancestor
   * card carries that data (set by productCardHtml above).
   */
  function bindProductClickTracking(root = document) {
    root.addEventListener('click', (e) => {
      const link = e.target.closest('[data-track-click]');
      if (!link) return;
      const card = link.closest('[data-product-id]');
      if (!card || !global.EventTracker) return;
      global.EventTracker.track({
        event_type: card.dataset.source === 'recommendation' ? 'recommendation_click' : 'product_click',
        product_id: card.dataset.productId,
        metadata: {
          position: card.dataset.position ? Number(card.dataset.position) : undefined,
          source: card.dataset.source || undefined,
        },
      });
    });
  }

  document.addEventListener('DOMContentLoaded', () => {
    bindMobileNav();
    bindProductClickTracking();
  });

  global.Flash = Flash;
  global.AppUI = { formatPrice, ratingStars, productCardHtml, skeletonCards, debounce, throttle, escapeHtml };
})(window);
