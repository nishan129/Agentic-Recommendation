# SmartReco — AI Recommendation Platform Frontend

A server-rendered (Jinja2 + FastAPI) frontend for the Agentic
Recommendation backend — no React, no build step, no SPA framework. Just
HTML, modern CSS, and modular vanilla JavaScript talking to the backend
API over `fetch`.

## 1. What this is

This service renders page *shells* with Jinja2. All data — products,
recommendations, auth, admin stats — is fetched **client-side** by the JS
modules in `static/js/`, calling the backend's `/api/v1` endpoints
directly. That split keeps this frontend a thin, fast, mostly-static
server that can be deployed and scaled independently of the backend.

Design direction: bold Gen-Z dark UI — a confident, AI-native feel rather
than a generic SaaS dashboard. Near-black background with glowing
violet-to-pink gradient accents, glassy blurred surfaces, Space Grotesk
display type + Plus Jakarta Sans body, animated gradient blobs, and
scroll-triggered reveal animations on every card grid.

## 2. Architecture

```
Browser
   ├── Jinja2-rendered HTML (page shell, navbar, footer)
   └── JavaScript (progressive enhancement)
         ├── api.js            — every fetch() call goes through here
         ├── events.js         — behavioral event tracking subsystem
         ├── auth.js           — login/register/logout, navbar auth state
         ├── app.js            — flash messages, mobile nav, shared card renderers
         ├── products.js       — listing page: search/filter/sort/pagination
         ├── recommendations.js— recommendation cards + view tracking
         └── admin.js          — dashboard stats, product CRUD table/forms
                     │
                     ▼
            Backend FastAPI API (/api/v1/...)
                     │
                     ▼
       PostgreSQL · RecommendationService · (future: LangGraph agent)
```

If JavaScript fails to load entirely, the page shell (nav, footer, basic
structure) still renders — only the dynamic data-driven regions
(product grids, recommendations, forms) stay in their skeleton/loading
state. Tracking and recommendations are additive layers, not
load-bearing for basic navigation.

## 2.5. Visual design system

`static/css/main.css` defines the token layer — everything else
(`components.css`, `responsive.css`) builds on these CSS variables, so
re-theming means editing tokens in one place:

| Token group | Values |
|---|---|
| Background | `--bg` (near-black), `--surface` / `--surface-hover` (card layers) |
| Accent gradient | `--gradient-primary` (violet → pink), `--gradient-cool` (cyan → violet) |
| Type | `--font-display` (Space Grotesk — headings, prices, stat numbers), `--font-body` (Plus Jakarta Sans) |
| Motion | `--ease` (shared cubic-bezier for all transitions) |

**Animation & interaction details:**
- Hero background uses two blurred, slowly-drifting gradient "blobs"
  (`.hero-blob`, pure CSS `@keyframes`) — no JS, no performance cost.
- `.gradient-text` animates a shifting gradient across headline text.
- Product/recommendation cards lift, glow, and reveal a gradient border
  on hover; card images scale slightly on hover (`transform`, GPU-cheap).
- **Scroll-reveal**: `app.js`'s `bindScrollReveal()` + `revealGrid()` fade
  and slide in any freshly-rendered card grid the first time it enters
  the viewport, with a small per-card stagger — implemented with a single
  shared `IntersectionObserver`, and skipped entirely when the OS-level
  `prefers-reduced-motion` setting is on.
- Admin dashboard uses a **bento-grid** layout (`.bento-grid` /
  `.bento-card`) instead of a plain stat row, each card with its own
  icon tile and hover lift.
- Buttons are pill-shaped with a gradient fill and a subtle press-scale
  (`:active { transform: scale(0.96) }`) for tactile feedback.



