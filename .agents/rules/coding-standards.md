# Coding Practices & Conventions for OpenShorts

## 1. Python 3.11+ Standards & Idioms

OpenShorts requires Python 3.11+. Code should leverage modern Python capabilities:
- **Generic Collections:** Use built-in generic syntax for collections (`list[str]`, `dict[str, Any]`, `tuple[int, ...]`, `set[Path]`) rather than legacy `typing.List` / `typing.Dict`.
- **Typing Constructs:** Use `typing.Optional`, `typing.Literal`, `typing.Union` (or `X | Y`), `typing.TypedDict`, and `typing.Protocol` for interface definitions.
- **Pattern Matching:** Use `match / case` for multi-branch enum or structure discrimination (e.g., layout mode routing).
- **Data Models:** Use Pydantic v2 `BaseModel` for API schemas and request/response payloads; use `@dataclass(slots=True)` for internal data transfer objects.

---

## 2. Strict Type Annotations

- **Full Signatures:** Every function, method, and endpoint parameter must carry explicit type annotations. Explicit return types (`-> None`, `-> list[dict[str, Any]]`) are mandatory.
- **No Implicit Any:** Avoid untyped parameters or variables that degenerate to `Any`. Where dynamic typing is required, document the contract explicitly or use `TypedDict`.
- **Constants & Attributes:** Class variables and module-level constants must be type-annotated (e.g., `MAX_FILE_SIZE_MB: int = 2048`).

---

## 3. Asynchronous & Concurrency Patterns

- **FastAPI Endpoints:** Use `async def` for I/O-bound endpoints (database interactions, S3 transfers, HTTP requests with `httpx.AsyncClient`).
- **Do Not Block the Event Loop:** Heavy computation (OpenCV frame manipulation, PyTorch inference, TransNetV2, Whisper, MediaPipe, FFmpeg subprocesses) MUST NOT execute directly on the FastAPI async event loop.
  - Offload heavy tasks to separate worker processes (via `subprocess.Popen`) or thread pools (`asyncio.to_thread` / `concurrent.futures.ThreadPoolExecutor`).
- **Cancellation & Timeouts:** Implement timeout barriers (`asyncio.timeout` or `asyncio.wait_for`) for external calls. Handle `asyncio.CancelledError` cleanly during server shutdown and deploy handover.
- **Background Tasks:** Non-critical post-processing (telemetry, notification emails) must use FastAPI's `BackgroundTasks` or dedicated worker queues.

---

## 4. Error Handling, Resilience & Persistence

- **Domain Exceptions:** Raise explicit domain exceptions (e.g., `VideoDownloadError`, `TranscriptionError`, `QuotaExceededError`) rather than generic `Exception` or `RuntimeError`.
- **No Silent Failures:** Never write bare `except:` blocks or swallow exceptions silently. Always log exceptions with contextual metadata (`job_id`, `video_id`, parameters) before re-raising or returning structured error responses.
- **Atomic File Persistence:** Never write directly to target configuration or state files that can be read concurrently.
  - Always use atomic write patterns (`jsonfile.write_json_atomic` or write-to-temp-then-rename `os.replace`), preventing corrupted JSON state if a process terminates abruptly.
- **Defensive Parsing:** When parsing sidecars, recipes, metadata, or job transcripts from disk, validate types before passing to system commands.

---

## 5. FFmpeg Pipelines & Filtergraph Safety

- **Structured Command Lists:** Always invoke FFmpeg using argument lists (e.g., `subprocess.run(["ffmpeg", "-y", "-ss", ...])`). Never use `shell=True` or concatenate untrusted strings into command arguments.
- **Filtergraph Whitelisting:** Any dynamic video/audio filter chains must validate against allowed filter names (`editor._ALLOWED_FILTERS`). Arbitrary filter expressions from user input or job manifests are strictly prohibited.
- **Sanitized Media Paths:** Video paths, font filenames, and subtitle file paths must be sanitized against path traversal and shell escapades before injection into filter graphs.
- **Single GPU Pass Rendering:**
  - Layout rendering should execute in a single GPU pass using the unified filtergraph generator (`gpu_render` + `osrender`) where supported.
  - If a filtergraph cannot be accelerated on GPU, fall back cleanly to CPU FFmpeg.
- **Subtitle Styling & Alignment:**
  - For split layouts or multi-speaker views, generate ASS subtitles with explicit coordinate alignments (`{\an5}` anchor) rather than basic SRT, ensuring text does not collide with seams or facial insets.

---

## 6. Resource & VRAM Management

- **Model Lifecycle:** Deep learning models (Whisper ASR, YOLO face detectors, TransNetV2 scene detector) consume large amounts of VRAM.
  - Immediately unload models and free GPU memory after processing passes: call `transcribe_backends.release_models()` and `torch.cuda.empty_cache()`.
- **Job Concurrency:** Respect `MAX_CONCURRENT_JOBS`. Never exceed GPU VRAM allocation boundaries. Free-tier CPU jobs must route to remote CPU workers (`remote_worker.py`) without occupying local GPU slots.
- **I/O & File Cleanup:** Ensure file descriptors and context managers are closed properly (`with open(...)`, `contextlib.closing`). Clean temporary files in `uploads/` and intermediate frames upon job completion.

---

## 7. Frontend Code Conventions (Dashboard)

- **React 18 & Vite:** Functional components, React hooks (`useState`, `useEffect`, `useCallback`, `useMemo`), avoiding redundant re-renders.
- **Design Tokens:** Strictly adhere to `design.md` tokens:
  - Colors: `bg-paper`, `bg-paper2`, `bg-paper3`, `text-ink`, `text-ink2`, `text-muted`, `border-rule`, `border-rule2`, `text-brass`, `text-coral`.
  - Radii: `rounded-card` (10px), `rounded-input` (8px), `rounded-full` (pills only).
  - Typography: Instrument Serif for display headlines, Geist for body, JetBrains Mono for UPPERCASE readouts.
- **Linting Gate:** Code must pass `npm run lint` with `--max-warnings 0` before check-in.
