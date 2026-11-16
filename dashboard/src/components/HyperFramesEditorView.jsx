import React, { useState, useEffect, useRef, useMemo, useCallback } from 'react';
import {
    X, Play, Pause, RotateCcw, Sparkles, Download, Check,
    Sliders, Type, Film, Flame, Loader2, ArrowLeft, Eye
} from 'lucide-react';
import { apiFetch } from '../lib/api';

/**
 * HyperFramesEditorView
 * Full-screen / integrated editing studio for viral shorts using HyperFrames.
 * Allows interactive preview with word-level subtitles, dynamic hook headlines,
 * and punch-in zooms, with 1-click re-prompting via Gemini and export via HyperFrames.
 */
export default function HyperFramesEditorView({
    clip,
    index,
    jobId,
    initialProps,
    onClose,
    onSave,
    isManaged,
    geminiApiKey,
}) {
    const [props, setProps] = useState(initialProps || {
        videoUrl: clip?.video_url || '',
        durationInFrames: Math.round((clip?.end - clip?.start || 30) * 30),
        fps: 30,
        width: 1080,
        height: 1920,
        hook: {
            text: clip?.viral_hook_text || clip?.video_title_for_youtube_short || 'VIRAL MOMENT',
            position: 'top',
            size: 'M',
            style: 'pill',
            entranceAnimation: 'spring',
            displayDurationSec: 3.5,
        },
        subtitles: {
            captions: [],
            position: 'bottom',
            style: {
                fontFamily: 'Montserrat',
                fontSize: 68,
                fontColor: '#FFFFFF',
                highlightColor: '#FFE600',
                borderColor: '#000000',
                borderWidth: 6,
                bgColor: '#000000',
                bgOpacity: 0.0,
                animation: 'karaoke',
                baseOpacity: 0.4,
                uppercase: true,
                reveal: true,
                shadow: 6,
            },
        },
        effects: {
            segments: [
                { startSec: 0, endSec: 3.5, zoom: 1.15, zoomCenterX: 0.5, zoomCenterY: 0.4, brightness: 1.05, contrast: 1.1, saturate: 1.15 },
                { startSec: 3.5, endSec: 7.0, zoom: 1.0, zoomCenterX: 0.5, zoomCenterY: 0.4, brightness: 1.0, contrast: 1.0, saturate: 1.0 },
            ],
        },
    });

    const [activeTab, setActiveTab] = useState('hook'); // 'hook' | 'subtitles' | 'effects'
    const [isPlaying, setIsPlaying] = useState(false);
    const [currentTime, setCurrentTime] = useState(0);
    const [duration, setDuration] = useState(clip?.end - clip?.start || 30);
    const [isGenerating, setIsGenerating] = useState(false);
    const [isRendering, setIsRendering] = useState(false);
    const [renderProgress, setRenderProgress] = useState(0);
    const [renderedUrl, setRenderedUrl] = useState(null);
    const [renderError, setRenderError] = useState(null);

    const videoRef = useRef(null);

    // Keep props in sync when initialProps updates (e.g. background Gemini auto-edit resolves)
    useEffect(() => {
        if (initialProps) {
            setProps(initialProps);
        }
    }, [initialProps]);

    // Pristine clean video URL (strips burned subtitle, hook, or watermark prefixes)
    const cleanVideoUrl = useMemo(() => {
        const raw = props.videoUrl || clip?.video_url || '';
        if (!raw) return '';
        let f = raw.split('/').pop() || '';
        const cleaned = f.replace(/^(?:(?:subtitled|hooked|recut)_\d+_|edited_|hook_|wm_)+/, '');
        return raw.replace(/[^/]+$/, cleaned);
    }, [props.videoUrl, clip?.video_url]);

    // Fetch word-level captions if not present
    useEffect(() => {
        if ((!props.subtitles?.captions || props.subtitles.captions.length === 0) && jobId && index !== undefined) {
            apiFetch(`/api/clip/${jobId}/${index}/transcript`)
                .then(res => res.ok ? res.json() : null)
                .then(data => {
                    if (data?.captions) {
                        setProps(prev => ({
                            ...prev,
                            subtitles: {
                                ...prev.subtitles,
                                captions: data.captions,
                            },
                        }));
                    }
                })
                .catch(err => console.warn('Could not load transcript for HyperFrames editor:', err));
        }
    }, [jobId, index]);

    // Handle time update for real-time overlay synchronization
    const handleTimeUpdate = () => {
        if (videoRef.current) {
            setCurrentTime(videoRef.current.currentTime);
        }
    };

    const handleLoadedMetadata = () => {
        if (videoRef.current) {
            setDuration(videoRef.current.duration || 30);
        }
    };

    const togglePlay = () => {
        if (!videoRef.current) return;
        if (isPlaying) {
            videoRef.current.pause();
            setIsPlaying(false);
        } else {
            videoRef.current.play();
            setIsPlaying(true);
        }
    };

    const handleSeek = (e) => {
        const time = parseFloat(e.target.value);
        setCurrentTime(time);
        if (videoRef.current) {
            videoRef.current.currentTime = time;
        }
    };

    // Calculate active zoom and filter based on effects segments
    const currentEffect = useMemo(() => {
        const segments = props.effects?.segments || [];
        const activeSeg = segments.find(s => currentTime >= s.startSec && currentTime <= s.endSec);
        if (activeSeg) {
            return {
                scale: activeSeg.zoom || 1.0,
                origin: `${(activeSeg.zoomCenterX ?? 0.5) * 100}% ${(activeSeg.zoomCenterY ?? 0.4) * 100}%`,
                filter: `brightness(${activeSeg.brightness ?? 1}) contrast(${activeSeg.contrast ?? 1}) saturate(${activeSeg.saturate ?? 1})`,
            };
        }
        return { scale: 1.0, origin: '50% 40%', filter: 'none' };
    }, [props.effects, currentTime]);

    // Calculate active subtitle word and current block
    const activeWordInfo = useMemo(() => {
        const captions = props.subtitles?.captions || [];
        const currentMs = currentTime * 1000;
        const currentWord = captions.find(w => currentMs >= w.startMs && currentMs <= w.endMs);
        
        // Find visible caption window (current word +/- 3 surrounding words)
        if (!currentWord) {
            // Find closest upcoming word
            const nextWordIdx = captions.findIndex(w => w.startMs > currentMs);
            if (nextWordIdx >= 0) {
                const start = Math.max(0, nextWordIdx - 2);
                return { activeWord: null, words: captions.slice(start, start + 5) };
            }
            return { activeWord: null, words: [] };
        }

        const idx = captions.indexOf(currentWord);
        const start = Math.max(0, idx - 2);
        return {
            activeWord: currentWord,
            words: captions.slice(start, start + 5),
        };
    }, [props.subtitles, currentTime]);

    // Whether hook banner is currently active
    const isHookActive = useMemo(() => {
        if (!props.hook?.text) return false;
        return currentTime <= (props.hook.displayDurationSec || 3.5);
    }, [props.hook, currentTime]);

    // AI Re-generation via Gemini
    const handleReGenerateAI = async () => {
        setIsGenerating(true);
        setRenderError(null);
        try {
            const apiKey = geminiApiKey || localStorage.getItem('gemini_key');
            const headers = { 'Content-Type': 'application/json' };
            if (apiKey) headers['X-Gemini-Key'] = apiKey;

            const res = await apiFetch('/api/hyperframes/auto-edit', {
                method: 'POST',
                headers,
                body: JSON.stringify({
                    job_id: jobId,
                    clip_index: index,
                }),
            });

            if (!res.ok) {
                const errData = await res.json().catch(() => ({}));
                throw new Error(errData.detail || 'Failed to auto-edit with Gemini');
            }

            const data = await res.json();
            if (data?.props) {
                setProps(data.props);
                if (onSave) onSave(data.props);
            }
        } catch (err) {
            setRenderError(err.message);
        } finally {
            setIsGenerating(false);
        }
    };

    // Trigger Final MP4 Render via HyperFrames render-service
    const handleTriggerRender = async () => {
        setIsRendering(true);
        setRenderProgress(0);
        setRenderError(null);
        try {
            const res = await apiFetch('/api/render', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    jobId,
                    clipIndex: index,
                    props: {
                        ...props,
                        videoUrl: cleanVideoUrl || clip?.video_url || props.videoUrl,
                    },
                }),
            });

            if (!res.ok) {
                const errData = await res.json().catch(() => ({}));
                throw new Error(errData.detail || 'Render submission failed');
            }

            const { renderId } = await res.json();

            // Poll render status
            const pollInterval = setInterval(async () => {
                try {
                    const statusRes = await apiFetch(`/api/render/${renderId}`);
                    if (!statusRes.ok) return;
                    const statusData = await statusRes.json();

                    if (statusData.progress !== undefined) {
                        setRenderProgress(statusData.progress);
                    }

                    if (statusData.status === 'done') {
                        clearInterval(pollInterval);
                        setIsRendering(false);
                        setRenderedUrl(statusData.outputUrl);
                    } else if (statusData.status === 'error') {
                        clearInterval(pollInterval);
                        setIsRendering(false);
                        setRenderError(statusData.error || 'HyperFrames render failed');
                    }
                } catch (e) {
                    clearInterval(pollInterval);
                    setIsRendering(false);
                    setRenderError(e.message);
                }
            }, 1000);
        } catch (err) {
            setIsRendering(false);
            setRenderError(err.message);
        }
    };

    return (
        <div className="fixed inset-0 z-50 bg-black/90 backdrop-blur-md flex flex-col text-ink select-none overflow-hidden">
            {/* Top Navigation Bar */}
            <div className="h-14 border-b border-white/10 px-4 sm:px-6 flex items-center justify-between bg-paper/60 shrink-0">
                <div className="flex items-center gap-3">
                    <button
                        onClick={onClose}
                        className="p-1.5 rounded-lg hover:bg-white/10 text-muted hover:text-ink transition-colors"
                        title="Back to Clips"
                    >
                        <ArrowLeft size={18} />
                    </button>
                    <div className="flex items-center gap-2">
                        <span className="font-semibold text-sm">HyperFrames Director</span>
                        {clip?.predicted_score !== undefined && (
                            <span className="badge badge-ok flex items-center gap-1 text-xs px-2 py-0.5">
                                <Flame size={12} className="text-orange-400" />
                                Viral {clip.predicted_score}/100
                            </span>
                        )}
                    </div>
                </div>

                <div className="flex items-center gap-2">
                    <button
                        onClick={handleReGenerateAI}
                        disabled={isGenerating || isRendering}
                        className="btn btn-secondary text-xs flex items-center gap-1.5 py-1.5 px-3"
                    >
                        {isGenerating ? <Loader2 size={14} className="animate-spin" /> : <Sparkles size={14} className="text-brass" />}
                        {isGenerating ? 'AI Directing...' : 'AI Re-Direct'}
                    </button>
                    <button
                        onClick={handleTriggerRender}
                        disabled={isRendering || isGenerating}
                        className="btn btn-primary text-xs flex items-center gap-1.5 py-1.5 px-3 bg-brass text-black font-semibold hover:brightness-110"
                    >
                        {isRendering ? <Loader2 size={14} className="animate-spin" /> : <Film size={14} />}
                        {isRendering ? `Rendering ${renderProgress}%` : 'Export with HyperFrames'}
                    </button>
                    <button
                        onClick={onClose}
                        className="p-1.5 rounded-lg hover:bg-white/10 text-muted hover:text-ink"
                    >
                        <X size={18} />
                    </button>
                </div>
            </div>

            {/* Main Stage: Left Viewport (9:16 Preview) + Right Inspector */}
            <div className="flex-1 flex flex-col md:flex-row min-h-0 overflow-hidden">
                {/* Video Preview Center Stage */}
                <div className="flex-1 flex flex-col items-center justify-center p-4 bg-black/60 relative">
                    <div className="relative aspect-[9/16] h-full max-h-[75vh] md:max-h-[82vh] rounded-2xl overflow-hidden shadow-2xl border border-white/10 bg-black">
                        {/* Video Layer */}
                        <div
                            className="w-full h-full transition-transform duration-300 ease-out"
                            style={{
                                transform: `scale(${currentEffect.scale})`,
                                transformOrigin: currentEffect.origin,
                                filter: currentEffect.filter,
                            }}
                        >
                            <video
                                ref={videoRef}
                                src={cleanVideoUrl || clip?.video_url}
                                className="w-full h-full object-cover"
                                playsInline
                                onTimeUpdate={handleTimeUpdate}
                                onLoadedMetadata={handleLoadedMetadata}
                                onEnded={() => setIsPlaying(false)}
                            />
                        </div>

                        {/* Hook Overlay Layer */}
                        {isHookActive && props.hook?.text && (
                            <div className="absolute top-10 left-0 right-0 flex justify-center px-4 pointer-events-none transition-all duration-300">
                                <div className={`
                                    px-4 py-2 rounded-full font-black tracking-wide text-center uppercase shadow-xl
                                    ${props.hook.style === 'yellow' ? 'bg-[#FFDD00] text-black' :
                                      props.hook.style === 'dark' ? 'bg-[#121214] text-white border border-white/20' :
                                      props.hook.style === 'neon_glow' ? 'bg-black text-[#00FF66] border border-[#00FF66] shadow-[0_0_15px_#00FF66]' :
                                      'bg-white/95 text-black border border-black/10'}
                                    ${props.hook.size === 'L' ? 'text-lg sm:text-xl' : props.hook.size === 'S' ? 'text-xs sm:text-sm' : 'text-sm sm:text-base'}
                                `}>
                                    {props.hook.text}
                                </div>
                            </div>
                        )}

                        {/* Animated Subtitles Layer */}
                        <div className="absolute bottom-16 left-0 right-0 flex justify-center px-6 pointer-events-none">
                            <div className="flex flex-wrap justify-center gap-1.5 text-center max-w-[90%]">
                                {activeWordInfo.words.map((w, idx) => {
                                    const isCurrent = activeWordInfo.activeWord?.text === w.text;
                                    return (
                                        <span
                                            key={idx}
                                            className="font-black uppercase tracking-tight transition-all duration-150"
                                            style={{
                                                fontSize: `${(props.subtitles?.style?.fontSize || 68) * 0.35}px`,
                                                color: isCurrent ? (props.subtitles?.style?.highlightColor || '#FFE600') : '#FFFFFF',
                                                opacity: isCurrent ? 1.0 : (props.subtitles?.style?.baseOpacity || 0.45),
                                                transform: isCurrent ? 'scale(1.2)' : 'scale(1.0)',
                                                textShadow: '0 2px 8px rgba(0,0,0,0.9), -1px -1px 0 #000, 1px -1px 0 #000, -1px 1px 0 #000, 1px 1px 0 #000',
                                            }}
                                        >
                                            {w.text}
                                        </span>
                                    );
                                })}
                            </div>
                        </div>

                        {/* Center Play/Pause Overlay Icon on Hover */}
                        <button
                            onClick={togglePlay}
                            className="absolute inset-0 flex items-center justify-center bg-black/20 opacity-0 hover:opacity-100 transition-opacity"
                        >
                            <div className="p-4 rounded-full bg-black/60 text-white backdrop-blur-sm">
                                {isPlaying ? <Pause size={28} /> : <Play size={28} className="translate-x-0.5" />}
                            </div>
                        </button>
                    </div>

                    {/* Timeline Playback Bar */}
                    <div className="w-full max-w-[420px] mt-3 flex items-center gap-3 px-2">
                        <button
                            onClick={togglePlay}
                            className="p-2 rounded-lg bg-white/10 hover:bg-white/20 text-white transition-colors"
                        >
                            {isPlaying ? <Pause size={16} /> : <Play size={16} />}
                        </button>
                        <span className="text-xs font-mono text-muted w-10">
                            {currentTime.toFixed(1)}s
                        </span>
                        <input
                            type="range"
                            min="0"
                            max={duration}
                            step="0.05"
                            value={currentTime}
                            onChange={handleSeek}
                            className="flex-1 accent-brass h-1.5 bg-white/20 rounded-lg cursor-pointer"
                        />
                        <span className="text-xs font-mono text-muted w-10 text-right">
                            {duration.toFixed(1)}s
                        </span>
                    </div>
                </div>

                {/* Right Inspector & Controls Column */}
                <div className="w-full md:w-80 lg:w-96 border-t md:border-t-0 md:border-l border-white/10 bg-paper flex flex-col shrink-0">
                    {/* Tabs Header */}
                    <div className="flex border-b border-white/10 bg-paper2/50 text-xs">
                        <button
                            onClick={() => setActiveTab('hook')}
                            className={`flex-1 py-3 px-2 flex items-center justify-center gap-1.5 font-medium border-b-2 transition-colors ${activeTab === 'hook' ? 'border-brass text-brass' : 'border-transparent text-muted hover:text-ink'}`}
                        >
                            <Flame size={14} /> Viral Hook
                        </button>
                        <button
                            onClick={() => setActiveTab('subtitles')}
                            className={`flex-1 py-3 px-2 flex items-center justify-center gap-1.5 font-medium border-b-2 transition-colors ${activeTab === 'subtitles' ? 'border-brass text-brass' : 'border-transparent text-muted hover:text-ink'}`}
                        >
                            <Type size={14} /> Subtitles
                        </button>
                        <button
                            onClick={() => setActiveTab('effects')}
                            className={`flex-1 py-3 px-2 flex items-center justify-center gap-1.5 font-medium border-b-2 transition-colors ${activeTab === 'effects' ? 'border-brass text-brass' : 'border-transparent text-muted hover:text-ink'}`}
                        >
                            <Sliders size={14} /> Zooms
                        </button>
                    </div>

                    {/* Tab Panes */}
                    <div className="flex-1 overflow-y-auto p-4 space-y-5 custom-scrollbar text-xs">
                        {activeTab === 'hook' && (
                            <div className="space-y-4">
                                <div>
                                    <label className="block text-muted mb-1.5 font-semibold">Headline Text</label>
                                    <textarea
                                        value={props.hook?.text || ''}
                                        onChange={(e) => setProps(p => ({ ...p, hook: { ...p.hook, text: e.target.value } }))}
                                        rows={2}
                                        className="w-full rounded-lg bg-paper3 border border-white/10 p-2.5 text-xs text-ink focus:border-brass outline-none uppercase font-bold"
                                        placeholder="VIRAL HEADLINE HOOK"
                                    />
                                </div>

                                <div>
                                    <label className="block text-muted mb-1.5 font-semibold">Visual Style</label>
                                    <div className="grid grid-cols-2 gap-2">
                                        {['pill', 'yellow', 'dark', 'neon_glow', 'classic'].map((style) => (
                                            <button
                                                key={style}
                                                onClick={() => setProps(p => ({ ...p, hook: { ...p.hook, style } }))}
                                                className={`p-2 rounded-lg border text-center font-semibold capitalize transition-all ${props.hook?.style === style ? 'border-brass bg-brass/10 text-brass' : 'border-white/10 hover:border-white/20'}`}
                                            >
                                                {style.replace('_', ' ')}
                                            </button>
                                        ))}
                                    </div>
                                </div>

                                <div>
                                    <label className="block text-muted mb-1.5 font-semibold">Display Duration: {props.hook?.displayDurationSec || 3.5}s</label>
                                    <input
                                        type="range"
                                        min="2"
                                        max="6"
                                        step="0.5"
                                        value={props.hook?.displayDurationSec || 3.5}
                                        onChange={(e) => setProps(p => ({ ...p, hook: { ...p.hook, displayDurationSec: parseFloat(e.target.value) } }))}
                                        className="w-full accent-brass"
                                    />
                                </div>
                            </div>
                        )}

                        {activeTab === 'subtitles' && (
                            <div className="space-y-4">
                                <div>
                                    <label className="block text-muted mb-1.5 font-semibold">Highlight Color</label>
                                    <div className="flex gap-2">
                                        {[
                                            { name: 'Yellow', hex: '#FFE600' },
                                            { name: 'Green', hex: '#00FF66' },
                                            { name: 'Cyan', hex: '#00F0FF' },
                                            { name: 'Pink', hex: '#FF0055' },
                                        ].map(c => (
                                            <button
                                                key={c.hex}
                                                onClick={() => setProps(p => ({ ...p, subtitles: { ...p.subtitles, style: { ...p.subtitles.style, highlightColor: c.hex } } }))}
                                                className={`w-8 h-8 rounded-full border-2 transition-transform ${props.subtitles?.style?.highlightColor === c.hex ? 'scale-110 border-white' : 'border-transparent'}`}
                                                style={{ backgroundColor: c.hex }}
                                                title={c.name}
                                            />
                                        ))}
                                    </div>
                                </div>

                                <div>
                                    <label className="block text-muted mb-1.5 font-semibold">Animation Style</label>
                                    <div className="grid grid-cols-2 gap-2">
                                        {['karaoke', 'pop', 'word-highlight'].map((anim) => (
                                            <button
                                                key={anim}
                                                onClick={() => setProps(p => ({ ...p, subtitles: { ...p.subtitles, style: { ...p.subtitles.style, animation: anim } } }))}
                                                className={`p-2 rounded-lg border text-center font-semibold capitalize transition-all ${props.subtitles?.style?.animation === anim ? 'border-brass bg-brass/10 text-brass' : 'border-white/10 hover:border-white/20'}`}
                                            >
                                                {anim}
                                            </button>
                                        ))}
                                    </div>
                                </div>

                                <div className="flex items-center justify-between">
                                    <span className="text-muted font-semibold">Uppercase Only</span>
                                    <input
                                        type="checkbox"
                                        checked={props.subtitles?.style?.uppercase ?? true}
                                        onChange={(e) => setProps(p => ({ ...p, subtitles: { ...p.subtitles, style: { ...p.subtitles.style, uppercase: e.target.checked } } }))}
                                        className="accent-brass w-4 h-4"
                                    />
                                </div>
                            </div>
                        )}

                        {activeTab === 'effects' && (
                            <div className="space-y-3">
                                <div className="flex justify-between items-center">
                                    <label className="text-muted font-semibold">Punch-in Zooms</label>
                                    <span className="text-muted text-[11px]">{props.effects?.segments?.length || 0} cuts</span>
                                </div>
                                <div className="space-y-2">
                                    {(props.effects?.segments || []).map((seg, i) => (
                                        <div key={i} className="p-2.5 rounded-lg bg-paper3 border border-white/5 space-y-1.5">
                                            <div className="flex justify-between font-mono text-muted">
                                                <span>{seg.startSec.toFixed(1)}s - {seg.endSec.toFixed(1)}s</span>
                                                <span className="text-brass font-bold">{seg.zoom}x zoom</span>
                                            </div>
                                            <input
                                                type="range"
                                                min="1.0"
                                                max="1.4"
                                                step="0.05"
                                                value={seg.zoom}
                                                onChange={(e) => {
                                                    const val = parseFloat(e.target.value);
                                                    setProps(p => {
                                                        const segs = [...(p.effects?.segments || [])];
                                                        segs[i] = { ...segs[i], zoom: val };
                                                        return { ...p, effects: { ...p.effects, segments: segs } };
                                                    });
                                                }}
                                                className="w-full accent-brass"
                                            />
                                        </div>
                                    ))}
                                </div>
                            </div>
                        )}

                        {renderError && (
                            <div className="p-3 rounded-lg bg-danger/10 border border-danger/30 text-danger text-xs">
                                {renderError}
                            </div>
                        )}

                        {renderedUrl && (
                            <div className="p-3 rounded-lg bg-ok/10 border border-ok/30 text-ok text-xs space-y-2">
                                <div className="flex items-center gap-1.5 font-semibold">
                                    <Check size={14} /> Render Finished!
                                </div>
                                <a
                                    href={renderedUrl}
                                    download
                                    className="btn btn-primary w-full py-1.5 text-xs flex items-center justify-center gap-1.5"
                                >
                                    <Download size={14} /> Download MP4
                                </a>
                            </div>
                        )}
                    </div>
                </div>
            </div>
        </div>
    );
}
