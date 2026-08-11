export const VERSION = "0.4.0-candidate";
export const MAX_IMAGE_BYTES = 24 * 1024 * 1024;
export const ACCEPTED_IMAGE_TYPES = new Set(["image/jpeg", "image/png", "image/webp"]);
export const ATEMPORAL_EQUATION = "Γ_g = α × IЯ × C_m × R_g × 100";

const clamp = (value, lower = 0, upper = 1) => Math.max(lower, Math.min(upper, value));

export function validateImageDescriptor({ name = "", size = 0, type = "" } = {}) {
  if (!ACCEPTED_IMAGE_TYPES.has(type)) {
    return { valid: false, code: "unsupported-type", message: "Поддерживаются JPEG, PNG и WebP." };
  }
  if (!Number.isFinite(size) || size <= 0) {
    return { valid: false, code: "empty-file", message: "Файл пуст или недоступен." };
  }
  if (size > MAX_IMAGE_BYTES) {
    return { valid: false, code: "file-too-large", message: "Размер изображения превышает 24 МБ." };
  }
  return { valid: true, code: "accepted", message: name || "image" };
}

export function fingerprint(value) {
  let hash = 2166136261;
  for (let index = 0; index < value.length; index += 1) {
    hash ^= value.charCodeAt(index);
    hash = Math.imul(hash, 16777619);
  }
  return `SPX-${(hash >>> 0).toString(16).padStart(8, "0").toUpperCase()}`;
}

export function boxBlur(values, width, height, radius) {
  if (values.length !== width * height) throw new Error("Размер поля не совпадает с геометрией.");
  const integral = new Float64Array((width + 1) * (height + 1));
  for (let y = 0; y < height; y += 1) {
    let row = 0;
    for (let x = 0; x < width; x += 1) {
      row += values[y * width + x];
      integral[(y + 1) * (width + 1) + x + 1] = integral[y * (width + 1) + x + 1] + row;
    }
  }
  const output = new Float32Array(width * height);
  for (let y = 0; y < height; y += 1) {
    for (let x = 0; x < width; x += 1) {
      const x0 = Math.max(0, x - radius);
      const x1 = Math.min(width - 1, x + radius);
      const y0 = Math.max(0, y - radius);
      const y1 = Math.min(height - 1, y + radius);
      const a = integral[y0 * (width + 1) + x0];
      const b = integral[y0 * (width + 1) + x1 + 1];
      const c = integral[(y1 + 1) * (width + 1) + x0];
      const d = integral[(y1 + 1) * (width + 1) + x1 + 1];
      output[y * width + x] = (d - b - c + a) / ((x1 - x0 + 1) * (y1 - y0 + 1));
    }
  }
  return output;
}

export function pairHistogram(points, bins = 24, limit = 80) {
  if (!Number.isInteger(bins) || bins < 4) throw new Error("Число интервалов должно быть не меньше четырёх.");
  const histogram = new Float64Array(bins);
  const sample = points.slice(0, limit);
  for (let left = 0; left < sample.length; left += 1) {
    for (let right = left + 1; right < sample.length; right += 1) {
      const dx = sample[left].nx - sample[right].nx;
      const dy = sample[left].ny - sample[right].ny;
      const distance = Math.min(Math.SQRT2, Math.hypot(dx, dy)) / Math.SQRT2;
      histogram[Math.min(bins - 1, Math.floor(distance * bins))] += 1;
    }
  }
  const norm = Math.hypot(...histogram) || 1;
  return Array.from(histogram, value => value / norm);
}

export function cosine(left, right) {
  if (left.length !== right.length || left.length === 0) throw new Error("Векторы должны иметь одинаковую ненулевую длину.");
  let dot = 0;
  let normLeft = 0;
  let normRight = 0;
  for (let index = 0; index < left.length; index += 1) {
    dot += left[index] * right[index];
    normLeft += left[index] ** 2;
    normRight += right[index] ** 2;
  }
  return dot / (Math.sqrt(normLeft * normRight) || 1);
}

