export const SEMANTIC_MODEL = "Xenova/paraphrase-multilingual-MiniLM-L12-v2";
export const SEMANTIC_MODEL_REVISION = "2c4055b12046f11709e9df2c122e59ffbdc2f900";
export const SEMANTIC_THRESHOLDS = Object.freeze({ preserved: 0.78, review: 0.6 });

const STOP_WORDS = new Set("это как при для или что чем над под его её их она они оно этот эта эти быть был была были через между после перед уже ещё где когда который которая которые такой такая также только очень одной один без из от до по на в во и а но с со у к ко о об не ни ли же".split(" "));
const LOGIC_GROUPS = [
  { code: "negation", label: "Изменение отрицания", pattern: /(?<!\p{L})(?:не|ни|нет|без|невозмож\p{L}*|отсутств\p{L}*)(?!\p{L})/giu, severity: "critical" },
  { code: "possibility", label: "Изменение возможности или гипотезы", pattern: /(?<!\p{L})(?:может|могут|возможно|вероятно|предполож\p{L}*|гипотез\p{L}*)(?!\p{L})/giu, severity: "warning" },
  { code: "necessity", label: "Изменение необходимости", pattern: /(?<!\p{L})(?:долж\p{L}*|необходим\p{L}*|обязательн\p{L}*)(?!\p{L})/giu, severity: "warning" },
  { code: "proof-status", label: "Изменение статуса доказанности", pattern: /(?<!\p{L})(?:доказ\p{L}*|истин\p{L}*|установлен\p{L}*|подтвержд\p{L}*|канонич\p{L}*|факт\p{L}*)(?!\p{L})/giu, severity: "critical" },
  { code: "observation", label: "Изменение статуса наблюдения", pattern: /(?<!\p{L})(?:наблюда\p{L}*|измер\p{L}*|эксперимент\p{L}*)(?!\p{L})/giu, severity: "warning" },
];

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

function markerCount(text, pattern) {
  return normalizeSemanticText(text).match(pattern)?.length ?? 0;
}

export function detectLogicRisks(source, variant) {
  return LOGIC_GROUPS.flatMap((group) => {
    const before = markerCount(source, group.pattern);
    const after = markerCount(variant, group.pattern);
    return before === after ? [] : [{
      code: group.code,
      label: group.label,
      severity: group.severity,
      before,
      after,
      explanation: `${before} → ${after} маркеров`,
    }];
  });
}

function contentTokens(text) {
  return [...new Set((normalizeSemanticText(text).match(/[\p{L}\p{N}-]+/gu) ?? [])
    .filter((token) => token.length > 2 && !STOP_WORDS.has(token)))];
}

export function lexicalDifference(source, variant, limit = 8) {
  const before = contentTokens(source);
  const after = contentTokens(variant);
  const beforeSet = new Set(before);
  const afterSet = new Set(after);
  return {
    removed: before.filter((token) => !afterSet.has(token)).slice(0, limit),
    added: after.filter((token) => !beforeSet.has(token)).slice(0, limit),
  };
}

export function chunkSemanticText(text, maxCharacters = 900) {
  const normalized = String(text ?? "").replace(/[\s\u00a0]+/g, " ").trim();
  if (!normalized) return [];
  const sentences = normalized.match(/[^.!?…]+[.!?…]+|[^.!?…]+$/gu) ?? [normalized];
  const chunks = [];
  let current = "";
  const pushCurrent = () => { if (current) chunks.push(current.trim()); current = ""; };
  for (const sentence of sentences) {
    const clean = sentence.trim();
    if (clean.length > maxCharacters) {
      pushCurrent();
      for (let offset = 0; offset < clean.length; offset += maxCharacters) chunks.push(clean.slice(offset, offset + maxCharacters).trim());
    } else if (!current || current.length + clean.length + 1 <= maxCharacters) {
      current = `${current} ${clean}`.trim();
    } else {
      pushCurrent();
      current = clean;
    }
  }
  pushCurrent();
  return chunks;
}

