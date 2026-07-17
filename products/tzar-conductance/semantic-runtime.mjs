import { SEMANTIC_MODEL } from "./semantic.mjs";

const TRANSFORMERS_URL = "https://cdn.jsdelivr.net/npm/@huggingface/transformers@4.0.1";
let extractorPromise;

function progressText(event) {
  if (event?.status === "progress" && Number.isFinite(event.progress)) {
    return `Загрузка модели · ${Math.round(event.progress)}%`;
  }
  if (event?.status === "ready") return "Модель готова";
  if (event?.file) return `Подготовка · ${event.file.split("/").pop()}`;
  return "Подготовка локальной модели…";
}

export async function loadSemanticExtractor(onProgress = () => {}) {
  if (!extractorPromise) {
    extractorPromise = (async () => {
      onProgress("Подключение смыслового ядра…");
      const { pipeline } = await import(TRANSFORMERS_URL);
      return pipeline("feature-extraction", SEMANTIC_MODEL, {
        dtype: "q8",
        progress_callback: (event) => onProgress(progressText(event)),
      });
    })().catch((error) => {
      extractorPromise = undefined;
      throw error;
    });
  }
  return extractorPromise;
}

export async function embedSemanticTexts(texts, onProgress = () => {}) {
  const extractor = await loadSemanticExtractor(onProgress);
  onProgress("Вычисление смысловых координат…");
  const output = await extractor(texts, { pooling: "mean", normalize: true });
  return output.tolist();
}
