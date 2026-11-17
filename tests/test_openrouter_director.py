import pytest
from pydantic import ValidationError
from editor import (
    OpenRouterClient,
    ViralDirectorEditingPlan,
    HookDirectorConfig,
    CameraMovementSegment,
    SFXEvent,
    StickerEvent,
    KineticSubtitlesDirectorConfig,
    RetentionBarDirectorConfig,
    VideoEditor,
)


def test_openrouter_client_requires_key_and_model():
    """Verify that OpenRouterClient enforces dynamic key and model with zero hardcoded defaults."""
    # Missing key raises ValueError
    with pytest.raises(ValueError, match="OpenRouter API key is required"):
        OpenRouterClient(api_key="", model="google/gemini-2.5-flash")

    with pytest.raises(ValueError, match="OpenRouter API key is required"):
        OpenRouterClient(api_key=None, model="google/gemini-2.5-flash")

    # Missing model raises ValueError (strict invariant: no hardcoded model)
    with pytest.raises(ValueError, match="OpenRouter model is required"):
        OpenRouterClient(api_key="sk-or-test-key", model="")

    with pytest.raises(ValueError, match="OpenRouter model is required"):
        OpenRouterClient(api_key="sk-or-test-key", model="   ")

    # Valid key and arbitrary dynamic model slug works
    client = OpenRouterClient(api_key="sk-or-test-key", model="deepseek/deepseek-chat")
    assert client.api_key == "sk-or-test-key"
    assert client.model == "deepseek/deepseek-chat"
    assert hasattr(client, "generate_json")
    assert hasattr(client, "generate_json_async")


def test_viral_director_editing_plan_schema():
    """Verify ViralDirectorEditingPlan schema parsing and validation."""
    valid_data = {
        "directorsVision": "Hook the viewer with an urgent curiosity gap, then dynamic zooms.",
        "hook": {
            "text": "THIS CHANGES EVERYTHING 🤯",
            "style": "pill",
            "position": "top",
            "positionY": 0.12,
            "durationSec": 3.5,
            "startSec": 0.0,
            "entranceAnimation": "spring",
        },
        "cameraChoreography": [
            {
                "startSec": 0.0,
                "endSec": 2.5,
                "zoom": 1.25,
                "zoomCenterX": 0.5,
                "zoomCenterY": 0.4,
                "screenShake": False,
                "colorTone": "normal",
                "sfx": "whoosh",
            },
            {
                "startSec": 2.5,
                "endSec": 5.0,
                "zoom": 1.0,
                "zoomCenterX": 0.5,
                "zoomCenterY": 0.4,
                "screenShake": True,
                "colorTone": "vibrant",
            },
        ],
        "sfxTrack": [
            {"timeSec": 0.1, "effect": "whoosh", "volume": 0.8},
            {"timeSec": 2.5, "effect": "vine_boom", "volume": 0.9},
        ],
        "stickers": [
            {
                "timeSec": 1.2,
                "durationSec": 1.5,
                "type": "mind_blown",
                "customEmoji": "🤯",
                "positionX": 0.5,
                "positionY": 0.35,
                "scale": 1.2,
                "animation": "pop",
            }
        ],
        "kineticSubtitles": {
            "animation": "karaoke",
            "fontFamily": "Montserrat, sans-serif",
            "fontSize": 76,
            "color": "#FFFFFF",
            "highlightColor": "#FFE600",
            "semanticColors": True,
            "uppercase": True,
            "baseOpacity": 0.4,
            "maxWordsPerSegment": 3,
        },
        "retentionBar": {
            "enabled": True,
            "position": "bottom",
            "color": "#FFE600",
            "heightPx": 8,
        },
    }

    plan = ViralDirectorEditingPlan.model_validate(valid_data)
    assert plan.hook.text == "THIS CHANGES EVERYTHING 🤯"
    assert len(plan.cameraChoreography) == 2
    assert len(plan.sfxTrack) == 2
    assert plan.sfxTrack[1].effect == "vine_boom"
    assert plan.retentionBar.enabled is True


def test_camera_and_sfx_sanitization():
    """Verify camera segment gap-filling and sfx anti-spam sanitization."""
    duration = 10.0
    # Camera with gap
    sparse_camera = [
        {"startSec": 2.0, "endSec": 5.0, "zoom": 1.25, "zoomCenterX": 0.5, "zoomCenterY": 0.4}
    ]
    sanitized_cam = VideoEditor._sanitize_camera_segments(sparse_camera, duration)
    # Must start at 0.0 and end at 10.0 with 0 gaps
    assert sanitized_cam[0]["startSec"] == 0.0
    assert sanitized_cam[-1]["endSec"] == duration
    for i in range(len(sanitized_cam) - 1):
        assert abs(sanitized_cam[i]["endSec"] - sanitized_cam[i + 1]["startSec"]) < 0.001

    # SFX with spam (< 0.5s apart)
    spam_sfx = [
        {"timeSec": 1.0, "effect": "whoosh", "volume": 0.8},
        {"timeSec": 1.2, "effect": "whoosh", "volume": 0.8},  # Should be dropped
        {"timeSec": 2.0, "effect": "pop", "volume": 0.8},     # Kept
    ]
    sanitized_sfx = VideoEditor._sanitize_sfx_track(spam_sfx, duration)
    assert len(sanitized_sfx) == 2
    assert sanitized_sfx[0]["timeSec"] == 1.0
    assert sanitized_sfx[1]["timeSec"] == 2.0
