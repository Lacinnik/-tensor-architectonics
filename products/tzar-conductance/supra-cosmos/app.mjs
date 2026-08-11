import {
  analyzeRgba,
  buildHypotheses,
  createResearchRecord,
  invariantMetrics,
  normalizeWcs,
  validateImageDescriptor,
  validateResearchRecord,
  VERSION
} from "./core.mjs";

const ui = Object.fromEntries([
  "object", "state", "locale", "install", "analyze", "results", "fingerprint", "sources-a", "sources-b", "raw", "baseline", "excess",
  "result-boundary", "hypothesis-list", "passport", "export", "import", "reset", "toast", "file-a", "file-b", "drop-a", "drop-b",
  "canvas-a", "canvas-b", "meta-a", "meta-b", "layer-sky", "layer-medium", "layer-sensor", "layer-invariant"
].map(id => [id, document.getElementById(id)]));

const copy = {
  ru: {
    eyebrow: "ТЕЗАР · БЕЗВРЕМЕННОЙ ПРОСТРАНСТВЕННЫЙ ПРОВОДНИК",
    title: "Космос начинается<br><em>с различения.</em>",
    lead: "Две проекции обрабатываются локально. Supra отделяет световые узлы, среду и сенсорный остаток, затем проверяет кандидат P_invariant относительно случайного поля.",
    boundary: "Γ задаёт порядок проверки, не вероятность. Q остаётся null до наблюдаемого отклика.", objectTitle: "Объект исследования", objectLabel: "Определи объект O дословно",
    objectHint: "Интерфейс не назначает объект, галактику, владельца или физическую причину по форме изображения.", projectionA: "Проекция A", projectionB: "Проекция B",
    dropA: "Выбрать или перенести изображение A", dropB: "Выбрать или перенести изображение B", wcs: "WCS-калибровка · необязательно",
    localTitle: "Локальный контур", localText: "Изображения не загружаются и не входят в JSON-экспорт.", analyze: "Провести через Supra",
    sourcesA: "Источники A", sourcesB: "Источники B", raw: "Сырое сходство", nullModel: "Случайный фон",
    layers: "Небо · среда · сенсор · инвариант", hypotheses: "Безвременное ранжирование", newPoint: "Паспорт исследования",
    export: "Экспортировать JSON", import: "Открыть паспорт", reset: "Новая сессия",
    ready: "READY", running: "CONDUCTING", open: "FIELD OPEN", objectRequired: "Сначала определи объект O.", imagesRequired: "Нужны две проекции.",
    finished: "Новая Точка создана", imported: "Паспорт проверен и открыт", invalidPassport: "Паспорт не прошёл проверку", install: "Установить",
    boundaryResult: ({ raw, baseline, excess }) => `Сырое сходство ${raw}%, случайный фон ${baseline}%, избыток P_invariant ${excess}%. Q остаётся null: структурный кандидат не является измерением физического эффекта.`
  },
  en: {
    eyebrow: "TEZAR · ATEMPORAL SPATIAL CONDUCTOR", title: "Cosmos begins<br><em>with distinction.</em>",
    lead: "Two projections are processed locally. Supra separates light nodes, medium and sensor residual, then tests P_invariant against a randomized field.",
    boundary: "Γ orders tests; it is not a probability. Q stays null until an observed response.", objectTitle: "Research object", objectLabel: "Declare object O verbatim",
    objectHint: "The interface does not infer an object, galaxy, owner or physical cause from image form.", projectionA: "Projection A", projectionB: "Projection B",
    dropA: "Choose or drop image A", dropB: "Choose or drop image B", wcs: "WCS calibration · optional", localTitle: "Local contour",
    localText: "Images are not uploaded or embedded in JSON export.", analyze: "Conduct through Supra", sourcesA: "Sources A", sourcesB: "Sources B",
    raw: "Raw similarity", nullModel: "Random baseline", layers: "Sky · medium · sensor · invariant", hypotheses: "Atemporal ranking",
    newPoint: "Research passport", export: "Export JSON", import: "Open passport", reset: "New session", ready: "READY", running: "CONDUCTING", open: "FIELD OPEN",
    objectRequired: "Declare object O first.", imagesRequired: "Two projections are required.", finished: "New Point created", imported: "Passport validated and opened",
    invalidPassport: "Passport failed validation", install: "Install",
    boundaryResult: ({ raw, baseline, excess }) => `Raw similarity ${raw}%, random baseline ${baseline}%, P_invariant excess ${excess}%. Q remains null: a structural candidate is not a physical-effect measurement.`
  }
};

