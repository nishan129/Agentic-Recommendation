/**
 * events.js — the behavioral event tracking subsystem.
 *
 * This is deliberately the most carefully engineered file in the
 * frontend. Its one job is to capture meaningful user behavior
 * efficiently and reliably WITHOUT ever being visible to the user:
 * no blocking, no jank, no broken pages if the events API is down.
 *
 * Pipeline:
 *   trackEvent() -> dedup check -> in-memory queue
 *                 -> flush on (queue size >= MAX_BATCH_SIZE) OR (FLUSH_INTERVAL elapsed)
 *                 -> POST /api/v1/events/batch (fire-and-forget from the caller's POV)
 *                 -> on failure: exponential-backoff retry, capped attempts
 *                 -> if still failing / offline: persist to localStorage, retry on 'online'
 *                 -> on page unload: flush whatever's left via sendBeacon (best-effort)
 */
(function (global) {
  'use strict';

  // ---- Configuration (tune here) --------------------------------------
  const MAX_BATCH_SIZE = 10;          // flush once the queue reaches this size
  const FLUSH_INTERVAL_MS = 3000;     // ...or after this much time, whichever first
  const MAX_QUEUE_SIZE = 200;         // hard cap on in-memory queue; drop LOW priority first
  const DEDUP_WINDOW_MS = 400;        // identical event_type+product_id within this window is dropped
  const MAX_RETRIES = 4;              // 1s, 2s, 4s, 8s backoff, then give up on this batch
  const RETRY_BASE_MS = 1000;
  const OFFLINE_STORAGE_KEY = 'arp_event_offline_queue';
  const OFFLINE_STORAGE_MAX_EVENTS = 300; // cap what we're willing to keep in localStorage
  const SESSION_STORAGE_KEY = 'arp_session_id';
  const SCROLL_THRESHOLDS = [25, 50, 75, 100];

  const PRIORITY = { HIGH: 3, MEDIUM: 2, LOW: 1 };
  const EVENT_PRIORITY = {
    purchase: PRIORITY.HIGH,
    add_to_cart: PRIORITY.HIGH,
    wishlist_add: PRIORITY.HIGH,
    course_complete: PRIORITY.HIGH,
    recommendation_click: PRIORITY.MEDIUM,
    product_click: PRIORITY.MEDIUM,
    product_view: PRIORITY.MEDIUM,
    course_start: PRIORITY.MEDIUM,
    search: PRIORITY.MEDIUM,
    category_view: PRIORITY.MEDIUM,
    recommendation_view: PRIORITY.LOW,
    page_view: PRIORITY.LOW,
    time_spent: PRIORITY.LOW,
    scroll: PRIORITY.LOW,
  };

  function uuid() {
    if (global.crypto && global.crypto.randomUUID) return global.crypto.randomUUID();
    return 'xxxxxxxx-xxxx-4xxx-yxxx-xxxxxxxxxxxx'.replace(/[xy]/g, (c) => {
      const r = (Math.random() * 16) | 0;
      const v = c === 'x' ? r : (r & 0x3) | 0x8;
      return v.toString(16);
    });
  }

  function getSessionId() {
    try {
      let id = sessionStorage.getItem(SESSION_STORAGE_KEY);
      if (!id) {
        id = 'sess_' + uuid();
        sessionStorage.setItem(SESSION_STORAGE_KEY, id);
      }
      return id;
    } catch (e) {
      // sessionStorage unavailable (privacy mode, etc.) — fall back to an
      // in-memory id that lives for the page's lifetime only.
      if (!global.__arp_fallback_session_id__) {
        global.__arp_fallback_session_id__ = 'sess_' + uuid();
      }
      return global.__arp_fallback_session_id__;
    }
  }

  class EventTracker {
    constructor() {
      this.queue = [];
      this.recentSignatures = new Map(); // dedup: signature -> timestamp
      this.flushTimer = null;
      this.retryCount = 0;
      this.retryTimer = null;
      this.sessionId = getSessionId();
      this.timers = new Map(); // productId/page -> { start, accumulated }
      this.scrollFired = new Set();
      this._initialized = false;
    }

    init() {
      if (this._initialized) return;
      this._initialized = true;

      this._loadOfflineQueue();

      // Flush on a steady interval regardless of size.
      this.flushTimer = setInterval(() => this.flush(), FLUSH_INTERVAL_MS);

      // Flush promptly when connectivity returns.
      global.addEventListener('online', () => this.flush());

      // Page lifecycle: stop time-spent timers and make a best-effort
      // final flush. 'pagehide' fires more reliably than 'beforeunload'
      // across mobile browsers.
      global.addEventListener('pagehide', () => this._onLeave());
      document.addEventListener('visibilitychange', () => {
        if (document.visibilityState === 'hidden') {
          this._onLeave();
        } else if (document.visibilityState === 'visible') {
          // Resume the page-level timer if one was paused.
          this._resumeTimer('page:' + location.pathname);
        }
      });

      // Automatic page_view on every page that includes this script.
      this.track({ event_type: 'page_view', page: location.pathname });
      this.startTimeSpent('page:' + location.pathname);

      // Scroll-depth tracking, throttled + threshold-based (25/50/75/100%),
      // never one event per pixel.
      this._bindScrollTracking();
    }

    // -------------------------------------------------------------
    // Public tracking API
    // -------------------------------------------------------------

    /**
     * Queue an event. Safe to call from anywhere; never throws, never
     * blocks. `user_id` is intentionally not accepted here — the backend
     * derives it from the authenticated request.
     */
    track(evt) {
      if (!evt || !evt.event_type) return;

      const normalized = {
        event_id: uuid(),
        event_type: evt.event_type,
        product_id: evt.product_id || undefined,
        session_id: this.sessionId,
        page: evt.page || location.pathname,
        search_query: evt.search_query || undefined,
        metadata: evt.metadata || undefined,
        client_timestamp: new Date().toISOString(),
      };

      if (this._isDuplicate(normalized)) return;

      this.queue.push(normalized);
      this._enforceQueueLimit();

      if (this.queue.length >= MAX_BATCH_SIZE) this.flush();
    }

    /** Convenience wrapper matching the spec's example call shape. */
    trackEvent(evt) {
      this.track(evt);
    }

    startTimeSpent(key, productId) {
      if (this.timers.has(key)) return; // already running
      this.timers.set(key, { start: Date.now(), accumulated: 0, productId });
    }

    _resumeTimer(key) {
      const t = this.timers.get(key);
      if (t && t.start === null) t.start = Date.now();
    }

    _pauseAndFlushTimer(key, alsoRemove) {
      const t = this.timers.get(key);
      if (!t || t.start === null) return;
      t.accumulated += (Date.now() - t.start) / 1000;
      t.start = null;

      const duration = Math.round(t.accumulated);
      if (duration >= 2) {
        // Ignore accidental sub-2-second glances — not a meaningful signal.
        this.track({
          event_type: 'time_spent',
          product_id: t.productId,
          page: key.startsWith('page:') ? key.slice(5) : undefined,
          metadata: { duration_seconds: duration },
        });
      }
      if (alsoRemove) this.timers.delete(key);
      else t.accumulated = 0;
    }

    stopTimeSpent(key) {
      this._pauseAndFlushTimer(key, true);
    }

    _onLeave() {
      // Flush every active timer as a final time_spent event, then push
      // whatever's queued out the door via sendBeacon (best-effort; see
      // the note in api.js about auth headers and sendBeacon).
      for (const key of Array.from(this.timers.keys())) {
        this._pauseAndFlushTimer(key, false);
      }
      this.flush({ useBeacon: true });
    }

    // -------------------------------------------------------------
    // Scroll depth (threshold-based, not per-pixel)
    // -------------------------------------------------------------
    _bindScrollTracking() {
      let ticking = false;
      global.addEventListener('scroll', () => {
        if (ticking) return;
        ticking = true;
        requestAnimationFrame(() => {
          ticking = false;
          this._checkScrollDepth();
        });
      }, { passive: true });
    }

    _checkScrollDepth() {
      const doc = document.documentElement;
      const scrollable = doc.scrollHeight - doc.clientHeight;
      if (scrollable <= 0) return;
      const pct = Math.min(100, Math.round((global.scrollY / scrollable) * 100));

      for (const threshold of SCROLL_THRESHOLDS) {
        const key = location.pathname + ':' + threshold;
        if (pct >= threshold && !this.scrollFired.has(key)) {
          this.scrollFired.add(key);
          this.track({ event_type: 'scroll', metadata: { depth_percent: threshold } });
        }
      }
    }

    // -------------------------------------------------------------
    // Dedup
    // -------------------------------------------------------------
    _isDuplicate(evt) {
      const sig = `${evt.event_type}:${evt.product_id || ''}:${evt.search_query || ''}`;
      const now = Date.now();
      const last = this.recentSignatures.get(sig);
      this.recentSignatures.set(sig, now);

      // Housekeeping so this map never grows unbounded.
      if (this.recentSignatures.size > 500) {
        const cutoff = now - DEDUP_WINDOW_MS * 10;
        for (const [key, ts] of this.recentSignatures) {
          if (ts < cutoff) this.recentSignatures.delete(key);
        }
      }
      return last !== undefined && now - last < DEDUP_WINDOW_MS;
    }

    // -------------------------------------------------------------
    // Queue pressure management
    // -------------------------------------------------------------
    _enforceQueueLimit() {
      if (this.queue.length <= MAX_QUEUE_SIZE) return;
      // Drop the oldest LOW priority events first, then MEDIUM, to make
      // room — never silently drop HIGH-priority signals like purchases.
      for (const level of [PRIORITY.LOW, PRIORITY.MEDIUM]) {
        while (this.queue.length > MAX_QUEUE_SIZE) {
          const idx = this.queue.findIndex((e) => (EVENT_PRIORITY[e.event_type] || PRIORITY.MEDIUM) === level);
          if (idx === -1) break;
          this.queue.splice(idx, 1);
        }
        if (this.queue.length <= MAX_QUEUE_SIZE) break;
      }
      // If still over (all HIGH priority), trim the oldest regardless.
      while (this.queue.length > MAX_QUEUE_SIZE) this.queue.shift();
    }

    // -------------------------------------------------------------
    // Flushing / sending
    // -------------------------------------------------------------
    async flush({ useBeacon = false } = {}) {
      if (this.queue.length === 0) return;

      const batch = this.queue.splice(0, this.queue.length);
      await this._send(batch, { useBeacon });
    }

    async _send(batch, { useBeacon = false } = {}) {
      if (!global.Api) return; // api.js not loaded — fail silently
      if (!global.Api.TokenStore.isAuthenticated()) {
        // Anonymous visitors: nothing to send to an authenticated endpoint.
        // (A future version could add an anonymous ingestion path.)
        return;
      }

      // Offline: skip straight to local persistence, no wasted request.
      if (typeof navigator !== 'undefined' && navigator.onLine === false && !useBeacon) {
        this._persistOffline(batch);
        return;
      }

      try {
        await global.Api.sendEventsBatch(batch, { useBeacon });
        this.retryCount = 0;
        this._clearOfflineQueue(batch);
      } catch (err) {
        this._scheduleRetry(batch);
      }
    }

    _scheduleRetry(batch) {
      if (this.retryCount >= MAX_RETRIES) {
        // Give up on immediate retry; hand off to the durable offline
        // queue so we still get the data once the network genuinely
        // recovers (e.g. a page reload, or the 'online' event).
        this._persistOffline(batch);
        this.retryCount = 0;
        return;
      }
      const delay = RETRY_BASE_MS * Math.pow(2, this.retryCount);
      this.retryCount += 1;
      clearTimeout(this.retryTimer);
      this.retryTimer = setTimeout(() => this._send(batch), delay);
    }

    // -------------------------------------------------------------
    // Offline durability (localStorage)
    // -------------------------------------------------------------
    _persistOffline(batch) {
      try {
        const existing = JSON.parse(localStorage.getItem(OFFLINE_STORAGE_KEY) || '[]');
        let combined = existing.concat(batch);
        if (combined.length > OFFLINE_STORAGE_MAX_EVENTS) {
          // Discard the oldest LOW-priority events first to stay under
          // the storage cap rather than growing localStorage unbounded.
          combined.sort((a, b) => (EVENT_PRIORITY[b.event_type] || 2) - (EVENT_PRIORITY[a.event_type] || 2));
          combined = combined.slice(0, OFFLINE_STORAGE_MAX_EVENTS);
        }
        localStorage.setItem(OFFLINE_STORAGE_KEY, JSON.stringify(combined));
      } catch (e) {
        // Storage full or unavailable — nothing more we can safely do;
        // tracking degrades gracefully rather than throwing.
      }
    }

    _clearOfflineQueue(sentBatch) {
      try {
        const existing = JSON.parse(localStorage.getItem(OFFLINE_STORAGE_KEY) || '[]');
        if (existing.length === 0) return;
        const sentIds = new Set(sentBatch.map((e) => e.event_id));
        const remaining = existing.filter((e) => !sentIds.has(e.event_id));
        localStorage.setItem(OFFLINE_STORAGE_KEY, JSON.stringify(remaining));
      } catch (e) {
        /* ignore */
      }
    }

    _loadOfflineQueue() {
      try {
        const existing = JSON.parse(localStorage.getItem(OFFLINE_STORAGE_KEY) || '[]');
        if (existing.length > 0) {
          // Re-queue and let the normal flush cycle pick them up rather
          // than sending immediately on page load.
          this.queue.push(...existing);
          localStorage.removeItem(OFFLINE_STORAGE_KEY);
        }
      } catch (e) {
        /* ignore */
      }
    }
  }

  global.EventTracker = new EventTracker();
})(window);
