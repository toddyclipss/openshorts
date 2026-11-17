# Architecture & Design Patterns for OpenShorts

## 1. System Topography & Component Layout

OpenShorts is structured around modular, loosely coupled components separating request routing from heavy media computing:

```
┌────────────────────────────────────────────────────────┐
│                   Client Layer                         │
│  React Dashboard (Vite) │ CLI / MCP │ Webhooks / API   │
└───────────────────────────┬────────────────────────────┘
                            │ HTTP / JSON
┌───────────────────────────▼────────────────────────────┐
│              API Gateway & Coordinator (app.py)        │
│  - FastAPI Routes & Lifespan                           │
│  - Auth & Metering (cloud/)                            │
│  - Concurrency Limiter & Job Scheduling                │
│  - Deploy Drain & Handover                             │
└──────────────┬──────────────────────────┬──────────────┘
               │ Fork Subprocess          │ HTTP Task Delegation
┌──────────────▼─────────────┐ ┌──────────▼──────────────┐
│  Core Worker (main.py)     │ │  Remote Worker          │
│  - Transcribe (Whisper)    │ │  (remote_worker.py)     │
│  - Scene Detect (TransNet) │ │  - CPU-only Rendering   │
│  - Scoring (Gemini 3.1)    │ │  - Free Tier Overflow   │
│  - Reframe & Render        │ └─────────────────────────┘
└──────────────┬─────────────┘
               │ Output Artifacts
┌──────────────▼─────────────────────────────────────────┐
│        Storage & Delivery (output/<job_id>/)           │
│  - Disk Storage (Job Manifests & Clean Clips)          │
│  - Dynamic Watermarker (wm_*)                          │
│  - Cloud Storage (S3 / Cloudflare R2)                  │
└────────────────────────────────────────────────────────┘
```

---

## 2. Modular Service & Worker Separation

### 2.1 Process Isolation & Secret Scrubbing
- Heavy video processing, machine learning inference (PyTorch, Whisper, YOLO, MediaPipe), and FFmpeg rendering must **never** run inside the ASGI web server threads.
- Each processing job runs as an isolated OS process via `main.py`. This ensures:
  - GPU memory is cleanly reclaimed by the OS when the process exits.
  - Native library crashes (CUDA driver issues, OpenCV segfaults) cannot crash the web server.
  - Unbounded CPU operations do not starve the FastAPI event loop.
- **Environment Scrubbing:** Subprocesses spawned by `app.py` must filter out cloud/billing secrets via `CHILD_ENV_DENYLIST` (stripping Stripe keys, DB passwords, JWT secrets) so child workers operate with least privilege.
- **Hardware Locks:** Host-wide file locks (`.asr-gpu-N.lock`, `.nvenc-N.lock`) arbitrate ASR inference and hardware encoder access across concurrent jobs.

### 2.2 Remote CPU Worker Delegation
- Free-tier overflow jobs can be rendered on secondary hosts via pull-based remote workers (`remote_worker.py` / `worker.py`).
- Remote jobs hold zero local GPU slots (`_local_running`).
- The worker receives only job options and sanitized source files (never credentials) and writes strictly non-dot output files into the job directory (`.remote.*`). All files read back must be treated as untrusted external data.

### 2.2 Disk-Backed Job State & Resumption
- Job state is persisted on disk inside `output/<job_id>/` using atomic JSON files (`write_json_atomic`):
  - `job.json`: Status, options, source metadata.
  - `transcript.json`: Word-level timestamps.
  - `scenes.json`: Detected cut boundaries.
  - `clips.json`: Selected moments, rankings, and layouts.
- In-memory state in `app.py` is minimal and reconstructible from disk, allowing safe service restarts without data loss.

### 2.3 Deploy Drain & Handover
- The application implements graceful shutdown routines triggered by SIGTERM / SIGINT (`DRAIN_TIMEOUT_SECONDS`).
- When a drain begins:
  1. The API gateway stops accepting new video jobs and returns a draining status.
  2. Active jobs are allowed a grace period to complete their current processing stage or write a resume checkpoint.
  3. The platform health check endpoint reflects drain state for zero-downtime rolling deploys.

---

## 3. Pipeline Separation & Execution Stages

The OpenShorts core pipeline executes strictly separated, sequential stages:

```
[Ingest & Download] ──► [Audio & ASR] ──► [Scene Detection] ──► [Gemini Scoring]
                                                                        │
[Delivery / Storage] ◄── [Dubbing & Subtitles] ◄── [Reframe / Render] ◄─┘
```

1. **Ingest & Probe:**
   - Handles YouTube URLs or uploaded files.
   - All network calls pass through `ssrf_guard.guarded()` to prevent SSRF and DNS rebinding attacks.
   - YouTube requests rotate through cookie accounts (`yt_account.Session`) and enforce proxy failover (Direct → Static → Paid Proxy).
2. **Audio Extraction & Whisper ASR:**
   - Extracts 16kHz mono audio. Runs `faster-whisper` to generate word-level timestamped transcripts.
   - Explicitly calls `transcribe_backends.release_models()` immediately after completion.
3. **Scene Detection:**
   - Splits video into distinct shots using TransNetV2 (or PySceneDetect content detection) to guide reframing and avoid cutting across active scenes.
4. **Viral Moment Selection:**
   - Transcript chunks are ranked by Gemini 3.1 Flash-Lite (`gemini-3.1-flash-lite`).
   - Shortlists top 3–15 segments (15–60s) based on hook potency, emotional peaks, and narrative completeness.
   - Visual segment fallback handles silent/gameplay footage.
5. **Layout Classification & Reframing:**
   - `layout_picker` evaluates frame samples and assigns optimal layouts (Tracked Single Speaker, Split Dual Speaker, Screencast with Face Inset, or Blurred Background).
   - Compiled into a single-pass GPU filtergraph (`gpu_render` / `osrender`) with automated CPU FFmpeg fallback.
6. **Subtitles, Hooks & Audio Dubbing:**
   - Generates synchronized subtitles (ASS for coordinate positioning, SRT for standard players).
   - Applies viral hook text overlays.
   - Optional ElevenLabs neural voice dubbing and language translation (`translate.py`).
7. **Delivery & Watermarking:**
   - Clean, unwatermarked master clips are stored.
   - Free-tier clips are dynamically delivered with a watermark (`wm_`) by `watermarked.py`.
   - Artifacts optionally sync to S3/R2 or post directly to social platforms via Upload-Post.

---

## 4. Clean Interfaces & Security Boundaries

### 4.1 Cloud vs Self-Host Decoupling
- Core video generation logic (`main.py`, `layout_picker.py`, `reframe_v2.py`, `subtitles.py`) must remain completely decoupled from billing and multi-tenant SaaS logic.
- SaaS concerns (Stripe billing, user accounts, API key validation, email lifecycle) reside exclusively within `cloud/` and activate conditionally when `BILLING_ENABLED=true`.

### 4.2 Media Authorization & URL Signing
- Media artifacts (`/videos/{job_id}/{clip_id}`, `/thumbnails/{job_id}/{clip_id}`) are protected by HMAC signatures (`media_auth.sign_absolute_url`).
- Unauthenticated access to job directories or arbitrary path traversals is prevented by verifying directory ownership (`.owner` marker).

### 4.3 GDPR Erasure Contract
- User account deletion must follow a strict, non-negotiable sequence:
  1. Cancel Stripe subscription (abort entire process on failure).
  2. Purge user assets from S3/R2 object storage.
  3. Execute a single atomic database transaction deleting all records across `USER_OWNED_TABLES`.
