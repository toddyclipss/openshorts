import path from "node:path";
import { bundle } from "@remotion/bundler";

let bundleLocation: string | null = null;

/**
 * Bundles the Remotion project on startup and caches the result.
 * Skipped if RENDER_ENGINE is "hyperframes" (or not "remotion").
 */
export async function initBundle(): Promise<void> {
  const engine = (process.env.RENDER_ENGINE || "hyperframes").toLowerCase();
  if (engine !== "remotion") {
    console.log(`[bundle] Skipping Remotion bundling on boot (RENDER_ENGINE=${engine})`);
    return;
  }

  const remotionRoot = process.env.REMOTION_BUNDLE_PATH
    ? path.resolve(process.env.REMOTION_BUNDLE_PATH)
    : path.resolve(import.meta.dirname, "../../remotion");

  const entryPoint = path.join(remotionRoot, "src", "index.ts");

  console.log(`[bundle] Bundling Remotion project from: ${entryPoint}`);

  bundleLocation = await bundle({
    entryPoint,
    onProgress: (progress: number) => {
      if (progress % 10 === 0) {
        console.log(`[bundle] Progress: ${progress}%`);
      }
    },
  });

  console.log(`[bundle] Bundle created at: ${bundleLocation}`);
}

/**
 * Returns the cached bundle location.
 * Throws if initBundle() has not been called yet.
 */
export function getBundleLocation(): string {
  if (!bundleLocation) {
    throw new Error(
      "Bundle not initialized. Call initBundle() before getBundleLocation()."
    );
  }
  return bundleLocation;
}