const state = {
  locale: localStorage.getItem("supra-cosmos-locale") === "en" ? "en" : "ru",
  slots: { A: { bitmap: null, pixels: null, analysis: null, name: null }, B: { bitmap: null, pixels: null, analysis: null, name: null } },
  record: null,
  installPrompt: null
};

let worker = null;
let requestSequence = 0;
const pending = new Map();
try {
  worker = new Worker("./worker.mjs", { type: "module" });
  worker.addEventListener("message", event => {
    const request = pending.get(event.data.id);
    if (!request) return;
    pending.delete(event.data.id);
    event.data.ok ? request.resolve(event.data.analysis) : request.reject(new Error(event.data.error));
  });
  worker.addEventListener("error", () => { worker = null; });
} catch (_) {
  worker = null;
}

function text(key) { return copy[state.locale][key] ?? copy.ru[key] ?? key; }

function setLocale(locale) {
  state.locale = locale;
  document.documentElement.lang = locale;
  localStorage.setItem("supra-cosmos-locale", locale);
  ui.locale.textContent = locale === "ru" ? "EN" : "RU";
  ui.install.textContent = text("install");
  document.querySelectorAll("[data-i18n]").forEach(element => {
    const value = text(element.dataset.i18n);
    if (element.dataset.i18n === "title") element.innerHTML = value;
    else element.textContent = value;
  });
  if (state.record) renderRecord(state.record);
}

function setStatus(message, tone = "idle") {
  ui.state.textContent = message;
  ui.state.dataset.tone = tone;
}

let toastTimer = 0;
function toast(message) {
  clearTimeout(toastTimer);
  ui.toast.textContent = message;
  ui.toast.classList.add("show");
  toastTimer = setTimeout(() => ui.toast.classList.remove("show"), 3300);
}

async function decodeImage(file) {
  const validation = validateImageDescriptor(file);
  if (!validation.valid) throw new Error(validation.message);
  const bitmap = await createImageBitmap(file, { imageOrientation: "from-image" });
  const scale = Math.min(1, 720 / Math.max(bitmap.width, bitmap.height));
  const width = Math.max(1, Math.round(bitmap.width * scale));
  const height = Math.max(1, Math.round(bitmap.height * scale));
  const canvas = document.createElement("canvas");
  canvas.width = width;
  canvas.height = height;
  const context = canvas.getContext("2d", { willReadFrequently: true });
  context.drawImage(bitmap, 0, 0, width, height);
  return { bitmap, pixels: context.getImageData(0, 0, width, height), width, height };
}

function analyzePixels(imageData) {
  if (!worker) return Promise.resolve(analyzeRgba(imageData));
  const id = ++requestSequence;
  return new Promise((resolve, reject) => {
    pending.set(id, { resolve, reject });
    worker.postMessage({ id, image: imageData });
  });
}

async function acceptFile(slotName, file) {
  const slot = state.slots[slotName];
  const decoded = await decodeImage(file);
  slot.bitmap?.close?.();
  slot.bitmap = decoded.bitmap;
  slot.pixels = decoded.pixels;
  slot.analysis = null;
  slot.name = file.name;
  state.record = null;
  ui.results.hidden = true;
  drawRaw(slotName);
  updateReadiness();
}

function drawRaw(slotName) {
  const slot = state.slots[slotName];
  const canvas = ui[`canvas-${slotName.toLowerCase()}`];
  canvas.hidden = false;
  canvas.width = slot.pixels.width;
  canvas.height = slot.pixels.height;
  canvas.getContext("2d").putImageData(slot.pixels, 0, 0);
  ui[`drop-${slotName.toLowerCase()}`].hidden = true;
  ui[`meta-${slotName.toLowerCase()}`].textContent = `${slot.name} · ${slot.pixels.width}×${slot.pixels.height}`;
}

