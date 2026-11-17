import fs from "node:fs";
import path from "node:path";
import { spawn } from "node:child_process";
import { renderJobs } from "./server.js";
import type { RenderParams } from "./render-worker.js";

/**
 * Executes a deterministic HyperFrames video render using headless Chrome and FFmpeg.
 * Consumes templates/short-video and dynamic JSON variables.
 */
export async function executeHyperFramesRender(params: RenderParams): Promise<void> {
  const { renderId, jobId, clipIndex, props } = params;
  const job = renderJobs.get(renderId);

  if (!job) {
    console.error(`[hyperframes-worker] Job ${renderId} not found in map`);
    return;
  }

  try {
    job.status = "rendering";
    job.progress = 0;

    console.log(
      `[hyperframes-worker] Starting HyperFrames render ${renderId} (job=${jobId}, clip=${clipIndex})`
    );

    // Determine output directory and file path
    const outputDir = process.env.OUTPUT_DIR
      ? path.resolve(process.env.OUTPUT_DIR)
      : path.resolve(import.meta.dirname, "../../output");

    const jobOutputDir = path.join(outputDir, jobId);
    fs.mkdirSync(jobOutputDir, { recursive: true });

    const timestamp = Date.now();
    const outputFileName = `hyperframes_${clipIndex}_${timestamp}.mp4`;
    const outputLocation = path.join(jobOutputDir, outputFileName);

    // Locate the unified short-video template
    const templateDir = process.env.TEMPLATES_DIR
      ? path.resolve(process.env.TEMPLATES_DIR, "short-video")
      : path.resolve(import.meta.dirname, "../../templates/short-video");

    // Write props payload to temporary file for --variables-file
    const propsFilePath = path.join(jobOutputDir, `props_${renderId}.json`);
    fs.writeFileSync(propsFilePath, JSON.stringify(props, null, 2), "utf-8");

    console.log(`[hyperframes-worker] Template: ${templateDir}`);
    console.log(`[hyperframes-worker] Output: ${outputLocation}`);

    const fps = props.fps || 30;

    // Execute hyperframes render CLI with Windows-safe path handling
    const safeTemplateDir = `"${templateDir}"`;
    const safeOutputLocation = `"${outputLocation}"`;
    const safePropsFilePath = `"${propsFilePath}"`;

    const args = [
      "hyperframes",
      "render",
      safeTemplateDir,
      "--output", safeOutputLocation,
      "--fps", String(fps),
      "--format", "mp4",
      "--variables-file", safePropsFilePath
    ];

    await new Promise<void>((resolve, reject) => {
      const child = spawn("npx", args, {
        shell: true,
        stdio: ["ignore", "pipe", "pipe"],
      });

      child.stdout.on("data", (chunk: Buffer) => {
        const text = chunk.toString();
        // Parse progress if emitted (e.g. "Progress: 45%" or frame indicators)
        const match = text.match(/(\d+)%/);
        if (match) {
          const percent = parseInt(match[1], 10);
          job.progress = percent;
          if (percent % 10 === 0) {
            console.log(`[hyperframes-worker] ${renderId} progress: ${percent}%`);
          }
        }
      });

      child.stderr.on("data", (chunk: Buffer) => {
        const text = chunk.toString();
        if (text.includes("error") || text.includes("Error")) {
          console.error(`[hyperframes-worker stderr] ${text.trim()}`);
        }
      });

      child.on("close", (code) => {
        try { fs.unlinkSync(propsFilePath); } catch {}
        if (code === 0) {
          resolve();
        } else {
          reject(new Error(`HyperFrames process exited with code ${code}`));
        }
      });

      child.on("error", (err) => {
        try { fs.unlinkSync(propsFilePath); } catch {}
        reject(err);
      });
    });

    job.status = "done";
    job.progress = 100;
    // Return relative /videos/ URL so browser client can download directly via FastAPI
    job.outputUrl = `/videos/${jobId}/${outputFileName}`;
    console.log(`[hyperframes-worker] Render ${renderId} successfully completed: ${job.outputUrl} (${outputLocation})`);
  } catch (err) {
    job.status = "error";
    job.error = err instanceof Error ? err.message : String(err);
    console.error(`[hyperframes-worker] Render ${renderId} failed:`, err);
  }
}
