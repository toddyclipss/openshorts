# OpenShorts Subsystem Hard Rules & Operational Invariants

This document establishes the non-negotiable subsystem constraints and operational invariants for OpenShorts (imported directly from `CLAUDE.md` to guarantee full parity across AI agents).

---

## 1. Subsystem Reference Index

Before modifying any subsystem, consult its dedicated architecture reference:
- SEO pages, free tools, attribution → `docs/architecture/seo-and-tools.md`
- Layout picker, reframing modes, hook grounding → `docs/architecture/layouts-and-reframing.md`
- Clip count, silent-footage fallback, local LLM → `docs/architecture/clip-selection.md`
- Thumbnail Studio → `docs/architecture/thumbnails.md`
- API endpoints, API keys, MCP, OAuth, webhooks → `docs/architecture/agent-access.md`
- Autopilot → `docs/architecture/autopilot.md`
- Free-plan watermark (served `wm_` copy, unmark on upgrade) → `docs/architecture/watermark.md`
- Quota wall, free overflow, lifecycle emails, cancel flow, survey, GDPR erasure → `docs/architecture/billing-and-account.md`
- Concurrency/VRAM, auto-retry, deploy handover and drain → `docs/architecture/jobs-and-deploys.md`
- Download routing, yt-dlp clients, paid proxy ledger → `docs/architecture/proxy-routing.md`
- Remote CPU worker (second host renders free jobs) → `docs/architecture/remote-worker.md`

---

## 2. SEO & Public Web Invariants

- **Landing Fallback Sync:** Keep `dashboard/seo/landing-fallback.js` in strict sync with `dashboard/src/Landing.jsx`. Never commit a static `public/sitemap.xml`; `vite-plugin-seo.js` dynamically generates it at build time.
- **Flat HTML Output:** Standalone marketing pages must be emitted as flat `.html` files (nested directories trigger Nginx 301 redirects and break canonical URLs).
- **Pricing Parity:** Whenever updating pricing anywhere in the codebase or marketing text, update `dashboard/seo/data.js` as well. Never state "OpenShorts is free" without displaying the Cloud edition price alongside it.
- **Silent Footage Landing Pages:** `/gta-5-clips`, `/gta-6-clips`, and `/platforms/twitch` document silent-footage thresholds and stretch dimensions. Update their text whenever those processing thresholds change.
- **Free Tools Proxy Restriction:** The `youtube-transcript` tool must use `STATIC_PROXY_URLS` or a direct route, **never** `PROXY_URL`. A static route returning zero formats and zero captions indicates degraded state, not "no captions".

---

## 3. Layouts, Reframing & Clip Selection

- **Layout Picker Resolution:** `layout_picker` sends 12 stills at 1024px to Gemini and requests a closed enum choice (`none`/`screencast`/`split`). Never send full video files or pixel measurements to the picker.
- **User Preference Immutability:** `layout_picker.apply()` only adds missing layout options. An explicit user selection must never be turned off or overridden by the AI model.
- **Vertical Source Fast-Path:** A video source that is already 9:16 vertical skips both the picker and classifier, defaulting immediately to `TRACK`.
- **Split Layout Alignment:** Split dual-speaker captions require ASS format with `{\an5}` alignment anchors positioned directly along the seam. SRT format cannot provide per-stretch coordinate alignment. Preserve `layout_ranges` across recuts (`layout_ranges.remap`).
- **Speaker Activity Normalization:** Mouth movement activity is normalized per speaker before comparison (`normalise_activity`).
- **GPU Reframe Compilation:** Reframe rendering executes in a single GPU pass (`gpu_render` + `osrender/`) constructed from scene filtergraphs. Keep layouts constrained to `crop/scale/gblur/overlay/vstack/pad`. When modifying `osrender/src/kernels.cu`, always regenerate `kernels.ptx` (see `osrender/README.md`).
- **Watermark Twin Invariant:** Canonical master files remain clean on disk. Free watermarks exist only on dynamically served `wm_` copies. While a job carries `.marked`, `/videos` refuses to serve clean deliverables.
- **Global Moment Ranking:** The scoring pass ranks every candidate window globally across the entire video (top N moments), never "choose up to K per batch". The `min_clips` floor is strictly enforced in code.
- **Vision Segments:** `get_visual_clips` is the only stage that passes video to Gemini. Beyond `VISION_SEGMENT_SECONDS`, it inspects near-equal segments (`vision_segments`), never a single monolithic upload.

