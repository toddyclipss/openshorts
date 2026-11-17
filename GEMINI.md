# OpenShorts — System Instructions & Guidelines (GEMINI.md)

This file provides system instructions, architectural constraints, and development guidelines for Google Antigravity agents working in the OpenShorts repository.

---

## 1. Project Overview

**OpenShorts** is an open-source, AI-powered vertical video pipeline that transforms long-form horizontal videos (YouTube URLs, direct streams, or local uploads) into engaging 9:16 vertical clips optimized for TikTok, Instagram Reels, and YouTube Shorts.

- **AI Engine:** Google Gemini 3.1 Flash-Lite (`gemini-3.1-flash-lite`, configurable via `GEMINI_MODEL`) identifies viral hooks, ranks candidate moments, and generates viral titles.
- **Editions:**
  - **Self-Hosted (BYOK):** Local or single-server deployment using user-provided API keys (`GEMINI_API_KEY`, etc.).
  - **Cloud Edition:** Multi-tenant SaaS with Stripe billing, usage metering, authentication, and worker delegation (`BILLING_ENABLED=true`, housed under `cloud/`).

---

## 2. Non-Negotiable Project Invariants

### 2.1 Mandatory English Only
- **All code, comments, docstrings, variable/function names, commit messages, PRs, and documentation MUST be written exclusively in English.**
- Portuguese, Spanish, or any other language is strictly forbidden in code artifacts.
- For full compliance specifications, see [language-policy.md](.agents/rules/language-policy.md).

### 2.2 Public Repository Security & Hygiene
- This repository is public. Never commit real API keys, credentials, IP addresses, internal server paths, customer PII, or internal business metrics.
- Keep `.env.example` scrubbed of real secrets.

### 2.3 Strict CI Quality Gate
- Before committing or requesting verification:
  - Python tests: `pytest tests/ -v` must pass.
  - Frontend tests & linter: `npm run lint` (`--max-warnings 0`) and `npm run build` inside `dashboard/` must pass cleanly.
- Code without passing tests or clean linting will be rejected.

---

## 3. Development Commands

```bash
# Backend (FastAPI on :8000)
python -m venv venv && source venv/bin/activate  # or .\\venv\\Scripts\\activate on Windows
pip install -r requirements.txt
uvicorn app:app --host 0.0.0.0 --port 8000 --reload

# Frontend Dashboard (Vite dev server on :5173 / proxies backend on :8000)
cd dashboard
npm install
npm run dev
npm run build     # Production static build
npm run lint      # ESLint strict validation

# Full Stack via Docker
docker compose up --build

# Test Suite
pytest tests/ -v
```

---

## 4. Pipeline Execution Model

Processing executes as an isolated child process per job (`main.py`) triggered by the FastAPI application (`app.py`):

1. **Ingest & Probe:** Video downloaded via `yt-dlp` (with cookie rotation, static proxy fallback, SSRF guard) or loaded from `uploads/`.
2. **Audio & Transcription:** Audio extracted to 16kHz mono WAV; Whisper (`faster-whisper`) extracts word-level timestamps.
3. **Scene Detection:** TransNetV2 / PySceneDetect identifies hard cuts and transitions.
4. **Moment Selection:** Gemini 3.1 Flash-Lite evaluates transcript windows and visual pacing to rank top moments (15–60s).
5. **Lossless Cut:** FFmpeg trims candidate segments using keyframe-accurate cuts.
6. **Layout & Reframing:** `layout_picker` selects optimal layout (Track, Split, Screen+Cam, Blurred Background) in a single-pass GPU pipeline (`gpu_render` / `osrender`) with CPU fallback.
7. **Subtitles & Overlays:** Word-level dynamic subtitles generated (SRT/ASS with alignment compensation) and hooks rendered.
8. **Dubbing & Translation:** Optional ElevenLabs voice dubbing and translated subtitles.
9. **Export & Storage:** Clean canonical clips delivered; free-tier watermarks (`wm_`) applied dynamically on delivery; optional S3/R2 backup and social posting.

---

## 5. Architectural Invariants & Subsystem Rules

### 5.1 Process & Worker Isolation
- **Child Process per Job:** Heavy ML/GPU processing executes in a dedicated subprocess (`main.py`), preventing memory leaks and event loop blocking in `app.py`.
- **VRAM & Model Management:** Always release models (`transcribe_backends.release_models()`, `torch.cuda.empty_cache()`) immediately after inference. Scale `MAX_CONCURRENT_JOBS` based on available GPU VRAM.
- **Deploy Drain Handover:** Graceful shutdown drains in-flight jobs without dropping tasks (`DRAIN_TIMEOUT_SECONDS`). Unfinished jobs persist their state to disk for resumption.

### 5.2 FFmpeg & Media Security
- **No Raw String Concatenation:** FFmpeg commands must be invoked with structured argument lists. Never construct filter strings from unvalidated user inputs.
- **Filter Whitelist:** Dynamic filter chains must strictly validate against `editor._ALLOWED_FILTERS`.
- **Clean Deliverables:** Canonical output files remain unwatermarked on disk. Free watermarks exist only on dynamically served `wm_` copies.

### 5.3 Network & SSRF Guarding
- **Strict SSRF Guard:** All outbound network scrapes and `yt-dlp` requests must route through `ssrf_guard.guarded()`. Validate destination IPs at connect time to prevent DNS rebinding attacks.
- **Download Proxy Hierarchy:** Direct connection → Static proxies (`STATIC_PROXY_URLS`) → Paid proxy (`PROXY_URL`). Never route non-YouTube traffic through the paid proxy.
- **YouTube Session Quota:** Cookie sessions rotate through `yt_account.Session` pools with cooling-off periods to prevent account blocking.

### 5.4 Cloud & Billing Invariants
- **GDPR Account Erasure:** Strict deletion order: Cancel Stripe subscription (abort on failure) → Purge R2/S3 assets → Single DB transaction deleting all records across `USER_OWNED_TABLES`.
- **Media Authorization:** All media URLs handed externally (API, MCP, webhooks) require HMAC signature tokens (`media_auth.sign_absolute_url`). Direct access to un-owned job directories is strictly forbidden.

### 5.5 UI & Design System (Lumen / Studio White)
- Follow the locked design system in [design.md](design.md).
- **Two-Register Rule:** UI prose renders **lowercase**; mono machine readouts (timecodes, ratios, costs) render **UPPERCASE**. Never lowercase user content (transcripts, titles).
- **Zero Gradients / Zero Glassmorphism:** Rely on crisp hairlines (`border-rule`), linen canvas (`--color-paper`), carbon ink (`--color-ink`), and burnished brass accent (`--color-accent`).

---

## 6. Modular Rules Index

Detailed guidelines are modularized in `.agents/rules/`:
- [subsystem-hard-rules.md](.agents/rules/subsystem-hard-rules.md) — Subsystem constraints, proxy routing, layout rendering invariants, MCP security, and billing (Claude parity).
- [language-policy.md](.agents/rules/language-policy.md) — Mandatory English Policy for all code, comments, commits, and docs.
- [coding-standards.md](.agents/rules/coding-standards.md) — Python 3.11+, strict typing, async patterns, FFmpeg safety, and resource management.
- [architecture.md](.agents/rules/architecture.md) — Service/worker boundaries, pipeline separation, clean interfaces, and deploy drain patterns.

@[Subsystem Hard Rules](.agents/rules/subsystem-hard-rules.md)
