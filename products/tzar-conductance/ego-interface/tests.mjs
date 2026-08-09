import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";

await import("./qengine.js");
await import("./tzar-language.js");
await import("./ego-core.js");

const { TzarQEngine: Q, TzarLanguage: Language, TzarEgoCore: Ego } = globalThis;
const languageEvaluation = JSON.parse(await readFile(new URL("./language-evaluation.json", import.meta.url), "utf8"));

const nowIso = "2026-07-31T10:00:00.000Z";
let uuidIndex = 0;
const environment = () => ({
  now: () => nowIso,
  nowMs: () => Date.parse(nowIso),
  uuid: () => `00000000-0000-4000-8000-${String(++uuidIndex).padStart(12, "0")}`,
  nonceStore: new Set(),
});

const state = () => ({
  egoVoice: "Я обязан доказать, что могу сделать всё сразу.",
  whyNow: "Срок приблизился, напряжение выросло.",
  object: "Разговор о сроке проекта",
  innerImage: "Если я назову предел, меня сочтут слабым",
  position: "Я говорю из позиции исполнителя, который пытается гарантировать всё",
  attention: "На страхе утратить доверие",
  euclid: "Есть три задачи и один рабочий день; завершение — согласованный приоритет",
  lobachevsky: "Сократить объём, перенести срок или привлечь второго человека",
  riemann: "Молчание увеличивает перегрузку, ранний разговор возвращает управляемость",
  projective: "Требование безошибочности — моя проекция, а не факт договора",
  supra: "Честность о реальной ёмкости без отказа от ответственности",
  innerLevel: "Мышление",
  outerDomain: "Структуры",
  coreNeed: "согласовать выполнимый приоритет",
  nextExperiment: "назвать три задачи и спросить, какая одна обязательна сегодня",
  trueRequest: "Как мне согласовать выполнимый приоритет, сохраняя честность о реальной ёмкости, и проверить это прямым вопросом?",
  confirmCandidate: true,
  ttlMinutes: 30,
  localSessionConfirmed: true,
  axisCriteria: {
    factVsProjection: true,
    nonCoercion: true,
    feedbackCanCorrect: true,
    subjectAuthorship: true,
  },
  metrics: { alpha: 0.78, iy: 0.72, cm: 0.74, q: 0.69, t: 0.82 },
});

const baseMeta = () => ({ now: () => nowIso, nowMs: () => Date.parse(nowIso), nonceStore: new Set() });

async function test(name, fn) {
  try {
    await fn();
    console.log(`✓ ${name}`);
  } catch (error) {
    console.error(`✗ ${name}`);
    throw error;
  }
}

await test("контракт перечисляет шесть движков и пять геометрий", () => {
  assert.deepEqual(Q.ENGINE_IDS, ["QP-01", "QR-01", "QG-01", "QA-01", "QC-01", "QI-01"]);
  assert.deepEqual(Q.GEOMETRIES, ["Gᴱ", "Gᴸ", "Gᴿ", "Gᴾ", "Gˢ"]);
});

await test("авторский языковой корпус содержит 49 Азов, 24 Буки и 7 Передач", () => {
  assert.equal(Language.AZ.length, 49);
  assert.equal(Language.BUKI.length, 24);
  assert.equal(Language.TRANSMISSIONS.length, 7);
  assert.equal(Language.MODEL_ID, "TZAR-LANGUAGE-001");
  assert.equal(Language.MODEL_VERSION, "0.2.0-candidate");
  assert.deepEqual(Object.keys(Language.PROFILES), ["tzar", "tzar-qengine", "ego-interface"]);
});

await test("синтез формирует редактируемый вопрос, а не диагноз", () => {
  const candidate = Ego.synthesizeCandidate(state());
  assert.match(candidate, /^Как мне /);
  assert.match(candidate, /сохраняя/);
  assert.match(candidate, /проверить выбранный ход/);
});

await test("языковой компилятор разделяет публичный текст и сингулярную формулу", () => {
  const result = Language.compile(state());
  assert.match(result.layers.publicStatement, /Я различаю наблюдаемое/);
  assert.match(result.layers.publicStatement, /наблюдаемый отклик/);
  assert.match(result.formula, /×/);
  assert.match(result.formula, /→/);
  assert.equal(result.boundary.observedQ, null);
  assert.equal(result.tensor.Q, null);
  assert.equal(result.tensor.O, state().object);
  assert.equal(result.tensor.S, state().egoVoice.replace(/\.$/u, ""));
  assert.equal(result.boundary.diagnosis, "not-performed");
});

