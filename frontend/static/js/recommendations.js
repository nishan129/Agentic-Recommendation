/**
 * recommendations.js — fetches personalized recommendations and renders
 * them wherever a `[data-recommendations-target]` container exists (the
 * homepage "Recommended For You" section and the dedicated /recommendations
 * page both use this). Tracks `recommendation_view` once per card the
 * first time it's rendered, and relies on app.js's delegated click
 * handler for `recommendation_click`.
 */
(function (global) {
  'use strict';

  const { skeletonCards, formatPrice, ratingStars, escapeHtml } = global.AppUI;

  function recommendationCardHtml(item, position) {
    return `
      <article class="recommendation-card" data-product-id="${escapeHtml(item.product_id)}" data-position="${position}" data-source="recommendation">
        <span class="score-chip">${Math.round(item.score * 100)}% match</span>
        <span class="badge badge-category">${escapeHtml(item.reason ? '' : '')}</span>
        <h3 class="product-card-title">
          <a href="/products/${encodeURIComponent(item.product_id)}" data-track-click>${escapeHtml(item.title)}</a>
        </h3>
        <p class="recommendation-reason">${escapeHtml(item.reason)}</p>
        <div class="product-card-meta">
          <span class="rating">${ratingStars(null)}</span>
        </div>
        <a href="/products/${encodeURIComponent(item.product_id)}" class="btn btn-outline btn-sm btn-block" data-track-click>View course</a>
      </article>
    `;
  }

  async function renderRecommendations(container, { limit = 8, emptyMessage } = {}) {
    if (!container) return;
    container.innerHTML = skeletonCards(Math.min(limit, 4));
    container.setAttribute('aria-busy', 'true');

    try {
      const data = await global.Api.getRecommendations(limit);
      const items = (data && data.recommendations) || [];

      if (items.length === 0) {
        container.innerHTML = `
          <div class="empty-state">
            <div class="icon">✦</div>
            <h3>No recommendations yet</h3>
            <p>${escapeHtml(emptyMessage || "Explore a few products and we'll personalize your recommendations.")}</p>
            <a href="/products" class="btn btn-accent">Explore products</a>
          </div>`;
        return;
      }

      container.innerHTML = items.map((item, i) => recommendationCardHtml(item, i)).join('');

      // Track a view per surfaced recommendation, once, using an
      // IntersectionObserver so we only count cards that actually
      // scroll into view rather than everything rendered off-screen.
      if (global.EventTracker && 'IntersectionObserver' in global) {
        const seen = new Set();
        const observer = new IntersectionObserver((entries) => {
          entries.forEach((entry) => {
            if (!entry.isIntersecting) return;
            const el = entry.target;
            const productId = el.dataset.productId;
            if (seen.has(productId)) return;
            seen.add(productId);
            global.EventTracker.track({
              event_type: 'recommendation_view',
              product_id: productId,
              metadata: { position: Number(el.dataset.position) },
            });
            observer.unobserve(el);
          });
        }, { threshold: 0.5 });

        container.querySelectorAll('[data-product-id]').forEach((el) => observer.observe(el));
      }
    } catch (err) {
      container.innerHTML = `
        <div class="empty-state">
          <div class="icon">⚠</div>
          <h3>Recommendations are temporarily unavailable</h3>
          <p>Please check back in a little while.</p>
        </div>`;
    } finally {
      container.removeAttribute('aria-busy');
    }
  }

  document.addEventListener('DOMContentLoaded', () => {
    document.querySelectorAll('[data-recommendations-target]').forEach((container) => {
      const limit = Number(container.dataset.recommendationsLimit) || 8;
      // Only fetch personalized recommendations once we know the user is
      // authenticated — resolved by auth.js, which fires this event.
      document.addEventListener('arp:auth-resolved', (e) => {
        if (e.detail.user) {
          renderRecommendations(container, { limit });
        } else {
          container.innerHTML = `
            <div class="empty-state">
              <div class="icon">✦</div>
              <h3>Sign in for personalized picks</h3>
              <p>Create a free account and we'll learn what you like as you browse.</p>
              <a href="/login" class="btn btn-accent">Sign in</a>
            </div>`;
        }
      }, { once: true });
    });
  });

  global.renderRecommendations = renderRecommendations;
})(window);
