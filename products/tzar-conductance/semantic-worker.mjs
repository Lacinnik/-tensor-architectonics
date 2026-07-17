import { embedSemanticDocuments } from "./semantic-runtime.mjs";

self.onmessage = async (event) => {
  if (event.data?.type !== "analyze") return;
  try {
    const result = await embedSemanticDocuments(event.data.texts, (message) => {
      self.postMessage({ type: "progress", message });
    });
    self.postMessage({ type: "result", ...result });
  } catch (error) {
    self.postMessage({ type: "error", message: error?.message || String(error) });
  }
};
