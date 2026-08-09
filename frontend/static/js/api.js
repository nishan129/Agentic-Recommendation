/**
 * api.js — centralized API client.
 *
 * Every fetch() call in the app goes through here. Nothing else in the
 * codebase should call fetch() directly against the backend, so auth
 * headers, error shapes, and the base URL only need to be handled once.
 */
(function (global) {
  'use strict';

  // Same-origin by default. Override by setting window.__API_BASE_URL__
  // before this script loads (e.g. from base.html) if the backend is
  // deployed on a different host.
  const API_BASE_URL = global.__API_BASE_URL__ || '/api/v1';
  const TOKEN_KEY = 'arp_access_token';

  // ---- Token storage -------------------------------------------------
  const TokenStore = {
    get() {
      try { return localStorage.getItem(TOKEN_KEY); } catch (e) { return null; }
    },
    set(token) {
      try { localStorage.setItem(TOKEN_KEY, token); } catch (e) { /* ignore */ }
    },
    clear() {
      try { localStorage.removeItem(TOKEN_KEY); } catch (e) { /* ignore */ }
    },
    isAuthenticated() {
      return !!TokenStore.get();
    },
  };

  class ApiError extends Error {
    constructor(message, status, errorCode) {
      super(message);
      this.status = status;
      this.errorCode = errorCode;
    }
  }

  /**
   * Core request helper. Attaches the bearer token when present, parses
   * the backend's consistent error envelope, and throws ApiError on
   * failure so callers can branch on `.status` / `.errorCode`.
   */
  async function request(path, { method = 'GET', body, headers = {}, auth = true, signal } = {}) {
    const finalHeaders = { ...headers };
    if (body !== undefined) finalHeaders['Content-Type'] = 'application/json';

    if (auth) {
      const token = TokenStore.get();
      if (token) finalHeaders['Authorization'] = `Bearer ${token}`;
    }

    let response;
    try {
      response = await fetch(`${API_BASE_URL}${path}`, {
        method,
        headers: finalHeaders,
        body: body !== undefined ? JSON.stringify(body) : undefined,
        signal,
      });
    } catch (networkError) {
      throw new ApiError('Network error — please check your connection.', 0, 'NETWORK_ERROR');
    }

    if (response.status === 204) return null;

    let data = null;
    try {
      data = await response.json();
    } catch (e) {
      // No JSON body (e.g. some error responses) — fall through.
    }

    if (!response.ok) {
      const message = (data && data.message) || `Request failed (${response.status})`;
      const errorCode = (data && data.error_code) || 'UNKNOWN_ERROR';
      throw new ApiError(message, response.status, errorCode);
    }

    return data;
  }

  function qs(params) {
    const usp = new URLSearchParams();
    Object.entries(params || {}).forEach(([key, value]) => {
      if (value !== undefined && value !== null && value !== '') usp.set(key, value);
    });
    const s = usp.toString();
    return s ? `?${s}` : '';
  }

  // ---- Public API surface --------------------------------------------
  const Api = {
    ApiError,
    TokenStore,

    // Auth
    register(payload) {
      return request('/auth/register', { method: 'POST', body: payload, auth: false });
    },
    async login(payload) {
      const data = await request('/auth/login', { method: 'POST', body: payload, auth: false });
      if (data && data.access_token) TokenStore.set(data.access_token);
      return data;
    },
    logout() {
      TokenStore.clear();
    },
    getCurrentUser() {
      return request('/auth/me');
    },
    updateProfile(payload) {
      return request('/auth/me', { method: 'PATCH', body: payload });
    },

    // Products (public)
    getProducts(params) {
      return request(`/products${qs(params)}`, { auth: false });
    },
    getProduct(id) {
      return request(`/products/${encodeURIComponent(id)}`, { auth: false });
    },

    // Admin — products
    adminListProducts(params) {
      return request(`/admin/products${qs(params)}`);
    },
    adminGetProduct(id) {
      return request(`/admin/products/${encodeURIComponent(id)}`);
    },
    adminCreateProduct(payload) {
      return request('/admin/products', { method: 'POST', body: payload });
    },
    adminUpdateProduct(id, payload) {
      return request(`/admin/products/${encodeURIComponent(id)}`, { method: 'PATCH', body: payload });
    },
    adminDeleteProduct(id) {
      return request(`/admin/products/${encodeURIComponent(id)}`, { method: 'DELETE' });
    },
    adminDashboard() {
      return request('/admin/dashboard');
    },
    adminEventStats() {
      return request('/admin/stats/events');
    },
    adminRecommendationStats() {
      return request('/admin/stats/recommendations');
    },

    // Events
    sendEventsBatch(events, { useBeacon = false } = {}) {
      const url = `${API_BASE_URL}/events/batch`;
      const token = TokenStore.get();
      const payload = JSON.stringify({ events });

      if (useBeacon && navigator.sendBeacon && token) {
        // sendBeacon can't set custom headers, so we can't attach the
        // bearer token to it — it's only used as a last-resort delivery
        // attempt on page unload when a normal fetch might get cancelled.
        // The backend call will fail auth in that case; that's an
        // accepted tradeoff documented in events.js.
        const blob = new Blob([payload], { type: 'application/json' });
        return Promise.resolve(navigator.sendBeacon(url, blob));
      }

      return request('/events/batch', { method: 'POST', body: { events } });
    },

    // Recommendations
    getRecommendations(limit) {
      return request(`/recommendations${qs({ limit })}`);
    },
    getRecommendationHistory(limit) {
      return request(`/recommendations/history${qs({ limit })}`);
    },
  };

  global.Api = Api;
})(window);
