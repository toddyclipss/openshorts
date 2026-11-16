import os
import json
import re
import subprocess
import time
from typing import List, Optional, Dict, Any
from google import genai
from google.genai import types
from pydantic import BaseModel

import gemini_worker
from edit_builder import build_filter_string
from ffmpeg_utils import video_encode_args, QUALITY, METADATA_SCRUB


class EditDecision(BaseModel):
    type: str
    start: float
    end: float
    strength: float = 0.0
    reason: str = ""


class EditPlan(BaseModel):
    edits: List[EditDecision]


class GeminiHookConfig(BaseModel):
    text: str
    style: str = "pill"
    position: str = "top"
    displayDurationSec: float = 3.5
    entranceAnimation: str = "spring"


class GeminiSubtitleStyle(BaseModel):
    animation: str = "karaoke"
    highlightColor: str = "#FFE600"
    uppercase: bool = True
    baseOpacity: float = 0.4


class GeminiEffectSegment(BaseModel):
    startSec: float
    endSec: float
    zoom: float = 1.0
    zoomCenterX: float = 0.5
    zoomCenterY: float = 0.4
    brightness: float = 1.0
    contrast: float = 1.0
    saturate: float = 1.0


class GeminiViralEditingPlan(BaseModel):
    hook: GeminiHookConfig
    subtitles: GeminiSubtitleStyle
    effects: List[GeminiEffectSegment]


