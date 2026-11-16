import fs from "node:fs";
import path from "node:path";
import { selectComposition, renderMedia } from "@remotion/renderer";
import { getBundleLocation } from "./bundle.js";
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
  };
}

/**
 * Executes a render in the background using either HyperFrames (default) or Remotion.
 * Switchable via RENDER_ENGINE environment variable ("hyperframes" | "remotion").
 */
export async function executeRender(params: RenderParams): Promise<void> {
  const engine = (process.env.RENDER_ENGINE || "hyperframes").toLowerCase();

  if (engine !== "remotion") {
    console.log(`[render-worker] Dispatching to HyperFrames engine for render ${params.renderId}`);
    return executeHyperFramesRender(params);
  }

  // --- Remotion Legacy Path ---
  const { renderId, jobId, clipIndex, props } = params;
  const job = renderJobs.get(renderId);

  if (!job) {
    console.error(`[render-worker] Job ${renderId} not found in map`);
    return;
  }

  try {
    job.status = "rendering";
    job.progress = 0;

    console.log(
      `[render-worker] Starting Remotion render ${renderId} (job=${jobId}, clip=${clipIndex})`
    );

    const bundleLocation = getBundleLocation();

    // Select the composition with the provided input props
    const composition = await selectComposition({
      serveUrl: bundleLocation,
      id: "ShortVideo",
      inputProps: props,
    });

    // Determine output directory and file path
    const outputDir = process.env.OUTPUT_DIR
      ? path.resolve(process.env.OUTPUT_DIR)
      : path.resolve(import.meta.dirname, "../../output");

    const jobOutputDir = path.join(outputDir, jobId);
    fs.mkdirSync(jobOutputDir, { recursive: true });

    const timestamp = Date.now();
    const outputFileName = `remotion_${clipIndex}_${timestamp}.mp4`;
    const outputLocation = path.join(jobOutputDir, outputFileName);

    console.log(`[render-worker] Output: ${outputLocation}`);

    // Render the video
    await renderMedia({
      composition,
      serveUrl: bundleLocation,
      codec: "h264",
      crf: 22,
      outputLocation,
      onProgress: ({ progress }) => {
        const percent = Math.round(progress * 100);
        job.progress = percent;

        if (percent % 10 === 0) {
          console.log(`[render-worker] ${renderId} progress: ${percent}%`);
        }
      },
    });

    // Success
    job.status = "done";
    job.progress = 100;
    job.outputUrl = outputLocation;

    console.log(`[render-worker] Render ${renderId} completed: ${outputLocation}`);
  } catch (err) {
    job.status = "error";
    job.error = err instanceof Error ? err.message : String(err);

    console.error(`[render-worker] Render ${renderId} failed:`, err);
  }
}