```
frontend/
├── app.py                      # FastAPI page routes (renders Jinja2 shells)
├── requirements.txt
├── templates/
│   ├── base.html                # layout: navbar, flash stack, footer, script loading
│   ├── components/
│   │   ├── navbar.html, footer.html, flash_message.html
│   │   ├── product_card.html, recommendation_card.html   # SSR-fallback partials
│   │   ├── search_bar.html, pagination.html
│   ├── home.html, login.html, register.html
│   ├── products.html, product_detail.html
│   ├── recommendations.html, profile.html
│   └── admin/
│       ├── _sidebar.html, _product_form.html
│       ├── dashboard.html, products.html
│       └── product_create.html, product_edit.html
└── static/
    ├── css/  main.css (design tokens/typography), components.css, responsive.css
    ├── js/   api.js, events.js, auth.js, app.js, products.js, recommendations.js, admin.js
    └── images/
```

## 4. Running locally

```bash
python -m venv .venv
source .venv/bin/activate          # Windows: .venv\Scripts\activate
pip install -r requirements.txt

# Point this at your running backend (see backend/README.md):
export API_BASE_URL=http://localhost:8000/api/v1   # Windows (Git Bash): same syntax

uvicorn app:app --reload --port 3000
```

Visit `http://localhost:3000`. Make sure the backend is running first
(`docker compose up` in `backend/`, or `uvicorn app.main:app --port 8000`)
— the frontend has nothing to show without it.

### CORS

The backend's `CORS_ORIGINS` env var must include this frontend's origin
(e.g. `http://localhost:3000`) or browser requests from these pages to
the API will be blocked. See `backend/.env.example`.

## 5. Pages

| Route | Renders |
|---|---|
| `/` | Home — hero, categories, recommendations, popular products |
| `/login`, `/register` | Auth forms |
| `/products` | Listing — search, category/price filters, sort, pagination |
| `/products/{id}` | Product detail — description, related, recommendations |
| `/search` | Same listing UI; reads `?search=` client-side |
| `/recommendations` | Full personalized recommendation grid |
| `/profile` | Account info, derived interests, recommendation summary |
| `/admin` | Dashboard — totals, event breakdown |
| `/admin/products` | Product management table (search, edit, delete) |
| `/admin/products/create`, `/admin/products/{id}/edit` | Product forms |

Admin pages render for anyone who navigates to them — **authorization is
enforced entirely by the backend API**, not by this frontend. A
non-admin visiting `/admin` will see failed API calls and empty state,
never real data. Never treat a frontend route guard as a security
boundary; see Section 9.

## 6. The event tracking system (`static/js/events.js`)

This is the most carefully engineered part of the frontend, by design.

```
trackEvent()
   → dedup check (identical event_type+product_id within 400ms dropped)
   → in-memory queue
   → flush when queue reaches 10 events, OR every 3 seconds — whichever first
   → POST /api/v1/events/batch  (never blocks the calling code)
        ├─ success → queue cleared
        └─ failure → exponential backoff retry (1s, 2s, 4s, 8s), capped at 4 attempts
                       → still failing / offline → persisted to localStorage
                                                     → retried on 'online' event
                                                     → capped at 300 events, drops
                                                       LOW-priority events first
on page unload (pagehide / visibilitychange=hidden):
   → flush all active time-spent timers as final time_spent events
   → best-effort flush via navigator.sendBeacon
```

**Configurable constants** (top of `events.js`): `MAX_BATCH_SIZE` (10),
`FLUSH_INTERVAL_MS` (3000), `MAX_QUEUE_SIZE` (200), `DEDUP_WINDOW_MS`
(400), `MAX_RETRIES` (4), `OFFLINE_STORAGE_MAX_EVENTS` (300).

**Priority levels** — `HIGH` (`purchase`, `add_to_cart`, `wishlist_add`,
`course_complete`), `MEDIUM` (`product_view`, `product_click`, `search`,
...), `LOW` (`page_view`, `time_spent`, `scroll`). When the in-memory
queue or the offline localStorage queue hits its cap, `LOW` events are
dropped first, then `MEDIUM` — `HIGH`-priority signals are never
silently discarded.

**Time spent**: started on page load and on each product detail page via
`EventTracker.startTimeSpent(key, productId)`; paused/flushed on
`visibilitychange` and `pagehide`, not on a timer — so a `time_spent`
event only fires once, with the real accumulated duration, when the user
actually leaves. Sub-2-second glances are discarded as noise.