await test("продуктовые голоса разделены, а Q принимается только как наблюдаемый бинарный возврат", () => {
  const system = Language.compileProduct("tzar", state());
  const artifact = Language.compileProduct("tzar-qengine", state());
  assert.match(system.layers.publicStatement, /^Контур различает объект/);
  assert.match(artifact.layers.publicStatement, /^Исполнение удерживает объект/);
  assert.throws(() => Language.compile({ ...state(), observedQ: 0.69 }), /TZAR_LANGUAGE_Q_MUST_BE_OBSERVED_BINARY/);
});

await test("контрольные авторские связки не дрейфуют", () => {
  for (const fixture of languageEvaluation.cases) {
    const result = Language.compile(fixture.input);
    assert.equal(result.selection.az.id, fixture.expected.az, `${fixture.id}: Аз`);
    assert.equal(result.selection.buka.id, fixture.expected.buka, `${fixture.id}: Бука`);
    assert.equal(result.selection.transmission.id, fixture.expected.transmission, `${fixture.id}: Передача`);
  }
});

await test("полный локальный контур завершается preserved", async () => {
  const run = await Ego.runEgoContour(state(), environment());
  assert.equal(run.status, "completed");
  assert.equal(run.passport.invariantVerdict, "preserved");
  assert.equal(run.engineResults.length, 7);
  assert.deepEqual([...new Set(run.engineResults.map(item => item.engineId))].sort(), [...Q.ENGINE_IDS].sort());
  assert.equal(run.passport.boundary.diagnosis, "not-performed");
  assert.match(run.passport.boundary.authentication, /not-external-authentication/);
  assert.match(run.passport.source.algebra.relation, /Az × Бука × TX/);
  assert.equal(run.passport.lifecycleState, "ACTIVE");
  assert.equal(run.passport.result.language.modelId, "TZAR-LANGUAGE-001");
  assert.equal(run.passport.result.language.engineBindings.length, 6);
  assert.equal(run.passport.result.observedQ, null);
  assert.match(run.passport.result.publicStatement, /Я различаю наблюдаемое/);
});

await test("истинный запрос, совпавший с голосом эго, останавливает preflight", async () => {
  const input = state();
  input.trueRequest = input.egoVoice;
  const run = await Ego.runEgoContour(input, environment());
  assert.equal(run.status, "suspended");
  assert.equal(run.stage, "preflight");
  assert.equal(run.engineResults[0].error.code, "INVARIANT_RUPTURE");
});

await test("неподтверждённое авторство останавливает preflight", async () => {
  const input = state();
  input.confirmCandidate = false;
  const run = await Ego.runEgoContour(input, environment());
  assert.equal(run.status, "suspended");
  assert.equal(run.stage, "preflight");
  assert.equal(run.engineResults[0].invariantVerdict, "review");
});

await test("неподтверждённая локальная сессия закрывает осевой допуск", async () => {
  const input = state();
  input.localSessionConfirmed = false;
  const run = await Ego.runEgoContour(input, environment());
  assert.equal(run.status, "suspended");
  assert.equal(run.stage, "axis");
  assert.equal(run.engineResults.at(-1).error.code, "AUTHENTICATION_REQUIRED");
});

await test("невыполненный осевой критерий закрывает осевой допуск", async () => {
  const input = state();
  input.axisCriteria.feedbackCanCorrect = false;
  const run = await Ego.runEgoContour(input, environment());
  assert.equal(run.status, "suspended");
  assert.equal(run.engineResults.at(-1).error.code, "AXIS_CRITERIA_UNMET");
});

await test("неполная Точка закрывается fail-closed", () => {
  const result = Q.runEngine("QP-01", {
    operationId: "point-incomplete",
    object: "объект",
    geometry: "Gᴾ",
  }, {}, { requireDistinctComponents: true }, baseMeta());
  assert.equal(result.outcome, "denied");
  assert.equal(result.error.code, "POINT_INCOMPLETE");
});

await test("слияние объекта и внутреннего образа приостанавливает Точку", () => {
  const result = Q.runEngine("QP-01", {
    operationId: "point-collapse",
    object: "одно",
    innerConfiguration: "одно",
    position: "позиция",
    attention: "внимание",
    geometry: "Gᴾ",
  }, {}, { requireDistinctComponents: true }, baseMeta());
  assert.equal(result.outcome, "suspended");
  assert.equal(result.error.code, "POINT_COLLAPSE");
});