export function surrogateBaseline(countA, countB, repeats = 24, seedValue = 0x5eed1234) {
  let seed = seedValue >>> 0;
  const random = () => {
    seed = (Math.imul(seed, 1664525) + 1013904223) >>> 0;
    return seed / 4294967296;
  };
  let total = 0;
  for (let repeat = 0; repeat < repeats; repeat += 1) {
    const left = Array.from({ length: Math.min(80, countA) }, () => ({ nx: random(), ny: random() }));
    const right = Array.from({ length: Math.min(80, countB) }, () => ({ nx: random(), ny: random() }));
    total += cosine(pairHistogram(left), pairHistogram(right));
  }
  return total / repeats;
}

export function invariantMetrics(analysisA, analysisB) {
  if (!analysisA?.histogram || !analysisB?.histogram) throw new Error("Для P_invariant нужны две завершённые проекции.");
  const similarity = cosine(analysisA.histogram, analysisB.histogram);
  const baseline = surrogateBaseline(analysisA.sourceCount, analysisB.sourceCount);
  const excess = clamp((similarity - baseline) / Math.max(0.0001, 1 - baseline));
  return { similarity, baseline, excess };
}

export function analyzeRgba({ data, width, height }) {
  if (!data || data.length !== width * height * 4) throw new Error("Ожидалось RGBA-поле.");
  const gray = new Float32Array(width * height);
  let mean = 0;
  for (let index = 0; index < gray.length; index += 1) {
    const pixel = index * 4;
    gray[index] = data[pixel] * 0.2126 + data[pixel + 1] * 0.7152 + data[pixel + 2] * 0.0722;
    mean += gray[index];
  }
  mean /= gray.length;
  const radius = Math.max(4, Math.round(Math.min(width, height) / 45));
  const background = boxBlur(gray, width, height, radius);
  const threshold = Math.max(7, mean * 0.085);
  const candidates = [];
  for (let y = 2; y < height - 2; y += 2) {
    for (let x = 2; x < width - 2; x += 2) {
      const index = y * width + x;
      const contrast = gray[index] - background[index];
      if (contrast < threshold) continue;
      let maximum = true;
      for (let offsetY = -2; offsetY <= 2 && maximum; offsetY += 1) {
        for (let offsetX = -2; offsetX <= 2; offsetX += 1) {
          if ((offsetX || offsetY) && gray[(y + offsetY) * width + x + offsetX] > gray[index]) {
            maximum = false;
            break;
          }
        }
      }
      if (maximum) candidates.push({ x, y, nx: x / width, ny: y / height, contrast });
    }
  }
  candidates.sort((left, right) => right.contrast - left.contrast);
  const points = [];
  const minDistance = Math.max(5, Math.min(width, height) / 75);
  for (const candidate of candidates) {
    if (points.some(point => Math.hypot(candidate.x - point.x, candidate.y - point.y) < minDistance)) continue;
    points.push(candidate);
    if (points.length >= 220) break;
  }
  let variance = 0;
  let diffuseVariance = 0;
  for (let index = 0; index < gray.length; index += 1) {
    variance += (gray[index] - mean) ** 2;
    diffuseVariance += (background[index] - mean) ** 2;
  }
  return {
    width,
    height,
    points,
    sourceCount: points.length,
    histogram: pairHistogram(points),
    mean,
    stdev: Math.sqrt(variance / gray.length),
    diffuse: Math.sqrt(diffuseVariance / gray.length),
    gray,
    background
  };
}

export function gamma({ alpha, i_y, c_m, relation }) {
  for (const value of [alpha, i_y, c_m, relation]) {
    if (!Number.isFinite(value) || value < 0 || value > 1) throw new Error("Оси Γ должны находиться в диапазоне 0..1.");
  }
  return Number((alpha * i_y * c_m * relation * 100).toFixed(3));
}

