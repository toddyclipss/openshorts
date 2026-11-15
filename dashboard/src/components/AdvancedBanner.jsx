import React from 'react';
import { Bot, ArrowRight } from 'lucide-react';

// Banner for advanced tools (AI Agent).
// Autonomous clipping team skill for Claude Code.
export default function AdvancedBanner({ needsPlan, onKeys }) {
  return (
    <div className="card mx-3 sm:mx-6 mt-3 px-3.5 sm:px-4 py-3 flex flex-col sm:flex-row sm:items-center justify-between gap-3 sm:gap-4 shrink-0 animate-fade">
      <div className="flex items-start sm:items-center gap-2.5 sm:gap-3 text-sm min-w-0">
        <Bot size={16} className="shrink-0 text-brass mt-0.5 sm:mt-0" />
        <div className="text-ink2 lowercase leading-relaxed min-w-0">
          <span className="font-medium text-ink">Advanced tool.</span>{' '}
          {needsPlan
            ? <>Sign in with <span className="font-medium text-ink">Google</span> to unlock free. Run your autonomous clipping team with the AI Agent skill.</>
            : <>Autonomous clipping and video analysis powered by the <span className="font-medium text-ink normal-case">AI Agent</span> skill for Claude Code.</>}
        </div>
      </div>
      <button
        onClick={needsPlan ? () => { window.location.hash = '#/pricing'; } : onKeys}
        className="btn-quiet shrink-0 text-xs px-3 py-1.5 w-full sm:w-auto"
      >
        {needsPlan ? <>See plans <ArrowRight size={14} /></> : 'Settings'}
      </button>
    </div>
  );
}
