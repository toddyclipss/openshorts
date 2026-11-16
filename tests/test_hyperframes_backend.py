"""Tests for HyperFrames backend models, segment sanitization, and auto-edit endpoint."""
import pytest
from editor import (
    GeminiHookConfig,
    GeminiSubtitleStyle,
    GeminiEffectSegment,
    GeminiViralEditingPlan,
    VideoEditor,
)


def test_gemini_models_instantiation():
    hook = GeminiHookConfig(text="TEST HOOK 🔥", style="pill", position="top", displayDurationSec=3.5)
    assert hook.text == "TEST HOOK 🔥"
    assert hook.style == "pill"
    assert hook.position == "top"

    sub = GeminiSubtitleStyle(animation="karaoke", highlightColor="#00FF66", uppercase=True)
    assert sub.animation == "karaoke"
    assert sub.highlightColor == "#00FF66"
    assert sub.uppercase is True

    seg = GeminiEffectSegment(startSec=0.0, endSec=4.0, zoom=1.2, zoomCenterX=0.5, zoomCenterY=0.4)
    assert seg.zoom == 1.2

    plan = GeminiViralEditingPlan(hook=hook, subtitles=sub, effects=[seg])
    dumped = plan.model_dump()
    assert dumped["hook"]["text"] == "TEST HOOK 🔥"
    assert len(dumped["effects"]) == 1


def test_sanitize_effect_segments_gap_filling():
    # Gap between 0 and 2.0, gap between 5.0 and 8.0, ends before 10.0
    raw_segments = [
        {"startSec": 2.0, "endSec": 5.0, "zoom": 1.25, "zoomCenterX": 0.5, "zoomCenterY": 0.4},
        {"startSec": 8.0, "endSec": 9.5, "zoom": 1.35, "zoomCenterX": 0.5, "zoomCenterY": 0.4},
    ]
    duration = 10.0
    sanitized = VideoEditor._sanitize_effect_segments(raw_segments, duration)

    # Must cover 0.0 to 10.0 completely with no gaps
    assert len(sanitized) == 5
    assert sanitized[0]["startSec"] == 0.0
    assert sanitized[0]["endSec"] == 2.0
    assert sanitized[0]["zoom"] == 1.0

    assert sanitized[1]["startSec"] == 2.0
    assert sanitized[1]["endSec"] == 5.0
    assert sanitized[1]["zoom"] == 1.25

    assert sanitized[2]["startSec"] == 5.0
    assert sanitized[2]["endSec"] == 8.0
    assert sanitized[2]["zoom"] == 1.0

    assert sanitized[3]["startSec"] == 8.0
    assert sanitized[3]["endSec"] == 9.5
    assert sanitized[3]["zoom"] == 1.35

    assert sanitized[4]["startSec"] == 9.5
    assert sanitized[4]["endSec"] == 10.0
    assert sanitized[4]["zoom"] == 1.0


def test_sanitize_effect_segments_clamping():
    # Extreme zooms and coordinates should be clamped to safe ranges
    raw_segments = [
        {"startSec": 0.0, "endSec": 5.0, "zoom": 2.5, "zoomCenterX": 1.5, "zoomCenterY": -0.5, "brightness": 2.0},
    ]
    sanitized = VideoEditor._sanitize_effect_segments(raw_segments, 5.0)
    assert sanitized[0]["zoom"] <= 1.45
    assert sanitized[0]["zoomCenterX"] <= 0.9
    assert sanitized[0]["zoomCenterY"] >= 0.1
    assert sanitized[0]["brightness"] <= 1.2


def test_auto_edit_endpoint_registered():
    import app
    routes = [r.path for r in app.app.routes]
    assert "/api/hyperframes/auto-edit" in routes
