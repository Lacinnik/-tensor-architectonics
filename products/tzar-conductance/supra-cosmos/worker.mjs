import { analyzeRgba } from "./core.mjs";

self.addEventListener("message", event => {
  const { id, image } = event.data || {};
  try {
    const analysis = analyzeRgba(image);
    self.postMessage({ id, ok: true, analysis });
  } catch (error) {
    self.postMessage({ id, ok: false, error: error instanceof Error ? error.message : String(error) });
  }
});