await test("резонанс не исполняется без пяти метрик", () => {
  const result = Q.runEngine("QR-01", {
    operationId: "resonance-no-metrics",
    subjectStructure: "Sₛ",
    fieldStructure: "Sₚ",
    point: "O ⊕ I",
    geometry: "Gᴿ",
    criteria: [{ id: "x", match: true }],
  }, {}, {}, baseMeta());
  assert.equal(result.error.code, "RESONANCE_CRITERIA_MISSING");
});

await test("ложно заявленный резонанс закрывается", () => {
  const result = Q.runEngine("QR-01", {
    operationId: "false-resonance",
    subjectStructure: "Sₛ",
    fieldStructure: "Sₚ",
    point: "O ⊕ I",
    geometry: "Gᴿ",
    criteria: [{ id: "a", match: true }, { id: "b", match: false }],
    metrics: state().metrics,
    claimedResonance: true,
  }, {}, { minimumMatch: 0.75, containerCapacity: 5 }, baseMeta());
  assert.equal(result.outcome, "denied");
  assert.equal(result.error.code, "RESONANCE_FALSE_POSITIVE");
});

await test("неразрешённый геометрический переход закрывается", () => {
  const result = Q.runEngine("QG-01", {
    operationId: "bad-transition",
    construct: "форма",
    sourceGeometry: "Gᴱ",
    targetGeometry: "Gˢ",
    representationProfile: "local-projection",
  }, { preflightInvariantVerdict: "preserved" }, { allowedTransitions: ["Gᴾ→Gˢ"] }, baseMeta());
  assert.equal(result.error.code, "GEOMETRY_OPERATION_UNSUPPORTED");
});

await test("геометрический переход требует отдельного preserved", () => {
  const result = Q.runEngine("QG-01", {
    operationId: "review-transition",
    construct: "форма",
    targetForm: "новая форма",
    sourceGeometry: "Gᴾ",
    targetGeometry: "Gˢ",
    representationProfile: "local-projection",
    invariantCriterion: "основание",
    transitionRule: "правило",
    invariantEvidence: ["evidence"],
  }, { preflightInvariantVerdict: "review" }, { allowedTransitions: ["Gᴾ→Gˢ"], transitionBudget: 1 }, baseMeta());
  assert.equal(result.outcome, "suspended");
  assert.equal(result.invariantVerdict, "review");
});

await test("Chronos запрещает повтор nonce", () => {
  const env = baseMeta();
  const request = {
    operationId: "chrono-1",
    phase: "arm",
    timeSource: "clock",
    issuedAt: nowIso,
    expiresAt: "2026-07-31T10:30:00.000Z",
    nonce: "nonce-1",
    idempotencyKey: "key-1",
  };
  const context = { cleanupHandlerId: "cleanup" };
  const policy = { trustedTimeSources: ["clock"], maxClockSkewMs: 0, maxTtlMs: 3_600_000 };
  assert.equal(Q.runEngine("QC-01", request, context, policy, env).outcome, "completed");
  const replay = Q.runEngine("QC-01", { ...request, operationId: "chrono-2" }, context, policy, env);
  assert.equal(replay.error.code, "NONCE_REUSED");
});

await test("Chronos disperse требует свидетельство cleanup", () => {
  const result = Q.runEngine("QC-01", {
    operationId: "disperse-no-cleanup",
    phase: "disperse",
  }, {}, {}, baseMeta());
  assert.equal(result.outcome, "failed");
  assert.equal(result.error.code, "CLEANUP_INCOMPLETE");
});

await test("инвариант без проверенной печати закрывается rupture", () => {
  const result = Q.runEngine("QI-01", {
    operationId: "bad-seal",
    invariant: "основание",
    author: "субъект",
    version: "0.2.0",
    source: "тест",
    seal: "sha256:x",
    provenance: ["source"],
    invariantCriteria: [{ id: "one", verdict: "preserved" }],
  }, { integrityEvidence: { sealVerified: false } }, { compatibleVersions: ["0.2.0"] }, baseMeta());
  assert.equal(result.invariantVerdict, "rupture");
  assert.equal(result.error.code, "SEAL_INVALID");
});

await test("неизвестный движок завершается техническим отказом", () => {
  const result = Q.runEngine("QX-99", { operationId: "unknown" }, {}, {}, baseMeta());
  assert.equal(result.outcome, "failed");
  assert.equal(result.error.code, "ENGINE_UNKNOWN");
});

console.log("\nВсе проверки TZAR Ego Interface пройдены.");
