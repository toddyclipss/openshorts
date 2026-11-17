# Operations & Outcome as a Service (OaaS) Operating Principle

## 1. Core Principle & Definition

**Operations as a Service (OaaS)** is the foundational service and execution philosophy of OpenShorts:
> **The focus is never the sale of an isolated tool, raw software access, or billable hours; the focus is the autonomous, turnkey delivery of an end result and a complete operation.**

In OpenShorts, users and client systems do not seek raw compute cycles or pipeline complexity—they seek finished, high-retention, viral-ready vertical video assets and fully managed social media output.

---

## 2. Agent Mindset & Execution Invariants

When working on features, bug fixes, or agent workflows, the agent must adhere to the following operational invariants:

### 2.1 Outcome Ownership Over Task Delegation
- **Deliver Complete Results:** Never stop at intermediate files, partial implementations, or manual hand-offs (e.g., avoid "now run this manually" or "configure X yourself"). Drive workflows to finished, verified outcomes.
- **Turnkey Production Readiness:** Generated deliverables (clips, thumbnails, hooks, subtitles) must be delivered fully packaged and immediately publishable without requiring manual touch-ups by the user.

### 2.2 Resilient Failover & Autonomous Recovery
- In an OaaS model, service interruptions directly impact the end outcome. Code and workers must embody autonomous fault tolerance:
  - **Proxy / Download Resiliency:** Seamless failover across direct connection → static ISP proxies → paid proxies.
  - **Rendering Resiliency:** If GPU acceleration (`gpu_render` / `osrender`) is unavailable or fails on a complex filtergraph, transparently fall back to FFmpeg CPU rendering to ensure delivery.
  - **Model & API Fallbacks:** If LLM inference degrades, fall back to secondary endpoints or rule-based heuristics rather than aborting job pipelines.

### 2.3 Value & Retention Over Technical Vanity
- Every algorithmic choice (moment selection scoring, subtitle pacing, active speaker framing, hook text placement) must optimize for **the end result**: audience engagement, viewer retention, and virality.
- Do not introduce operational complexity that does not measurably improve output quality, rendering speed, or service reliability.

### 2.4 Zero Unfinished Artifacts
- Never commit placeholder code, stubbed endpoints, or `// TODO` items in critical paths.
- All delivered API responses, CLI actions, and UI states must be functionally complete, tested, and self-contained.
