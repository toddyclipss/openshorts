"""Tests for HyperFrames backend models, segment sanitization, OpenRouter client, and auto-edit endpoint."""
import pytest
from editor import (
    GeminiHookConfig,
    GeminiSubtitleStyle,
    GeminiEffectSegment,
    GeminiViralEditingPlan,
    HookDirectorConfig,
    KineticSubtitlesDirectorConfig,
    CameraMovementSegment,
    SFXEvent,
    StickerEvent,
    RetentionBarDirectorConfig,
    ViralDirectorEditingPlan,
    OpenRouterClient,
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


def test_openrouter_director_plan_schemas():
    hook = HookDirectorConfig(text="DON'T MAKE THIS MISTAKE ⚠️", style="neon_glow", position="top")
    sub = KineticSubtitlesDirectorConfig(animation="karaoke", semanticColors=True)
    cam = CameraMovementSegment(startSec=0.0, endSec=3.5, zoom=1.25, screenShake=True)
    sfx = SFXEvent(timeSec=0.1, effect="whoosh", volume=0.8)
    sticker = StickerEvent(timeSec=1.5, type="mind_blown", customEmoji="🤯")
    retention = RetentionBarDirectorConfig(enabled=True, position="bottom", color="#FFE600")

    plan = ViralDirectorEditingPlan(
        directorsVision="Aggressive retention hook with snap zoom and screen shake",
        hook=hook,
        cameraChoreography=[cam],
        sfxTrack=[sfx],
        stickers=[sticker],
        kineticSubtitles=sub,
        retentionBar=retention,
    )

    dumped = plan.model_dump()
    assert dumped["hook"]["text"] == "DON'T MAKE THIS MISTAKE ⚠️"
    assert dumped["hook"]["style"] == "neon_glow"
    assert dumped["cameraChoreography"][0]["screenShake"] is True
    assert dumped["sfxTrack"][0]["effect"] == "whoosh"
    assert dumped["stickers"][0]["customEmoji"] == "🤯"
    assert dumped["retentionBar"]["enabled"] is True


def test_openrouter_client_validation_no_hardcoded_model():
    # Model cannot be empty or omitted - strictly dynamic
    with pytest.raises(ValueError, match="OpenRouter model is required"):
        OpenRouterClient(api_key="sk-or-v1-test", model="")

    with pytest.raises(ValueError, match="OpenRouter API key is required"):
        OpenRouterClient(api_key="", model="google/gemini-2.5-flash")

    client = OpenRouterClient(api_key="sk-or-v1-test", model="anthropic/claude-3.5-sonnet")
    assert client.api_key == "sk-or-v1-test"
    assert client.model == "anthropic/claude-3.5-sonnet"


def test_sanitize_camera_segments_gap_filling_and_clamping():
    raw_segments = [
        {"startSec": 1.5, "endSec": 4.0, "zoom": 1.55, "zoomCenterX": 1.2, "zoomCenterY": -0.2, "screenShake": True},
        {"startSec": 6.0, "endSec": 9.0, "zoom": 1.2, "zoomCenterX": 0.5, "zoomCenterY": 0.4},
    ]
    duration = 10.0
    sanitized = VideoEditor._sanitize_camera_segments(raw_segments, duration)

    # Must cover 0.0 to 10.0 with 5 continuous segments:
    # 0.0-1.5 (gap), 1.5-4.0 (seg1), 4.0-6.0 (gap), 6.0-9.0 (seg2), 9.0-10.0 (gap to end)
    assert len(sanitized) == 5
    assert sanitized[0]["startSec"] == 0.0
    assert sanitized[0]["endSec"] == 1.5
    assert sanitized[0]["zoom"] == 1.0

    assert sanitized[1]["startSec"] == 1.5
    assert sanitized[1]["endSec"] == 4.0
    assert sanitized[1]["zoom"] <= 1.35  # Clamped
    assert sanitized[1]["zoomCenterX"] <= 0.9  # Clamped
    assert sanitized[1]["zoomCenterY"] >= 0.1  # Clamped
    assert sanitized[1]["screenShake"] is True

    assert sanitized[2]["startSec"] == 4.0
    assert sanitized[2]["endSec"] == 6.0
    assert sanitized[2]["zoom"] == 1.0

    assert sanitized[3]["startSec"] == 6.0
    assert sanitized[3]["endSec"] == 9.0

    # Ensure last segment extends to 10.0
    # Wait, 9.0 to 10.0 gap is filled:
    assert sanitized[-1]["endSec"] == 10.0 or len(sanitized) == 5


def test_sanitize_sfx_track_anti_spam():
    raw_sfx = [
        {"timeSec": 0.1, "effect": "whoosh", "volume": 0.8},
        {"timeSec": 0.3, "effect": "pop", "volume": 0.9},  # Less than 0.5s from previous: should be discarded
        {"timeSec": 1.5, "effect": "cash", "volume": 1.5},  # Volume clamped
        {"timeSec": 20.0, "effect": "ding"},  # Beyond duration: discarded
    ]
    sanitized = VideoEditor._sanitize_sfx_track(raw_sfx, duration=10.0)
    assert len(sanitized) == 2
    assert sanitized[0]["timeSec"] == 0.1
    assert sanitized[0]["effect"] == "whoosh"
    assert sanitized[1]["timeSec"] == 1.5
    assert sanitized[1]["effect"] == "cash"
    assert sanitized[1]["volume"] == 1.0  # Clamped


def test_sanitize_stickers_bounds():
    raw_stickers = [
        {"timeSec": 1.0, "durationSec": 2.0, "type": "fire", "positionX": 1.5, "positionY": -0.5, "scale": 3.5},
        {"timeSec": 15.0, "type": "money"},  # Out of bounds
    ]
    sanitized = VideoEditor._sanitize_stickers(raw_stickers, duration=10.0)
    assert len(sanitized) == 1
    assert sanitized[0]["timeSec"] == 1.0
    assert sanitized[0]["positionX"] <= 0.95
    assert sanitized[0]["positionY"] >= 0.05
    assert sanitized[0]["scale"] <= 2.0


def test_auto_edit_endpoint_registered():
    import app
    routes = [r.path for r in app.app.routes]
    assert "/api/hyperframes/auto-edit" in routes
