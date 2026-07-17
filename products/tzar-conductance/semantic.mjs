export const SEMANTIC_MODEL = "Xenova/paraphrase-multilingual-MiniLM-L12-v2";
export const SEMANTIC_THRESHOLDS = Object.freeze({ preserved: 0.78, review: 0.6 });

export function normalizeSemanticText(value) {
  return String(value ?? "")
    .normalize("NFKC")
    .toLocaleLowerCase("ru")
    .replace(/[\s\u00a0]+/g, " ")
    .trim();
}

export function parseAnchors(value) {
  const source = Array.isArray(value) ? value : String(value ?? "").split("\n");
  return [...new Set(source.map(normalizeSemanticText).filter(Boolean))];
}

export function inspectAnchors(text, anchors) {
  const normalized = normalizeSemanticText(text);
  const required = parseAnchors(anchors);
  const present = required.filter((anchor) => normalized.includes(anchor));
  const missing = required.filter((anchor) => !normalized.includes(anchor));
  return {
    required,
    present,
    missing,
    coverage: required.length ? present.length / required.length : 1,
  };
}

export function cosineSimilarity(left, right) {
  if (!Array.isArray(left) || !Array.isArray(right) || left.length !== right.length || left.length === 0) {
    throw new Error("Векторы должны иметь одинаковую ненулевую длину");
  }
  let dot = 0;
  let leftNorm = 0;
  let rightNorm = 0;
  for (let index = 0; index < left.length; index += 1) {
    dot += left[index] * right[index];
    leftNorm += left[index] ** 2;
    rightNorm += right[index] ** 2;
  }
  if (leftNorm === 0 || rightNorm === 0) throw new Error("Нулевой вектор нельзя сравнить");
  return dot / (Math.sqrt(leftNorm) * Math.sqrt(rightNorm));
}

export function classifySemantic(similarity, anchorInspection, thresholds = SEMANTIC_THRESHOLDS) {
  if (!Number.isFinite(similarity) || similarity < -1 || similarity > 1) {
    throw new Error("Сходство должно находиться в диапазоне от −1 до 1");
  }
  if (anchorInspection.missing.length) {
    return {
      code: "critical-break",
      label: "КРИТИЧЕСКИЙ РАЗРЫВ",
      tone: "fail",
      explanation: "Утрачена хотя бы одна обязательная смысловая опора.",
    };
  }
  if (similarity >= thresholds.preserved) {
    return {
      code: "preserved",
      label: "СМЫСЛ СОХРАНЁН",
      tone: "pass",
      explanation: "Опоры сохранены, модельная близость находится в верхнем диапазоне.",
    };
  }
  if (similarity >= thresholds.review) {
    return {
      code: "review",
      label: "ТРЕБУЕТ РАЗЛИЧЕНИЯ",
      tone: "review",
      explanation: "Опоры сохранены, но преобразование заметно изменило смысловое окружение.",
    };
  }
  return {
    code: "rupture",
    label: "СМЫСЛОВОЙ РАЗРЫВ",
    tone: "fail",
    explanation: "Даже при сохранённых опорах модель обнаружила низкую смысловую близость.",
  };
}

export function buildSemanticItems(source, variants, vectors, anchors, thresholds = SEMANTIC_THRESHOLDS) {
  if (vectors.length !== variants.length + 1) throw new Error("Число эмбеддингов не соответствует числу текстов");
  return variants.map((variant, index) => {
    const similarity = cosineSimilarity(vectors[0], vectors[index + 1]);
    const anchorInspection = inspectAnchors(variant.text, anchors);
    return {
      label: variant.label || `Вариант ${index + 1}`,
      text: variant.text,
      similarity,
      anchors: anchorInspection,
      verdict: classifySemantic(similarity, anchorInspection, thresholds),
    };
  });
}

export function semanticReportMarkdown(report) {
  const rows = report.items.map((item) =>
    `| ${item.label} | ${(item.similarity * 100).toFixed(1)}% | ${(item.anchors.coverage * 100).toFixed(0)}% | ${item.verdict.label} |`,
  ).join("\n");
  return `# TZAR Semantic Conductance Report

- Product: \`${report.product}\`
- Mode: semantic beta
- Model: \`${report.model}\`
- Generated: ${report.generatedAt}
- Control seal: \`${report.seal}\`

## Source

${report.source}

## Critical anchors

${report.anchors.length ? report.anchors.map((anchor) => `- ${anchor}`).join("\n") : "Not specified"}

| Variant | Similarity | Anchor coverage | Verdict |
|---|---:|---:|---|
${rows}

Thresholds are operational calibration values, not a scientific proof. A model score is an aid to human distinction; critical anchors are strict user-defined constraints.
`;
}