function updateReadiness() {
  const ready = Boolean(state.slots.A.pixels && state.slots.B.pixels && ui.object.value.trim().length >= 3);
  ui.analyze.disabled = !ready;
  if (!state.record) setStatus(ready ? text("ready") : "WAITING", "idle");
}

function wcsFor(slotName) {
  const prefix = slotName.toLowerCase();
  return normalizeWcs({
    centerRaDeg: document.getElementById(`${prefix}-ra`).value,
    centerDecDeg: document.getElementById(`${prefix}-dec`).value,
    fieldWidthDeg: document.getElementById(`${prefix}-width`).value,
    fieldHeightDeg: document.getElementById(`${prefix}-height`).value
  });
}

function drawProjection(slotName, wcs) {
  const slot = state.slots[slotName];
  const canvas = ui[`canvas-${slotName.toLowerCase()}`];
  const context = canvas.getContext("2d");
  context.putImageData(slot.pixels, 0, 0);
  context.lineWidth = 1;
  for (const point of slot.analysis.points.slice(0, 150)) {
    context.strokeStyle = "rgba(104,240,210,.72)";
    context.beginPath();
    context.arc(point.x, point.y, 2.2 + Math.min(3.4, point.contrast / 44), 0, Math.PI * 2);
    context.stroke();
  }
  context.font = "11px ui-monospace";
  if (wcs) {
    context.strokeStyle = "rgba(255,211,106,.34)";
    context.fillStyle = "rgba(255,229,160,.88)";
    for (let index = 1; index < 4; index += 1) {
      const x = canvas.width * index / 4;
      const y = canvas.height * index / 4;
      context.beginPath(); context.moveTo(x, 0); context.lineTo(x, canvas.height); context.stroke();
      context.beginPath(); context.moveTo(0, y); context.lineTo(canvas.width, y); context.stroke();
    }
    context.fillText(`RA ${wcs.centerRaDeg.toFixed(3)}° · DEC ${wcs.centerDecDeg.toFixed(3)}°`, 10, 19);
    context.fillText(`WCS ${wcs.fieldWidthDeg}° × ${wcs.fieldHeightDeg}°`, 10, 35);
  } else {
    context.fillStyle = "rgba(255,209,150,.88)";
    context.fillText("WCS = NULL · SENSOR TOPOLOGY", 10, 19);
  }
}

function setupCanvas(canvas, width, height) {
  canvas.width = width;
  canvas.height = height;
  return canvas.getContext("2d");
}

function drawLayers(analysisA, analysisB, metrics) {
  const width = analysisA.width;
  const height = analysisA.height;
  let context = setupCanvas(ui["layer-sky"], width, height);
  context.fillStyle = "#01030a";
  context.fillRect(0, 0, width, height);
  for (const point of analysisA.points) {
    context.fillStyle = `hsl(188 90% ${Math.min(95, 58 + point.contrast)}%)`;
    context.beginPath(); context.arc(point.x, point.y, 1.3 + point.contrast / 65, 0, Math.PI * 2); context.fill();
  }

  context = setupCanvas(ui["layer-medium"], width, height);
  const medium = context.createImageData(width, height);
  for (let index = 0; index < analysisA.background.length; index += 1) {
    const value = Math.max(0, Math.min(255, analysisA.background[index] * 1.42));
    const pixel = index * 4;
    medium.data[pixel] = value * 0.62;
    medium.data[pixel + 1] = value * 0.83;
    medium.data[pixel + 2] = value;
    medium.data[pixel + 3] = 255;
  }
  context.putImageData(medium, 0, 0);

  context = setupCanvas(ui["layer-sensor"], width, height);
  const sensor = context.createImageData(width, height);
  for (let index = 0; index < analysisA.gray.length; index += 1) {
    const residual = Math.max(0, Math.min(255, 128 + (analysisA.gray[index] - analysisA.background[index]) * 3.1));
    const pixel = index * 4;
    sensor.data[pixel] = residual * 0.76;
    sensor.data[pixel + 1] = residual * 0.9;
    sensor.data[pixel + 2] = residual;
    sensor.data[pixel + 3] = 255;
  }
  context.putImageData(sensor, 0, 0);

  context = setupCanvas(ui["layer-invariant"], 540, 280);
  context.fillStyle = "#01030a";
  context.fillRect(0, 0, 540, 280);
  const drawHistogram = (histogram, color) => {
    context.strokeStyle = color;
    context.lineWidth = 2;
    context.beginPath();
    histogram.forEach((value, index) => {
      const x = 24 + index * (492 / (histogram.length - 1));
      const y = 225 - value * 380;
      index ? context.lineTo(x, y) : context.moveTo(x, y);
    });
    context.stroke();
  };
  drawHistogram(analysisA.histogram, "#68f0d2");
  drawHistogram(analysisB.histogram, "#ff8fd1");
  context.fillStyle = "#ffd36a";
  context.font = "700 34px ui-monospace";
  context.fillText(`+${(metrics.excess * 100).toFixed(1)}%`, 24, 65);
  context.fillStyle = "rgba(210,232,250,.62)";
  context.font = "11px ui-monospace";
  context.fillText("P_INVARIANT EXCESS · Q=NULL", 24, 88);
  context.fillText(`RAW ${(metrics.similarity * 100).toFixed(1)}% · NULL ${(metrics.baseline * 100).toFixed(1)}%`, 24, 106);
}

