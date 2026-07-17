import { chunkSemanticText, meanNormalizedVector, SEMANTIC_MODEL, SEMANTIC_MODEL_REVISION } from "./semantic.mjs";

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
        revision: SEMANTIC_MODEL_REVISION,
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

export async function embedSemanticDocuments(texts, onProgress = () => {}) {
  const groups = texts.map((text) => chunkSemanticText(text));
  if (groups.some((group) => !group.length)) throw new Error("Пустой текст нельзя преобразовать в смысловой вектор");
  const chunks = groups.flat();
  onProgress(`Подготовлено смысловых блоков: ${chunks.length}`);
  const chunkVectors = await embedSemanticTexts(chunks, onProgress);
  let offset = 0;
  const vectors = groups.map((group) => {
    const vector = meanNormalizedVector(chunkVectors.slice(offset, offset + group.length));
    offset += group.length;
    return vector;
  });
  return { vectors, chunkCounts: groups.map((group) => group.length) };
}