export function buildHypotheses(metrics, analysisA, analysisB, locale = "ru") {
  const stellarCoherence = clamp(Math.sqrt(analysisA.sourceCount * analysisB.sourceCount) / 125);
  const diffuseCoherence = clamp((analysisA.diffuse + analysisB.diffuse) / 30);
  const copy = locale === "en" ? {
    stellar: ["Milky Way node topology", "Point-source density forms the strongest observed spatial support."],
    screen: ["Spatial screen between O and I", "Atmosphere, interstellar medium, optics and sensor remain unresolved."],
    medium: ["Galactic absorption corridor", "Dust or scattering may shape the non-uniform stellar field."],
    ether: ["ETHER DIRECT as P_invariant", "Candidate excess of shared relations above a randomized stellar-field baseline."],
    cold: ["Cold state of external galaxies", "No external galaxy or spectral gas trace has been identified in the input."]
  } : {
    stellar: ["Узловая топология Млечного Пути", "Плотность точечных источников образует сильнейшую наблюдаемую пространственную опору."],
    screen: ["Пространственный экран между O и I", "Атмосфера, межзвёздная среда, оптика и сенсор пока не разделены."],
    medium: ["Коридор поглощения галактической среды", "Пыль или рассеяние могут формировать неравномерность звёздного поля."],
    ether: ["ЭФИР ПРЯМОЙ как P_invariant", "Кандидат — избыток общих отношений над случайным звёздным фоном."],
    cold: ["Холодное состояние внешних галактик", "Во входе не идентифицирована внешняя галактика и спектральный след газа."]
  };
  const hypotheses = [
    { id: "H1_STELLAR_TOPOLOGY", title: copy.stellar[0], detail: copy.stellar[1], status: "observed+derived", alpha: 0.95, i_y: 0.88 + 0.08 * stellarCoherence, c_m: 0.95, relation: 0.90 },
    { id: "H2_SPATIAL_SCREEN", title: copy.screen[0], detail: copy.screen[1], status: "observed+hypothesis", alpha: 0.90, i_y: 0.68 + 0.18 * diffuseCoherence, c_m: 0.90, relation: 0.88 },
    { id: "H3_GALACTIC_MEDIUM", title: copy.medium[0], detail: copy.medium[1], status: "hypothesis", alpha: 0.70, i_y: 0.58 + 0.08 * diffuseCoherence, c_m: 0.76, relation: 0.82 },
    { id: "H4_ETHER_DIRECT", title: copy.ether[0], detail: copy.ether[1], status: "hypothesis; Q=null", alpha: 0.50, i_y: metrics.excess * 0.75, c_m: 0.55, relation: 1 },
    { id: "H5_EXTERNAL_COLD_STATE", title: copy.cold[0], detail: copy.cold[1], status: "unknown; Q=null", alpha: 0.25, i_y: 0.25, c_m: 0.50, relation: 0.70 }
  ];
  return hypotheses
    .map(item => ({ ...item, gamma_g: gamma(item) }))
    .sort((left, right) => right.gamma_g - left.gamma_g)
    .map((item, index) => ({ rank: index + 1, ...item }));
}

export function normalizeWcs(input = {}) {
  const parsed = {};
  for (const key of ["centerRaDeg", "centerDecDeg", "fieldWidthDeg", "fieldHeightDeg"]) {
    const raw = input[key];
    const value = raw === "" || raw === null || raw === undefined ? Number.NaN : Number(raw);
    parsed[key] = Number.isFinite(value) ? value : null;
  }
  const complete = Object.values(parsed).every(value => value !== null);
  if (complete && (parsed.centerRaDeg < 0 || parsed.centerRaDeg >= 360 || parsed.centerDecDeg < -90 || parsed.centerDecDeg > 90 || parsed.fieldWidthDeg <= 0 || parsed.fieldHeightDeg <= 0)) {
    throw new Error("WCS выходит за допустимые границы.");
  }
  return complete ? parsed : null;
}