class VideoEditor:
    def __init__(self, api_key):
        self.client = genai.Client(api_key=api_key)
        self.model_name = (
            os.environ.get("GEMINI_MODEL_EDITOR")
            or os.environ.get("GEMINI_MODEL")
            or "gemini-3.1-flash-lite"
        )

    def upload_video(self, video_path):
        """Uploads video to Gemini File API."""
        print(f"📤 Uploading {video_path} to Gemini...")
        
        # Ensure we are passing a path that exists
        if not os.path.exists(video_path):
            raise FileNotFoundError(f"Video file not found: {video_path}")
            
        # Using 'file' keyword instead of 'path'
        try:
            file_upload = gemini_worker.upload_media(self.client, video_path)
        except Exception as e:
            print(f"❌ Gemini Upload Error: {e}")
            raise e
        
        # Wait for processing
        print("⏳ Waiting for video processing by Gemini...")
        deadline = time.time() + 120
        while True:
            file_info = self.client.files.get(name=file_upload.name)
            state = getattr(file_info, "state", file_info)
            state_name = str(getattr(state, "name", state)).upper()
            if state_name == "ACTIVE":
                print("✅ Video processed and ready.")
                return file_upload
            if state_name == "FAILED":
                raise Exception("Video processing failed by Gemini.")
            if time.time() > deadline:
                raise TimeoutError("Gemini file processing timed out after 120s.")
            time.sleep(2)

    def delete_uploaded(self, video_file_obj):
        """Remove an uploaded clip from the Gemini Files API.

        The upload is a full copy of the user's video on Google's servers, kept
        there for 48 h if nobody deletes it. The effects passes need it for one
        request; every caller must drop it in a ``finally`` right after, so the
        privacy policy's "we do not leave your footage with the model provider"
        describes the code. Best-effort: an editing job must not fail because
        the cleanup call did.
        """
        name = getattr(video_file_obj, "name", None)
        if not name:
            return
        try:
            self.client.files.delete(name=name)
        except Exception as e:
            print(f"⚠️ Could not delete {name} from Gemini Files ({e}) — "
                  f"it expires there in 48 h.")

    def get_ffmpeg_filter(self, video_file_obj, duration, fps=30, width=None, height=None, transcript=None, has_captions=False):
        """Asks Gemini for an edit decision list, then builds the FFmpeg filter
        deterministically (edit_builder) so syntax and zoom limits are always safe."""
        if width is None or height is None:
            # Keep prompt usable even if caller didn't pass dimensions.
            width, height = 1080, 1920

        transcript_text = json.dumps(transcript) if transcript else "Not available."

        caption_rule = ""
        if has_captions:
            caption_rule = (
                "\n        CRITICAL: This video already has burned-in captions and/or a hook text. "
                "Any zoom would crop or shift them off screen. Do NOT use zoom_in, punch_in or zoom_pulse — "
                "only color_pop, bw_moment, flash and vignette are allowed.\n"
            )

        prompt = f"""
        You are a viral short-form video editor (TikTok / Reels / Shorts). You receive a video and its transcript.
        Decide WHERE a small set of tasteful, high-impact effects belongs. You do NOT write FFmpeg —
        you return an edit decision list, and a deterministic renderer applies it safely.

        Video duration: {duration:.1f} seconds. Resolution: {width}x{height}.

        Available effect types:
        - "zoom_in": slow push-in across the segment. Builds tension or focus on a key statement. strength 0.06-0.15, segment 1.5-6s.
        - "punch_in": instant tighter framing for the whole segment. Emphasis, punchlines, "listen to this" moments. strength 0.06-0.15, segment 0.8-5s.
        - "zoom_pulse": quick in-and-out pulse peaking mid-segment. Beat drops, single impactful words. strength 0.04-0.10, segment 0.4-1.2s.
        - "color_pop": richer saturation/contrast. Energy, excitement, product/visual highlights. strength 0.2-1.0.
        - "bw_moment": black & white. Drama, serious quotes, flashbacks.
        - "flash": brief bright flash at segment start. Hard-cut energy, reveals. Use at most 2.
        - "vignette": darkened edges. Focus, intimacy, storytelling moments.

        Rules:
        1. Match effects to the CONTENT: place them on the exact words or moments they emphasize, using the transcript timestamps.
        2. Less is more: 2-6 edits per 30 seconds of video. A random effect is worse than no effect.
        3. Never overlap two zoom-type edits (zoom_in/punch_in/zoom_pulse).
        4. Calm, serious delivery => few or no motion effects. High-energy content => more punch.
        {caption_rule}
        TRANSCRIPT (with timestamps, the context of what is being said):
        {transcript_text}

        Return JSON only:
        {{"edits": [{{"type": "punch_in", "start": 3.2, "end": 5.4, "strength": 0.1, "reason": "punchline"}}]}}
        If no effects genuinely improve the video, return {{"edits": []}}.
        """

        print("🤖 Asking Gemini for an edit decision list...")
        # Low media resolution: Gemini samples at 1 FPS and normalizes frames to
        # fixed token sizes, so "low" (~70 tokens/frame) cuts video-input cost
        # without hurting motion/scene understanding. Fall back to defaults if
        # the SDK or model rejects the option.
        try:
            config = types.GenerateContentConfig(
                response_mime_type="application/json",
                response_schema=EditPlan,
                media_resolution=types.MediaResolution.MEDIA_RESOLUTION_LOW,
            )
        except Exception:
            config = types.GenerateContentConfig(
                response_mime_type="application/json",
                response_schema=EditPlan,
            )
        try:
            response = self.client.models.generate_content(
                model=self.model_name,
                contents=[video_file_obj, prompt],
                config=config,
            )
        except Exception as e:
            if getattr(config, "media_resolution", None) is None:
                raise
            print(f"⚠️ media_resolution=low rejected ({e}); retrying with defaults...")
            response = self.client.models.generate_content(
                model=self.model_name,
                contents=[video_file_obj, prompt],
                config=types.GenerateContentConfig(
                    response_mime_type="application/json",
                    response_schema=EditPlan,
                ),
            )

        raw_edits = self._extract_edits(response)
        if raw_edits is None:
            return None

        filter_string, applied = build_filter_string(
            raw_edits, duration=duration, fps=fps, width=width, height=height,
            has_captions=has_captions,
        )
        if not filter_string:
            print("ℹ️ Gemini suggested no (valid) edits — keeping the clip untouched.")
            return {"filter_string": None, "edits": []}
        print(f"🎯 Applying {len(applied)} edits: " + ", ".join(f"{e['type']}@{e['start']:.1f}s" for e in applied))
        return {"filter_string": filter_string, "edits": applied}

    def get_effects_config(self, video_file_obj, duration, fps=30, width=None, height=None, transcript=None):
        """Asks Gemini for a structured EffectsConfig JSON for Remotion rendering."""
        if width is None or height is None:
            width, height = 1080, 1920

        transcript_text = json.dumps(transcript) if transcript else "Not available."

        prompt = f"""
        You are an expert video editor analyzing a video and its transcript to generate dynamic visual effects for a Remotion-based renderer.

        Video Duration: {duration} seconds.
        Video FPS: {fps}
        Video Resolution: {width}x{height}

        TRANSCRIPT (Context of what is being said):
        {transcript_text}

        Your task is to produce a structured JSON describing time-based effect segments that cover the FULL video duration.

        Each segment has these fields:
        - "startSec" (number): Start time in seconds.
        - "endSec" (number): End time in seconds.
        - "zoom" (number): Zoom level. 1.0 = no zoom, max 1.5. Use subtle values like 1.05-1.2 for most cases.
        - "zoomCenterX" (number): Horizontal focus point for zoom, 0.0 (left) to 1.0 (right). 0.5 = center.
        - "zoomCenterY" (number): Vertical focus point for zoom, 0.0 (top) to 1.0 (bottom). 0.5 = center.
        - "brightness" (number): Brightness multiplier. 1.0 = normal. Range 0.8-1.2.
        - "contrast" (number): Contrast multiplier. 1.0 = normal. Range 0.8-1.3.
        - "saturate" (number): Saturation multiplier. 1.0 = normal. Range 0.8-1.3.

        Instructions:
        1. ANALYZE the video content and transcript to understand mood, pacing, and key moments.
        2. Apply CONTEXTUAL effects aligned with speech and action:
           - Use slow, subtle zooms toward the speaker's face during speaking moments.
           - Emphasize key moments, punchlines, or dramatic beats with slightly stronger zoom or contrast.
           - Keep transitions smooth — avoid jarring jumps between segments.
           - If nothing significant is happening, keep values at defaults (zoom 1.0, all multipliers 1.0).
        3. Segments MUST cover the entire video duration from 0 to {duration} seconds with no gaps.
        4. Prefer fewer, longer segments with gradual changes over many rapid short segments.
        5. Output ONLY valid JSON, no explanations.

        Output format:
        {{
            "segments": [
                {{
                    "startSec": 0,
                    "endSec": 3.5,
                    "zoom": 1.0,
                    "zoomCenterX": 0.5,
                    "zoomCenterY": 0.5,
                    "brightness": 1.0,
                    "contrast": 1.0,
                    "saturate": 1.0
                }}
            ]
        }}
        """

        print("🤖 Asking Gemini for Remotion effects config...")
        response = self.client.models.generate_content(
            model=self.model_name,
            contents=[video_file_obj, prompt],
            config=types.GenerateContentConfig(
                response_mime_type="application/json"
            )
        )

        print(f"🔍 DEBUG: Gemini Raw Response:\n{response.text}")

        try:
            # Clean response text (remove potential markdown blocks)
            text = response.text
            if text.startswith("```json"):
                text = text[7:]
            elif text.startswith("```"):
                text = text[3:]

            if text.endswith("```"):
                text = text[:-3]

            text = text.strip()

            # Find the first '{' and last '}'
            start_idx = text.find('{')
            end_idx = text.rfind('}')

            if start_idx != -1 and end_idx != -1:
                text = text[start_idx:end_idx+1]

            print(f"🔍 DEBUG: Cleaned JSON Text:\n{text}")

            return json.loads(text)
        except json.JSONDecodeError:
            print(f"❌ Failed to parse effects config JSON: {response.text}")
            return None

    @staticmethod
    def _sanitize_effect_segments(raw_segments: List[dict], duration: float) -> List[dict]:
        """Ensures effect segments cover the full duration with no gaps or overlaps."""
        duration = float(duration)
        if not raw_segments:
            return [{
                "startSec": 0.0,
                "endSec": round(duration, 2),
                "zoom": 1.0,
                "zoomCenterX": 0.5,
                "zoomCenterY": 0.4,
                "brightness": 1.0,
                "contrast": 1.0,
                "saturate": 1.0,
            }]

        sorted_segs = sorted(raw_segments, key=lambda s: float(s.get("startSec", 0.0)))
        sanitized: List[dict] = []
        current_time = 0.0

        for seg in sorted_segs:
            start = round(max(0.0, float(seg.get("startSec", 0.0))), 2)
            end = round(min(duration, float(seg.get("endSec", duration))), 2)

            if end <= start:
                continue

            if start > current_time:
                sanitized.append({
                    "startSec": current_time,
                    "endSec": start,
                    "zoom": 1.0,
                    "zoomCenterX": 0.5,
                    "zoomCenterY": 0.4,
                    "brightness": 1.0,
                    "contrast": 1.0,
                    "saturate": 1.0,
                })
                current_time = start

            zoom = round(max(1.0, min(1.45, float(seg.get("zoom", 1.0)))), 2)
            cx = round(max(0.1, min(0.9, float(seg.get("zoomCenterX", 0.5)))), 2)
            cy = round(max(0.1, min(0.9, float(seg.get("zoomCenterY", 0.4)))), 2)
            b = round(max(0.8, min(1.2, float(seg.get("brightness", 1.0)))), 2)
            c = round(max(0.8, min(1.3, float(seg.get("contrast", 1.0)))), 2)
            s = round(max(0.8, min(1.3, float(seg.get("saturate", 1.0)))), 2)

            sanitized.append({
                "startSec": current_time,
                "endSec": end,
                "zoom": zoom,
                "zoomCenterX": cx,
                "zoomCenterY": cy,
                "brightness": b,
                "contrast": c,
                "saturate": s,
            })
            current_time = end

        if current_time < duration:
            sanitized.append({
                "startSec": current_time,
                "endSec": round(duration, 2),
                "zoom": 1.0,
                "zoomCenterX": 0.5,
                "zoomCenterY": 0.4,
                "brightness": 1.0,
                "contrast": 1.0,
                "saturate": 1.0,
            })

        return sanitized

    def get_viral_hyperframes_props(
        self,
        video_file_obj,
        duration: float,
        fps: float = 30.0,
        width: int = 1080,
        height: int = 1920,
        transcript: Optional[dict] = None,
        predicted_score: Optional[int] = None,
        viral_hook_text: Optional[str] = None,
        why: Optional[str] = None,
        captions: Optional[List[dict]] = None,
    ) -> dict:
        """Asks Gemini for a comprehensive, structured HyperFrames viral editing plan.

        Choreographs:
        1. High-curiosity viral headline hook (style, position, animation, text).
        2. Dynamic word-level subtitle styling (karaoke / pop, highlight colors).
        3. Gapless camera zooms and color grading over the entire clip duration.
        """
        uploaded_here = False
        active_file_obj = video_file_obj
        if isinstance(video_file_obj, str):
            active_file_obj = self.upload_video(video_file_obj)
            uploaded_here = True

        try:
            transcript_text = json.dumps(transcript) if transcript else "Not available."
            score_readout = f"{predicted_score}/100" if predicted_score is not None else "High"
            initial_hook = viral_hook_text or ""
            initial_why = why or ""

            prompt = f"""
You are an elite viral short-form video director (TikTok, Instagram Reels, YouTube Shorts).
Your mission is to maximize retention, scroll-stopping visual impact, and viewer engagement.

Clip Metadata:
- Duration: {duration:.2f} seconds ({int(round(duration * fps))} frames @ {fps} fps)
- Resolution: {width}x{height} (9:16 vertical)
- Predicted Virality Score: {score_readout}
- Candidate Hook Idea: "{initial_hook}"
- Viral Rationale: "{initial_why}"

TRANSCRIPT (Context of spoken words with timestamps):
{transcript_text}

Produce a structured viral editing plan (GeminiViralEditingPlan) with three unified components:

1. HOOK HEADLINE (Opening 2.5s - 4.5s):
   - Short, punchy, high-curiosity headline (3 to 6 words) in ALL-CAPS with 1 emotional emoji at the end.
   - Must evoke intense curiosity without misleading. Example: "THIS CHANGED EVERYTHING 🤯", "DON'T MAKE THIS MISTAKE ⚠️".
   - style: "pill" (default rounded modern badge), "yellow", "dark", "outline", or "neon_glow".
   - position: "top" (keeps vertical center clear for speaker).
   - entranceAnimation: "spring" (punchy pop) or "slide-up".
   - displayDurationSec: between 3.0 and 4.2 seconds.

2. SUBTITLE STYLING:
   - High-contrast, high-energy subtitle treatment for mobile screens.
   - animation: "karaoke" (active word brightly highlighted while inactive words remain legible but dimmed) or "pop".
   - highlightColor: pick a vibrant retention color (e.g. "#FFE600" yellow, "#00FF66" neon green, "#00F0FF" electric cyan, "#FF3366" hot pink).
   - uppercase: true (all-caps format maximizes readability).
   - baseOpacity: 0.35 to 0.45.

3. CAMERA ZOOMS & COLOR EFFECTS:
   - Choreograph time-based effect segments that cover the FULL video duration from 0.0s to {duration:.2f}s with NO GAPS.
   - The first segment MUST start at 0.0. The last segment MUST end at {duration:.2f}.
   - Zoom levels:
     * 1.00: Standard framing (neutral sections).
     * 1.08 - 1.15: Subtle push-in to focus on storytelling or build-up.
     * 1.22 - 1.35: Punch-in zoom on punchlines, dramatic moments, or key revelations.
   - In 9:16 vertical video, the speaker's face is centered horizontally (zoomCenterX = 0.5) and located in the upper half (zoomCenterY = 0.38 - 0.44).
   - Color multipliers: subtle enhancement during high-energy moments (brightness 1.02-1.08, contrast 1.05-1.12, saturate 1.05-1.15). Keep 1.0 when neutral.
   - Keep segments purposeful: 3 to 6 well-timed segments per 30 seconds aligned with speech cues.
"""
            print("🤖 Asking Gemini for HyperFrames viral editing plan...")
            raw_plan: Optional[GeminiViralEditingPlan] = None

            try:
                config = types.GenerateContentConfig(
                    response_mime_type="application/json",
                    response_schema=GeminiViralEditingPlan,
                )
                response = self.client.models.generate_content(
                    model=self.model_name,
                    contents=[active_file_obj, prompt],
                    config=config,
                )
                parsed = getattr(response, "parsed", None)
                if isinstance(parsed, GeminiViralEditingPlan):
                    raw_plan = parsed
                elif isinstance(parsed, dict):
                    raw_plan = GeminiViralEditingPlan.model_validate(parsed)
            except Exception as e:
                print(f"⚠️ Structured schema request failed ({e}); falling back to raw JSON parsing...")
                try:
                    response = self.client.models.generate_content(
                        model=self.model_name,
                        contents=[active_file_obj, prompt],
                        config=types.GenerateContentConfig(response_mime_type="application/json"),
                    )
                except Exception as ex:
                    print(f"❌ Gemini content generation failed: {ex}")
                    response = None

            if raw_plan is None and response and getattr(response, "text", None):
                text = response.text.strip()
                if text.startswith("```json"):
                    text = text[7:]
                elif text.startswith("```"):
                    text = text[3:]
                if text.endswith("```"):
                    text = text[:-3]
                text = text.strip()
                s_idx = text.find('{')
                e_idx = text.rfind('}')
                if s_idx != -1 and e_idx != -1:
                    try:
                        data = json.loads(text[s_idx:e_idx+1])
                        raw_plan = GeminiViralEditingPlan.model_validate(data)
                    except Exception as parse_err:
                        print(f"⚠️ Raw JSON parsing error: {parse_err}")

            # Safe fallbacks if Gemini provided partial or no plan
            hook_text = (
                (raw_plan.hook.text.strip() if raw_plan and raw_plan.hook and raw_plan.hook.text else None)
                or initial_hook.upper()
                or "MUST WATCH MOMENT 🔥"
            )
            hook_style = (raw_plan.hook.style if raw_plan and raw_plan.hook else None) or "pill"
            hook_position = (raw_plan.hook.position if raw_plan and raw_plan.hook else None) or "top"
            hook_entrance = (raw_plan.hook.entranceAnimation if raw_plan and raw_plan.hook else None) or "spring"
            hook_duration = (raw_plan.hook.displayDurationSec if raw_plan and raw_plan.hook else None) or min(4.0, max(2.5, duration * 0.25))

            sub_anim = (raw_plan.subtitles.animation if raw_plan and raw_plan.subtitles else None) or "karaoke"
            sub_highlight = (raw_plan.subtitles.highlightColor if raw_plan and raw_plan.subtitles else None) or "#FFE600"
            sub_opacity = (raw_plan.subtitles.baseOpacity if raw_plan and raw_plan.subtitles else None) or 0.4
            sub_uppercase = raw_plan.subtitles.uppercase if raw_plan and raw_plan.subtitles else True

            raw_effects = [e.model_dump() for e in raw_plan.effects] if raw_plan and raw_plan.effects else []
            sanitized_effects = self._sanitize_effect_segments(raw_effects, duration)

            total_frames = max(1, int(round(duration * fps)))

            return {
                "durationInFrames": total_frames,
                "fps": fps,
                "width": width,
                "height": height,
                "hook": {
                    "text": hook_text,
                    "position": hook_position,
                    "size": "M",
                    "style": hook_style,
                    "entranceAnimation": hook_entrance,
                    "displayDurationSec": round(float(hook_duration), 2),
                },
                "subtitles": {
                    "captions": captions or [],
                    "position": "bottom",
                    "style": {
                        "fontFamily": "Montserrat",
                        "fontSize": 72,
                        "fontColor": "#FFFFFF",
                        "highlightColor": sub_highlight,
                        "highlightTextColor": "#000000",
                        "borderColor": "#000000",
                        "borderWidth": 5,
                        "bgColor": "#000000",
                        "bgOpacity": 0.0,
                        "animation": sub_anim,
                        "baseOpacity": round(float(sub_opacity), 2),
                        "uppercase": sub_uppercase,
                        "reveal": True,
                        "shadow": 4,
                    },
                },
                "effects": {
                    "segments": sanitized_effects,
                },
            }
        finally:
            if uploaded_here and active_file_obj:
                self.delete_uploaded(active_file_obj)

    @staticmethod
    def _extract_edits(response):
        """Pull the edit list out of a Gemini response (parsed schema preferred,
        raw-JSON fallback). Returns a list of dicts, or None on hard failure."""
        parsed = getattr(response, "parsed", None)
        if parsed is not None:
            try:
                return [edit.model_dump() for edit in parsed.edits]
            except Exception:
                pass

        text = (getattr(response, "text", None) or "").strip()
        print(f"🔍 DEBUG: Gemini Raw Response:\n{text}")
        if text.startswith("```json"):
            text = text[7:]
        elif text.startswith("```"):
            text = text[3:]
        if text.endswith("```"):
            text = text[:-3]
        text = text.strip()
        start_idx = text.find('{')
        end_idx = text.rfind('}')
        if start_idx != -1 and end_idx != -1:
            text = text[start_idx:end_idx + 1]
        try:
            data = json.loads(text)
        except json.JSONDecodeError:
            print(f"❌ Failed to parse edit plan JSON: {text[:500]}")
            return None
        edits = data.get("edits") if isinstance(data, dict) else None
        return edits if isinstance(edits, list) else []

    @staticmethod
    def _split_filter_chain(filter_string: str) -> list[str]:
        """Split a -vf filter chain on commas, respecting single-quoted substrings."""
        parts: list[str] = []
        start = 0
        in_quote = False
        for i, ch in enumerate(filter_string):
            if ch == "'":
                in_quote = not in_quote
            elif ch == "," and not in_quote:
                parts.append(filter_string[start:i])
                start = i + 1
        parts.append(filter_string[start:])
        return parts

    @classmethod
    def _enforce_zoompan_output_size(cls, filter_string: str, width: int, height: int) -> str:
        """Force any zoompan filter to output the same geometry as the input clip."""
        parts = cls._split_filter_chain(filter_string)
        out_parts: list[str] = []
        for part in parts:
            if "zoompan=" in part:
                # Force s=WxH inside zoompan options (digitsxdigits only).
                if re.search(r":s=\d+x\d+", part):
                    part = re.sub(r":s=\d+x\d+", f":s={width}x{height}", part)
                else:
                    part = f"{part}:s={width}x{height}"
            out_parts.append(part)
        return ",".join(out_parts)

    @staticmethod
    def _sanitize_filter_string(filter_string: str) -> str:
        """
        Best-effort sanitizer for Gemini-generated FFmpeg expressions.
        Converts comparison operators (t<3, on>=75, etc.) into FFmpeg expr functions (lt(), gte(), ...),
        which are far more reliably parsed across FFmpeg builds.
        """
        s = filter_string

        # Order matters: handle >= / <= before > / <
        patterns: list[tuple[re.Pattern[str], str]] = [
            (re.compile(r"(?<![A-Za-z0-9_])([A-Za-z_]\w*)\s*>=\s*(-?\d+(?:\.\d+)?)"), r"gte(\1,\2)"),
            (re.compile(r"(?<![A-Za-z0-9_])([A-Za-z_]\w*)\s*<=\s*(-?\d+(?:\.\d+)?)"), r"lte(\1,\2)"),
            (re.compile(r"(?<![A-Za-z0-9_])([A-Za-z_]\w*)\s*>\s*(-?\d+(?:\.\d+)?)"), r"gt(\1,\2)"),
            (re.compile(r"(?<![A-Za-z0-9_])([A-Za-z_]\w*)\s*<\s*(-?\d+(?:\.\d+)?)"), r"lt(\1,\2)"),
        ]
        for pat, repl in patterns:
            s = pat.sub(repl, s)

        return s

    # The filters the edit builder emits (edit_builder.build_filter_string),
    # plus the ones this module adds itself. A filter string is run only if
    # every filter in it is one of these: none of them can open a file, and
    # anything else (a filter that reads a file, an instance name, a label, a
    # second chain) means the string was not built here. The self-repair path
    # is the one that returns free text from the model.
    _ALLOWED_FILTERS = frozenset({"eq", "zoompan", "vignette", "hue", "setsar",
                                  "format", "scale", "fps", "null"})

    @classmethod
    def _touches_files(cls, filter_string) -> bool:
        """True unless the string is a plain chain of the allowed filters."""
        s = str(filter_string or "")
        if not s.strip() or any(c in s for c in "@\\[];\n\r\x00"):
            return True
        for part in cls._split_filter_chain(s):
            name = part.strip().split("=", 1)[0].strip()
            if name not in cls._ALLOWED_FILTERS:
                return True
        return False

    @staticmethod
    def _ffmpeg_env():
        """The environment for an ffmpeg that runs a generated filter: the
        process's own, without anything named like a credential."""
        env = {k: v for k, v in os.environ.items()
               if not re.search(r"KEY|SECRET|TOKEN|PASSWORD|DATABASE|COOKIE|PROXY|DSN", k, re.I)}
        env["LANG"] = "C.UTF-8"
        env["LC_ALL"] = "C.UTF-8"
        return env

    @staticmethod
    def _test_filter(input_path, filter_string, env):
        """Dry-run the filter on the first 2 seconds (no output written).

        Catches broken Gemini-generated filter syntax in seconds instead of
        failing after a full-length encode. Returns (ok, stderr_tail)."""
        cmd = [
            'ffmpeg', '-v', 'error', '-t', '2',
            '-i', input_path,
            '-vf', filter_string,
            '-f', 'null', '-',
        ]
        try:
            result = subprocess.run(
                [a.encode('utf-8') if isinstance(a, str) else a for a in cmd],
                env=env, capture_output=True, timeout=120,
            )
        except subprocess.TimeoutExpired:
            return False, "filter dry-run timed out after 120s"
        if result.returncode == 0:
            return True, ""
        stderr_text = (result.stderr or b"").decode(errors="replace")
        return False, stderr_text[-1500:]

    def _repair_filter(self, filter_string, error_text, width, height):
        """One self-repair round-trip: show Gemini the FFmpeg error and ask for
        a corrected filter string. Returns the new string or None."""
        if not self.client:
            return None
        prompt = f"""
        The following FFmpeg -vf filter string you generated fails to run.

        FILTER:
        {filter_string}

        FFMPEG ERROR:
        {error_text}

        Fix the filter. Keep the same creative intent, obey the same rules as before:
        - exact output resolution {width}x{height} (zoompan must set s={width}x{height}),
        - no bare comparison operators (use between/lt/lte/gt/gte),
        - expression values in single quotes.
        Output JSON only: {{"filter_string": "..."}}
        """
        try:
            response = self.client.models.generate_content(
                model=self.model_name,
                contents=prompt,
                config=types.GenerateContentConfig(response_mime_type="application/json"),
            )
            text = (response.text or "").strip()
            start_idx = text.find('{')
            end_idx = text.rfind('}')
            if start_idx != -1 and end_idx != -1:
                text = text[start_idx:end_idx + 1]
            repaired = json.loads(text).get("filter_string")
            return repaired if isinstance(repaired, str) and repaired.strip() else None
        except Exception as e:
            print(f"⚠️ Filter self-repair failed: {e}")
            return None

    def apply_edits(self, input_path, output_path, filter_data):
        """Executes FFmpeg with the generated filter."""
        
        if (filter_data and filter_data.get("filter_string")
                and self._touches_files(filter_data["filter_string"])):
            print("⚠️ The filter names a file or a command filter. Not run; copying original.")
            filter_data = None
        if not filter_data or not filter_data.get("filter_string"):
            print("⚠️ No filter string found. Copying original.")
            try:
                subprocess.run(['ffmpeg', '-y', '-i', input_path, '-c', 'copy',
                                *METADATA_SCRUB, output_path], timeout=1800)
            except subprocess.TimeoutExpired:
                raise RuntimeError("FFmpeg copy timed out after 1800s.")
            return

        filter_string = filter_data["filter_string"]
        
        # Get input dimensions so we can enforce geometry (avoid broken aspect ratios).
        try:
            probe_cmd = ['ffprobe', '-v', 'error', '-select_streams', 'v:0', '-show_entries', 'stream=width,height', '-of', 'csv=s=x:p=0', input_path]
            res_out = subprocess.check_output(probe_cmd, env={**os.environ, "LANG": "C.UTF-8"}, timeout=60).decode().strip()
            w, h = map(int, res_out.split('x'))
        except Exception as e:
            print(f"⚠️ Could not probe resolution: {e}")
            w, h = None, None

        # Sanitize common expression pitfalls (e.g., t<3 / on>=75) before executing FFmpeg.
        sanitized = self._sanitize_filter_string(filter_string)
        if sanitized != filter_string:
            print("🧼 Sanitized AI Filter (converted comparisons to lt/lte/gt/gte functions)")
            print(f"🧼 Before: {filter_string}")
            print(f"🧼 After:  {sanitized}")
            filter_string = sanitized

        # Enforce zoompan output size to preserve aspect ratio / resolution.
        if w and h:
            enforced = self._enforce_zoompan_output_size(filter_string, w, h)
            if enforced != filter_string:
                print(f"📐 Enforced zoompan output size to {w}x{h}")
                filter_string = enforced

            # Ensure square pixels (avoid weird display stretching in some players).
            if "setsar=" not in filter_string:
                filter_string = f"{filter_string},setsar=1"

        # Use explicit environment with UTF-8 to avoid ascii errors in subprocess
        # On some minimal docker images, we need to ensure we use a UTF-8 locale
        # (C.UTF-8 is the safe one there). No credentials: ffmpeg needs none.
        env = self._ffmpeg_env()

        # Dry-run the filter on 2 seconds before committing to a full encode;
        # on failure, give Gemini one self-repair attempt with the real error.
        ok, error_text = self._test_filter(input_path, filter_string, env)
        if not ok:
            print(f"⚠️ AI filter failed dry-run: {error_text}")
            repaired = self._repair_filter(filter_string, error_text, w or 1080, h or 1920)
            if repaired and self._touches_files(repaired):
                print("⚠️ The repaired filter names a file or a command filter. Dropped.")
                repaired = None
            if repaired:
                repaired = self._sanitize_filter_string(repaired)
                if w and h:
                    repaired = self._enforce_zoompan_output_size(repaired, w, h)
                    if "setsar=" not in repaired:
                        repaired = f"{repaired},setsar=1"
                ok, error_text = self._test_filter(input_path, repaired, env)
                if ok:
                    print("🔧 Self-repaired AI filter passed dry-run.")
                    filter_string = repaired
            if not ok:
                raise RuntimeError(f"AI filter failed validation even after self-repair: {error_text}")

        print(f"🎬 Executing AI Filter: {filter_string}")

        cmd = [
            'ffmpeg', '-y',
            '-i', input_path,
            '-vf', filter_string,
            *video_encode_args(QUALITY),
            '-c:a', 'copy',
            *METADATA_SCRUB,
            '-movflags', '+faststart',
            output_path
        ]
        
        try:
            # We must encode arguments if filesystem is ascii but we have unicode chars
            # But subprocess in Python 3 handles unicode args by encoding them with os.fsencode().
            # If sys.getfilesystemencoding() is ascii, this fails.
            # We can't change fs encoding at runtime easily.
            # Workaround: pass bytes directly? subprocess allows bytes in args.
            
            # Convert command elements to bytes assuming utf-8 if they are strings
            cmd_bytes = []
            for arg in cmd:
                if isinstance(arg, str):
                    cmd_bytes.append(arg.encode('utf-8'))
                else:
                    cmd_bytes.append(arg)
            
            subprocess.run(cmd_bytes, check=True, env=env, timeout=1800)
        except subprocess.TimeoutExpired:
            print("❌ FFmpeg filter timed out after 1800s.")
            raise RuntimeError("FFmpeg filter timed out after 1800s.")
        except subprocess.CalledProcessError as e:
            print(f"❌ FFmpeg failed: {e}")
            raise e

if __name__ == "__main__":
    pass