**Scroll tracking**: throttled via `requestAnimationFrame` and reported
only at 25/50/75/100% depth thresholds, once each per page — never one
event per pixel.

**Session ID**: a `sess_<uuid>` generated once per browser tab and
stored in `sessionStorage`, attached to every event.

**What it never does**: block the UI, retry indefinitely, grow
localStorage unbounded, or let a failed event request surface as a user
facing error. Tracking failures are always silent from the user's
perspective — see Section 9.

`user_id` is never sent by the client — the backend derives it from the
authenticated request (see `backend/app/services/event_service.py`).

## 7. Search & pagination

`products.js` debounces the search input at 400ms — a keystroke never
triggers an immediate API call. Filters (category, price) use their own
short debounce/immediate-on-change as appropriate. Pagination re-fetches
the current filtered/sorted view for the requested page and updates the
URL (`?search=`, `?category=`, implicit `page`) via `history.replaceState`
so results are shareable/bookmarkable without a full page reload.

## 8. Recommendation UX

Recommendation cards always show a plain-language `reason` string from
the backend (e.g. *"Based on your recent interest in programming"*) —
never internal scores or model details beyond a friendly "% match" chip.
Views are tracked once per card using an `IntersectionObserver` (a card
scrolled past off-screen is never counted), and clicks are tracked via a
single delegated listener in `app.js` shared with regular product cards.

## 9. Error handling & resilience

- API failures never render a raw error page. Product/recommendation
  sections show a friendly inline message ("temporarily unavailable")
  and the rest of the page keeps working.
- Event tracking failures are invisible to the user by design — see
  Section 6.
- Empty states are written to guide the next action, not just say "no
  data" (e.g. "No recommendations yet — explore a few products…").
- Every async section renders a skeleton loader while its first request
  is in flight, never a spinner-only blank screen.

## 10. Accessibility

Semantic HTML landmarks (`header`, `main`, `footer`, `nav`), a skip-to-
content link, labeled form fields with visible error text, keyboard-
reachable interactive elements, `aria-busy`/`aria-live` on
dynamically-loading regions, and color choices that don't rely on hue
alone (status badges pair color with text, not just a dot).

## 11. Performance

- Images use `loading="lazy"`.
- No frontend framework/bundle — each page loads only the JS modules it
  needs (e.g. `admin.js` and `products.js` are only referenced on their
  respective pages via `{% block extra_scripts %}`).
- Search and filters are debounced; recommendations are fetched once per
  page load, not re-fetched on every interaction.
- A single delegated click listener handles product-card tracking
  site-wide instead of one listener per card.

## 12. Security notes

- The frontend never treats itself as an authorization boundary — see
  Section 5. All access control is enforced server-side by the backend.
- The JWT access token lives in `localStorage` (see `api.js`'s
  `TokenStore`) and is attached as a `Bearer` header on every
  authenticated request; it is never logged, never put in a URL, and
  never embedded in page HTML.
- No secrets (`DATABASE_URL`, `SECRET_KEY`, etc.) exist anywhere in this
  frontend or its JS — only `API_BASE_URL`, a public value.

## 13. Connecting to the backend

Set `API_BASE_URL` (server env var, read by `app.py`) to wherever the
backend is reachable from the *browser* (not from this server — the
frontend process itself makes no API calls; only client-side JS does).
In Docker Compose, that typically means the backend's published host
port (e.g. `http://localhost:8000/api/v1`), not its internal service
name, since the browser — not this container — makes the request.

## 14. Future: agentic integration

No frontend changes are required when the backend's
`RecommendationService` is swapped for a LangGraph agent — `recommendations.js`
already renders whatever `reason`/`score` the API returns. If the agent
surfaces richer explanations or multi-step reasoning traces, extend the
`recommendationCardHtml()` template in `recommendations.js` without
touching the tracking pipeline or the rest of the app.