export function createResearchRecord({ object, metrics, analysisA, analysisB, wcsA = null, wcsB = null, hypotheses, locale = "ru" }) {
  const cleanObject = String(object || "").trim();
  if (cleanObject.length < 3) throw new Error("Исследователь должен явно определить объект O.");
  const core = {
    object: cleanObject,
    metrics: {
      topologySimilarity: Number(metrics.similarity.toFixed(6)),
      randomFieldBaseline: Number(metrics.baseline.toFixed(6)),
      pInvariantExcess: Number(metrics.excess.toFixed(6))
    },
    sources: [analysisA.sourceCount, analysisB.sourceCount],
    wcs: [wcsA, wcsB],
    hypotheses: hypotheses.map(item => [item.id, item.gamma_g])
  };
  return {
    schema: "tzar.supra-xr.cosmos-point.v0.4.0",
    version: VERSION,
    fingerprint: fingerprint(JSON.stringify(core)),
    mode: "ATEMPORAL_CONFIGURATION_SUPERPOSITION",
    locale,
    object: cleanObject,
    tensor: {
      map: "O → S → I → R_g @ C",
      singularPoint: "O ⊕ I",
      O: cleanObject,
      S: "две локально обработанные пространственные проекции",
      I: "карта световых узлов, среды, сенсорного остатка и топологического инварианта",
      R_g: "отношение пространственных инвариантов к цели исследования",
      C: "пользовательские изображения и явно введённая WCS; время имеет нулевой вычислительный вес",
      Q: null
    },
    equation: ATEMPORAL_EQUATION,
    time: { physicalAxis: "excluded", frameOrder: "ignored", exif: "provenance-only" },
    privacy: { imagesUploaded: false, imagesEmbeddedInExport: false, processing: "local-browser" },
    spatialEvidence: {
      projectionA: { sources: analysisA.sourceCount, width: analysisA.width, height: analysisA.height, wcs: wcsA },
      projectionB: { sources: analysisB.sourceCount, width: analysisB.width, height: analysisB.height, wcs: wcsB },
      ...core.metrics
    },
    hypotheses: hypotheses.map(({ rank, id, title, detail, status, alpha, i_y, c_m, relation, gamma_g }) => ({ rank, id, title, detail, status, alpha, i_y, c_m, relation, gamma_g })),
    result: {
      state: "ATEMPORAL_FIELD_OPEN",
      pInvariant: metrics.excess > 0 ? "candidate" : "not-distinguished",
      etherDirectMeasured: false,
      empiricalEffectVerified: false,
      Q: null
    }
  };
}

export function validateResearchRecord(record) {
  const errors = [];
  if (record?.schema !== "tzar.supra-xr.cosmos-point.v0.4.0") errors.push("schema");
  if (record?.mode !== "ATEMPORAL_CONFIGURATION_SUPERPOSITION") errors.push("mode");
  if (record?.tensor?.Q !== null || record?.result?.Q !== null) errors.push("Q");
  if (record?.time?.physicalAxis !== "excluded") errors.push("time");
  if (!record?.fingerprint?.startsWith("SPX-")) errors.push("fingerprint");
  if (!Array.isArray(record?.hypotheses) || record.hypotheses.length !== 5) errors.push("hypotheses");
  if (record?.spatialEvidence && Array.isArray(record?.hypotheses)) {
    const core = {
      object: record.object,
      metrics: {
        topologySimilarity: record.spatialEvidence.topologySimilarity,
        randomFieldBaseline: record.spatialEvidence.randomFieldBaseline,
        pInvariantExcess: record.spatialEvidence.pInvariantExcess
      },
      sources: [record.spatialEvidence.projectionA?.sources, record.spatialEvidence.projectionB?.sources],
      wcs: [record.spatialEvidence.projectionA?.wcs ?? null, record.spatialEvidence.projectionB?.wcs ?? null],
      hypotheses: record.hypotheses.map(item => [item.id, item.gamma_g])
    };
    if (fingerprint(JSON.stringify(core)) !== record.fingerprint) errors.push("fingerprint-integrity");
  }
  return { valid: errors.length === 0, errors };
}
