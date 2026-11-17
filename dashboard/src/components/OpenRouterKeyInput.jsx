import React, { useState, useEffect } from 'react';
import { Key, Eye, EyeOff, Check, Sparkles, ExternalLink } from 'lucide-react';

export default function OpenRouterKeyInput({
    openrouterKey,
    onKeySet,
    openrouterModel,
    onModelSet,
    compact = false
}) {
    const [key, setKey] = useState(openrouterKey || '');
    const [model, setModel] = useState(openrouterModel || '');
    const [isVisible, setIsVisible] = useState(false);
    const [isSaved, setIsSaved] = useState(!!openrouterKey);

    useEffect(() => {
        setKey(openrouterKey || '');
        setIsSaved(!!openrouterKey);
    }, [openrouterKey]);

    useEffect(() => {
        setModel(openrouterModel || '');
    }, [openrouterModel]);

    const handleSave = () => {
        onKeySet(key.trim());
        onModelSet(model.trim());
        setIsSaved(true);
    };

    return (
        <div className={`card ${compact ? 'p-3.5 sm:p-4 mb-4' : 'p-4 sm:p-6 mb-6'} animate-fade border border-rule`}>
            <div className="flex items-center justify-between gap-3 mb-3">
                <div className="flex items-center gap-2.5">
                    <div className="p-1.5 sm:p-2 bg-paper3 rounded-input text-brass">
                        <Sparkles size={16} />
                    </div>
                    <div>
                        <h2 className="font-display lowercase text-sm sm:text-base text-ink flex items-center gap-2">
                            OpenRouter AI Director
                            {isSaved && key && (
                                <span className="badge-ok text-[10px] py-0.5 px-2">Ready</span>
                            )}
                        </h2>
                        <p className="text-[11px] text-muted leading-tight">
                            Directs camera zooms, kinetic typography, and sound effects via OpenRouter.
                        </p>
                    </div>
                </div>
            </div>

            <div className="space-y-3">
                {/* API Key Field */}
                <div>
                    <label className="block text-[11px] font-mono uppercase text-muted mb-1">
                        OpenRouter API Key
                    </label>
                    <div className="relative">
                        <input
                            type={isVisible ? "text" : "password"}
                            value={key}
                            onChange={(e) => {
                                setKey(e.target.value);
                                setIsSaved(false);
                            }}
                            placeholder="sk-or-v1-..."
                            className="input-field pr-10 font-mono text-xs"
                        />
                        <button
                            type="button"
                            onClick={() => setIsVisible(!isVisible)}
                            className="absolute right-3 top-1/2 -translate-y-1/2 text-muted hover:text-ink transition-colors"
                            aria-label={isVisible ? "Hide API key" : "Show API key"}
                        >
                            {isVisible ? <EyeOff size={15} /> : <Eye size={15} />}
                        </button>
                    </div>
                </div>

                {/* Model Slug Field (Free Text, No Hardcoded Model) */}
                <div>
                    <div className="flex items-center justify-between mb-1">
                        <label className="block text-[11px] font-mono uppercase text-muted">
                            Model Slug (Free text)
                        </label>
                        <a
                            href="https://openrouter.ai/models"
                            target="_blank"
                            rel="noopener noreferrer"
                            className="text-[11px] text-brass hover:underline flex items-center gap-1"
                        >
                            Browse models <ExternalLink size={10} />
                        </a>
                    </div>
                    <input
                        type="text"
                        value={model}
                        onChange={(e) => {
                            setModel(e.target.value);
                            setIsSaved(false);
                        }}
                        placeholder="e.g. google/gemini-2.5-flash, anthropic/claude-3.5-sonnet, deepseek/deepseek-chat..."
                        className="input-field font-mono text-xs"
                    />
                    <p className="mt-1 text-[10px] text-muted">
                        No model is hardcoded. Enter any valid OpenRouter model slug of your choice.
                    </p>
                </div>

                {/* Save button and Links */}
                <div className="flex flex-col sm:flex-row items-start sm:items-center justify-between gap-2 pt-1 border-t border-rule">
                    <a
                        href="https://openrouter.ai/keys"
                        target="_blank"
                        rel="noopener noreferrer"
                        className="text-[11px] text-brass hover:underline inline-flex items-center gap-1"
                    >
                        Get your OpenRouter Key <ExternalLink size={10} />
                    </a>
                    <button
                        type="button"
                        onClick={handleSave}
                        disabled={!key.trim() && !model.trim()}
                        className={isSaved ? 'badge-ok px-3 py-1.5 cursor-default text-xs flex items-center gap-1' : 'btn-primary py-1.5 px-3 text-xs'}
                    >
                        {isSaved ? <><Check size={13} /> Saved</> : 'Save Settings'}
                    </button>
                </div>
            </div>
        </div>
    );
}