export function meanNormalizedVector(vectors) {
  if (!Array.isArray(vectors) || !vectors.length) throw new Error("Нечего объединять в смысловой вектор");
  const width = vectors[0].length;
  if (!width || vectors.some((vector) => vector.length !== width)) throw new Error("Размерности смысловых векторов различаются");
  const mean = Array(width).fill(0);
  for (const vector of vectors) for (let index = 0; index < width; index += 1) mean[index] += vector[index] / vectors.length;
  const norm = Math.sqrt(mean.reduce((sum, value) => sum + value ** 2, 0));
  if (!norm) throw new Error("Получен нулевой смысловой вектор");
  return mean.map((value) => value / norm);
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
      label: "НАРУШЕНА ТОЧНАЯ ОПОРА",
      tone: "fail",
      explanation: "Не найдена хотя бы одна обязательная точная фраза.",
    };
  }
  if (similarity >= thresholds.preserved) {
    return {
      code: "preserved",
      label: "ВЫСОКАЯ МОДЕЛЬНАЯ БЛИЗОСТЬ",
      tone: "pass",
      explanation: "Точные опоры найдены; коэффициент модели находится в верхнем диапазоне.",
    };
  }
  if (similarity >= thresholds.review) {
    return {
      code: "review",
      label: "ЗОНА РУЧНОГО РАЗЛИЧЕНИЯ",
      tone: "review",
      explanation: "Точные опоры найдены, но модельная близость неоднозначна.",
    };
  }
  return {
    code: "rupture",
    label: "НИЗКАЯ МОДЕЛЬНАЯ БЛИЗОСТЬ",
    tone: "fail",
    explanation: "Точные опоры найдены, но коэффициент модели находится в нижнем диапазоне.",
  };
}

export function buildSemanticItems(source, variants, vectors, anchors, thresholds = SEMANTIC_THRESHOLDS) {
  if (vectors.length !== variants.length + 1) throw new Error("Число эмбеддингов не соответствует числу текстов");
  return variants.map((variant, index) => {
    const similarity = cosineSimilarity(vectors[0], vectors[index + 1]);
    const anchorInspection = inspectAnchors(variant.text, anchors);
    const logicRisks = detectLogicRisks(source, variant.text);
    let verdict = classifySemantic(similarity, anchorInspection, thresholds);
    if (verdict.code === "preserved" && logicRisks.some((risk) => risk.severity === "critical")) {
      verdict = {
        code: "logical-risk",
        label: "ЛОГИЧЕСКИЙ РИСК",
        tone: "review",
        explanation: "Высокая модельная близость не снимает обнаруженного логического предупреждения.",
      };
    }
    return {
      label: variant.label || `Вариант ${index + 1}`,
      text: variant.text,
      similarity,
      anchors: anchorInspection,
      logicRisks,
      lexical: lexicalDifference(source, variant.text),
      verdict,
    };
  });
}

export function semanticReportMarkdown(report) {
  const rows = report.items.map((item) =>
    `| ${item.label} | ${item.similarity.toFixed(3)} | ${item.anchors.present.length}/${item.anchors.required.length} | ${item.logicRisks.length} | ${item.verdict.label} |`,
  ).join("\n");
  return `# TZAR Semantic Conductance Report

- Product: \`${report.product}\`
- Mode: semantic beta
- Model: \`${report.model}@${report.modelRevision}\`
- Generated: ${report.generatedAt}
- Control seal: \`${report.seal}\`

## Source

${report.source}

## Critical anchors

${report.anchors.length ? report.anchors.map((anchor) => `- ${anchor}`).join("\n") : "Not specified"}

| Variant | Cosine coefficient | Exact anchors | Logic warnings | Verdict |
|---|---:|---:|---:|---|
${rows}

Thresholds are operational calibration values, not a scientific proof or a percentage of preserved meaning. A model coefficient is an aid to human distinction; critical anchors are strict user-defined phrases.
`;
}