---

## 4. Download Routing, Proxies & YouTube Cookies

- **Proxy Routing Hierarchy:** Outbound requests strictly follow: Direct connection → Static ISP proxies (`STATIC_PROXY_URLS`) → Paid per-GB proxy (`PROXY_URL`). Non-YouTube URLs must never route through the paid proxy.
- **YouTube Session Cookies:** Probe and download requests both carry `YOUTUBE_COOKIES` (attempt 1 with cookies, attempt 2 anonymous).
- **yt-dlp Client List:** Maintain the explicit `yt_clients.py` client configuration. Never reintroduce `player_skip: webpage`. Enforce `noplaylist` globally; validate non-video URLs against the whitelist.
- **Cookie Account Rotation & Cooldowns:** Every extraction sending `YOUTUBE_COOKIES` acquires a session from `yt_account.Session` and runs inside `request()`. No requests execute while `yt_account.cooling_down()`. Account limit errors are retried after the cooldown (`YT_ACCOUNT_LIMITED`), never treated as broken videos.
- **Proxy Ceilings:** Enable `DOWNLOAD_SKIP_STATICS` only when the probe confirms every static proxy was bot-checked. `PAID_PROXY_DAILY_MB` is a hard daily ceiling. Never store `PROXY_URL` in a local `.env`.

---

## 5. Agent Access, MCP & Security Boundaries

- **MCP Stdio Initialization:** In `mcp_stdio.py`, redirect `sys.stdout` to `stderr` **before importing `app`**, and properly enter the FastAPI application lifespan.
- **Webhook Target Validation:** Webhook URLs must pass `security_utils.assert_public_url` both at job submission and at actual delivery time.
- **API Key Scopes:** API keys (`osk_`) cannot manage API keys, consent to OAuth, modify billing, or trigger account deletion (`get_session_user_required`). OAuth tokens carry scopes (`cloud/scopes.py`). New MCP tool endpoints must join `_MCP_ROUTES`.
- **Media Authorization Tokens:** Cloud endpoints `/videos` and `/thumbnails` require HMAC signatures, user media tokens, or verified ownership credentials (`app._authorize_media`). Direct file downloads without authorization are blocked.
- **OAuth Callback Security:** The Google OAuth callback redirects with a single-use code bound to the dashboard's `cc` challenge, never the raw session JWT (`/api/auth/exchange`).
- **SSRF Connect-Time Validation:** All yt-dlp fetches and server-side web scrapes run inside `ssrf_guard.guarded()`. Destination IP addresses and DNS redirects are validated at connect time to prevent DNS rebinding.

---

## 6. Billing, Lifecycle & GDPR Account Erasure

- **Atomic GDPR Deletion Order:** Deleting a user account must strictly execute:
  1. Cancel Stripe subscription (abort immediately if cancellation fails).
  2. Purge user assets from S3/R2 storage.
  3. Execute a single atomic database transaction deleting all records across `USER_OWNED_TABLES`.
- **Secret Hygiene:** Coupon IDs and promotion codes live only in environment variables or Stripe dashboards, never committed to this repository.
- **Alert Sanitization:** Churn and cancellation alerts transmit reason enums and numeric ratings, never unconstrained user free text.
- **Balance Invariant:** `reserve_process_minutes` never reserves more than the user's available balance.
- **Commercial Email Compliance:** Marketing and lifecycle communications must route through `emails.send_commercial_email` with mandatory opt-out and List-Unsubscribe headers.

---

## 7. Public Repository Hygiene & CI Quality Gates

- **Public Repo Policy:** No internal hosts, private IPs, production paths, server metrics, or customer PII in code, comments, or documentation.
- **Pre-Push Validation:** Always verify locally before pushing:
  ```bash
  pytest tests/ -v
  cd dashboard && npm run lint && npm run build
  ```
- **Green Pipeline Rule:** A task is only complete when CI finishes green. Never leave a broken pipeline on `main`.