function renderHypotheses(hypotheses) {
  ui["hypothesis-list"].replaceChildren();
  for (const item of hypotheses) {
    const article = document.createElement("article");
    article.className = "hypothesis";
    const rank = document.createElement("span"); rank.className = "rank"; rank.textContent = item.rank;
    const body = document.createElement("div");
    const title = document.createElement("h3"); title.textContent = item.title;
    const detail = document.createElement("p"); detail.textContent = `${item.detail} · ${item.status}`;
    const score = document.createElement("span"); score.className = "gamma"; score.textContent = `Γ ${item.gamma_g.toFixed(3)}`;
    body.append(title, detail); article.append(rank, body, score); ui["hypothesis-list"].append(article);
  }
}

function renderRecord(record) {
  ui.fingerprint.textContent = record.fingerprint;
  ui["sources-a"].textContent = record.spatialEvidence.projectionA.sources;
  ui["sources-b"].textContent = record.spatialEvidence.projectionB.sources;
  ui.raw.textContent = `${(record.spatialEvidence.topologySimilarity * 100).toFixed(1)}%`;
  ui.baseline.textContent = `${(record.spatialEvidence.randomFieldBaseline * 100).toFixed(1)}%`;
  ui.excess.textContent = `+${(record.spatialEvidence.pInvariantExcess * 100).toFixed(1)}%`;
  ui["result-boundary"].textContent = copy[state.locale].boundaryResult({
    raw: (record.spatialEvidence.topologySimilarity * 100).toFixed(1),
    baseline: (record.spatialEvidence.randomFieldBaseline * 100).toFixed(1),
    excess: (record.spatialEvidence.pInvariantExcess * 100).toFixed(1)
  });
  renderHypotheses(record.hypotheses);
  ui.passport.textContent = JSON.stringify(record, null, 2);
  ui.results.hidden = false;
}

async function conduct() {
  const object = ui.object.value.trim();
  if (object.length < 3) return toast(text("objectRequired"));
  if (!state.slots.A.pixels || !state.slots.B.pixels) return toast(text("imagesRequired"));
  ui.analyze.disabled = true;
  setStatus(text("running"), "running");
  try {
    const [analysisA, analysisB] = await Promise.all([analyzePixels(state.slots.A.pixels), analyzePixels(state.slots.B.pixels)]);
    state.slots.A.analysis = analysisA;
    state.slots.B.analysis = analysisB;
    const metrics = invariantMetrics(analysisA, analysisB);
    const wcsA = wcsFor("A");
    const wcsB = wcsFor("B");
    const hypotheses = buildHypotheses(metrics, analysisA, analysisB, state.locale);
    const record = createResearchRecord({ object, metrics, analysisA, analysisB, wcsA, wcsB, hypotheses, locale: state.locale });
    state.record = record;
    drawProjection("A", wcsA);
    drawProjection("B", wcsB);
    drawLayers(analysisA, analysisB, metrics);
    renderRecord(record);
    setStatus(text("open"), "idle");
    toast(text("finished"));
    ui.results.scrollIntoView({ behavior: "smooth", block: "start" });
  } catch (error) {
    setStatus("RUPTURE", "error");
    toast(error instanceof Error ? error.message : String(error));
  } finally {
    updateReadiness();
  }
}

