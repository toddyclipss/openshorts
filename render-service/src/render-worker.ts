import { renderJobs } from "./server.js";
import { executeHyperFramesRender } from "./hyperframes-worker.js";

export interface RenderParams {
  renderId: string;
  jobId: string;
  clipIndex: number;
  props: {
    videoUrl: string;
    durationInFrames: number;
    fps: number;
    width: number;
    height: number;
    subtitles: unknown;
    hook: unknown;
    effects: unknown;
    sfxTrack?: unknown;
    stickers?: unknown;
    retentionBar?: unknown;
    keywordHighlights?: unknown;
    treatment?: unknown;
  };
}

/**
 * Executes video rendering exclusively using the HyperFrames engine (Apache 2.0).
 * Remotion has been completely replaced.
 */
export async function executeRender(params: RenderParams): Promise<void> {
  console.log(`[render-worker] Dispatching to HyperFrames engine for render ${params.renderId}`);
  return executeHyperFramesRender(params);
}