function downloadRecord() {
  if (!state.record) return;
  const blob = new Blob([`${JSON.stringify(state.record, null, 2)}\n`], { type: "application/json" });
  const url = URL.createObjectURL(blob);
  const anchor = document.createElement("a");
  anchor.href = url;
  anchor.download = `supra-cosmos-${state.record.fingerprint.toLowerCase()}.json`;
  anchor.click();
  setTimeout(() => URL.revokeObjectURL(url), 1000);
}

async function importRecord(file) {
  if (!file || file.size > 2 * 1024 * 1024) throw new Error("JSON превышает 2 МБ.");
  const record = JSON.parse(await file.text());
  const validation = validateResearchRecord(record);
  if (!validation.valid) throw new Error(`${text("invalidPassport")}: ${validation.errors.join(", ")}`);
  state.record = record;
  ui.object.value = record.object;
  renderRecord(record);
  setStatus("PASSPORT", "idle");
  toast(text("imported"));
}

function resetSession() {
  for (const slotName of ["A", "B"]) {
    const slot = state.slots[slotName];
    slot.bitmap?.close?.();
    Object.assign(slot, { bitmap: null, pixels: null, analysis: null, name: null });
    ui[`canvas-${slotName.toLowerCase()}`].hidden = true;
    ui[`drop-${slotName.toLowerCase()}`].hidden = false;
    ui[`meta-${slotName.toLowerCase()}`].textContent = "EMPTY";
  }
  state.record = null;
  ui.results.hidden = true;
  ui.object.value = "";
  document.querySelectorAll(".wcs input").forEach(input => { input.value = ""; });
  updateReadiness();
  window.scrollTo({ top: 0, behavior: "smooth" });
}

for (const slotName of ["A", "B"]) {
  const key = slotName.toLowerCase();
  const input = ui[`file-${key}`];
  const drop = ui[`drop-${key}`];
  input.addEventListener("change", async () => {
    try { if (input.files?.[0]) await acceptFile(slotName, input.files[0]); }
    catch (error) { toast(error.message); }
    input.value = "";
  });
  for (const eventName of ["dragenter", "dragover"]) drop.addEventListener(eventName, event => { event.preventDefault(); drop.classList.add("drag"); });
  for (const eventName of ["dragleave", "drop"]) drop.addEventListener(eventName, event => { event.preventDefault(); drop.classList.remove("drag"); });
  drop.addEventListener("drop", async event => {
    try { if (event.dataTransfer?.files?.[0]) await acceptFile(slotName, event.dataTransfer.files[0]); }
    catch (error) { toast(error.message); }
  });
  drop.addEventListener("keydown", event => { if (event.key === "Enter" || event.key === " ") { event.preventDefault(); input.click(); } });
}

ui.object.addEventListener("input", updateReadiness);
ui.locale.addEventListener("click", () => setLocale(state.locale === "ru" ? "en" : "ru"));
ui.analyze.addEventListener("click", conduct);
ui.export.addEventListener("click", downloadRecord);
ui.import.addEventListener("change", async () => {
  try { if (ui.import.files?.[0]) await importRecord(ui.import.files[0]); }
  catch (error) { toast(error.message); }
  ui.import.value = "";
});
ui.reset.addEventListener("click", resetSession);

window.addEventListener("beforeinstallprompt", event => {
  event.preventDefault();
  state.installPrompt = event;
  ui.install.hidden = false;
});
ui.install.addEventListener("click", async () => {
  if (!state.installPrompt) return;
  await state.installPrompt.prompt();
  state.installPrompt = null;
  ui.install.hidden = true;
});

if ("serviceWorker" in navigator && location.protocol !== "file:") {
  navigator.serviceWorker.register("./sw.js").catch(() => {});
}

setLocale(state.locale);
setStatus(`${text("ready")} · ${VERSION}`, "idle");
updateReadiness();
