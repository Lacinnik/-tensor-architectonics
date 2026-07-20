export const QENGINE_SCHEMA = "tzar.qengine-result/0.1.0-rc.1";
export const QENGINE_VERSION = "0.1.0-rc.1";
export const ENGINE_IDS = ["QP-01", "QR-01", "QG-01", "QA-01", "QC-01", "QI-01"];
export const GEOMETRIES = ["Gᴱ", "Gᴸ", "Gᴿ", "Gᴾ", "Gˢ"];
const REPRESENTATION_PROFILES = ["encrypted-envelope", "local-projection", "network-payload", "visual-rendering", "audio-rendering"];
const defaultNonceStore = new Set();

const present = value => value !== undefined && value !== null && value !== "";
const list = value => Array.isArray(value) ? value : [];
const normalizedMetrics = metrics => {
  const keys = ["alpha", "iy", "cm", "q", "t"];
  if (!metrics || !keys.every(key => Number.isFinite(metrics[key]) && metrics[key] >= 0 && metrics[key] <= 1)) return null;
  return Object.fromEntries(keys.map(key => [key, metrics[key]]));
};

function executionMeta(engineId, request, environment) {
  const now = environment.now || (() => new Date().toISOString());
  const uuid = environment.uuid || (() => globalThis.crypto?.randomUUID?.() || "qengine-" + Date.now());
  return { engineId, operationId:request.operationId || uuid(), createdAt:now() };
}

function result(meta, patch = {}) {
  return {
    schema: QENGINE_SCHEMA,
    operationId: meta.operationId,
    engineId: meta.engineId,
    engineVersion: QENGINE_VERSION,
    lifecycleState: patch.lifecycleState || "COMPLETED",
    outcome: patch.outcome || "completed",
    invariantVerdict: patch.invariantVerdict || "not-evaluated",
    output: patch.output ?? null,
    evidence: patch.evidence || [],
    error: patch.error || null,
    createdAt: meta.createdAt,
    runtimeStatus: "reference-candidate",
  };
}

function closed(meta, code, category, message, options = {}) {
  const outcome = options.outcome || "denied";
  return result(meta, {
    lifecycleState: options.lifecycleState || (outcome === "suspended" ? "SUSPENDED" : outcome === "failed" ? "FAILED" : "DENIED"),
    outcome,
    invariantVerdict: options.invariantVerdict || "not-evaluated",
    evidence: options.evidence || [],
    error: { code, category, message, retryable:Boolean(options.retryable), causedBy:options.causedBy || null, cleanupRequired:Boolean(options.cleanupRequired) },
  });
}

function runPoint(request, context, policy, meta) {
  const required = ["object", "innerConfiguration", "position", "attention", "geometry"];
  const missing = required.filter(key => !present(request[key]));
  if (missing.length) return closed(meta, "POINT_INCOMPLETE", "contract", "Обязательные компоненты Точки не предъявлены: " + missing.join(", ") + ".");
  if (request.object === request.innerConfiguration) return closed(meta, "POINT_COLLAPSE", "invariant", "Объект и внутренняя конфигурация сведены к одному источнику.", { outcome:"suspended", invariantVerdict:"review" });
  if (policy.requireDistinctComponents !== true) return closed(meta, "POINT_AMBIGUOUS", "policy", "Политика не требует различать объект и внутреннюю конфигурацию.", { outcome:"suspended", invariantVerdict:"review" });
  return result(meta, { invariantVerdict:"review", output:{ point:{ object:request.object, innerConfiguration:request.innerConfiguration }, position:request.position, attention:request.attention, geometry:request.geometry, irreversibleLosses:list(request.irreversibleLosses) }, evidence:["explicit-object", "explicit-inner-configuration", "distinct-components-policy"] });
}

function runResonance(request, context, policy, meta) {
  const criteria = list(request.criteria); const metrics = normalizedMetrics(request.metrics);
  if (!present(request.subjectStructure) || !present(request.fieldStructure) || !present(request.point) || !present(request.geometry) || !criteria.length || !metrics) return closed(meta, "RESONANCE_CRITERIA_MISSING", "contract", "Для оценки нужны явно предъявленные структуры, Точка, геометрия, критерии и пять метрик.");
  if (request.profile && !list(policy.allowedProfiles).includes(request.profile)) return closed(meta, "RESONANCE_PROFILE_UNSUPPORTED", "policy", "Профиль Az / Бука / TX не разрешён явной политикой.");
  if (Number(request.requiredLoad) > Number(policy.containerCapacity)) return closed(meta, "RESONANCE_OVERLOAD", "policy", "Заявленная нагрузка превышает ёмкость контейнера.");
  const matches = criteria.filter(item => item && item.match === true).length;
  const ratio = matches / criteria.length; const threshold = Number.isFinite(policy.minimumMatch) ? policy.minimumMatch : 1;
  if (request.claimedResonance === true && ratio < threshold) return closed(meta, "RESONANCE_FALSE_POSITIVE", "invariant", "Резонанс заявлен при недостаточном явном совпадении критериев.", { invariantVerdict:"review" });
  return result(meta, { invariantVerdict:"review", output:{ form:request.proposedForm || null, matchMap:criteria.map(item => ({id:item.id, match:item.match === true})), matchRatio:ratio, metrics, assessmentBoundary:"recommendational-not-authorizing" }, evidence:["explicit-subject-structure", "explicit-field-structure", "explicit-criteria", "user-supplied-metrics"] });
}

function runGeometry(request, context, policy, meta) {
  if (!GEOMETRIES.includes(request.sourceGeometry) || !GEOMETRIES.includes(request.targetGeometry) || !REPRESENTATION_PROFILES.includes(request.representationProfile)) return closed(meta, "GEOMETRY_OPERATION_UNSUPPORTED", "contract", "Геометрия или профиль представления не входит в заявленный контракт.");
  if (!list(policy.allowedTransitions).includes(request.sourceGeometry + "→" + request.targetGeometry)) return closed(meta, "GEOMETRY_OPERATION_UNSUPPORTED", "policy", "Переход не разрешён политикой.");
  if (Number(request.transitionCount || 1) > Number(policy.transitionBudget || 1)) return closed(meta, "TRANSITION_BUDGET_EXCEEDED", "policy", "Превышен допустимый предел переходов.");
  if (context.preflightInvariantVerdict === "rupture") return closed(meta, "GEOMETRY_RUPTURE", "invariant", "Предварительная проверка обнаружила утрату основания.", { invariantVerdict:"rupture" });
  if (!present(request.construct) || !present(request.targetForm) || !present(request.invariantCriterion) || !present(request.transitionRule) || !list(request.invariantEvidence).length || context.preflightInvariantVerdict !== "preserved") return closed(meta, "GEOMETRY_EVIDENCE_INSUFFICIENT", "evidence", "Нет достаточного внешнего свидетельства сохранения инварианта.", { outcome:"suspended", invariantVerdict:"review" });
  return result(meta, { invariantVerdict:"preserved", output:{ sourceGeometry:request.sourceGeometry, targetGeometry:request.targetGeometry, targetForm:request.targetForm, representationProfile:request.representationProfile, losses:list(request.losses), gains:list(request.gains) }, evidence:[...request.invariantEvidence, "preflight-invariant-preserved"] });
}

function runAxis(request, context, policy, meta) {
  if (!context.authenticationEvidence || context.authenticationEvidence.verified !== true) return closed(meta, "AUTHENTICATION_REQUIRED", "access", "Внешнее проверяемое свидетельство аутентификации отсутствует.");
  if (!list(policy.allowedRoles).includes(request.role) || !list(policy.allowedOperations).includes(request.operation)) return closed(meta, "AUTHORIZATION_DENIED", "access", "Роль или операция не разрешена политикой.");
  if (!list(policy.allowedScopes).includes(request.scope)) return closed(meta, "AUTHORIZATION_SCOPE_VIOLATION", "access", "Область операции выходит за пределы полномочия.");
  const criteria = list(request.axisCriteria);
  if (!criteria.length || criteria.some(item => !item || item.met !== true)) return closed(meta, "AXIS_CRITERIA_UNMET", "axis", "Явно заданные критерии осевого допуска не выполнены.");
  if (list(context.axisEvidence).some(item => item.conflict === true)) return closed(meta, "AXIS_EVIDENCE_CONFLICT", "axis", "Предъявленные свидетельства допуска противоречат друг другу.", { outcome:"suspended" });
  if (!present(policy.explanationProtocol)) return closed(meta, "AXIS_DECISION_UNEXPLAINED", "policy", "Политика не задаёт протокол объяснения решения.", { outcome:"suspended" });
  return result(meta, { output:{ decision:"allow", subjectRef:request.subjectRef, role:request.role, operation:request.operation, scope:request.scope, expiresAt:request.expiresAt || null, explanationProtocol:policy.explanationProtocol }, evidence:["external-authentication-evidence", "role-policy", "explicit-axis-criteria"] });
}

function runChronos(request, context, policy, meta, environment) {
  if (request.phase === "disperse") {
    if (!context.cleanupEvidence || context.cleanupEvidence.completed !== true) return closed(meta, "CLEANUP_INCOMPLETE", "cleanup", "Процедура освобождения ресурсов не подтверждена.", { outcome:"failed", cleanupRequired:true });
    return result(meta, { lifecycleState:"DISPERSED", output:{ phase:"disperse", cleanup:context.cleanupEvidence }, evidence:["explicit-cleanup-evidence"] });
  }
  if (!list(policy.trustedTimeSources).includes(request.timeSource)) return closed(meta, "CLOCK_UNTRUSTED", "time", "Источник времени не разрешён политикой.");
  const issued = Date.parse(request.issuedAt); const expires = Date.parse(request.expiresAt); const nowMs = environment.nowMs ? environment.nowMs() : Date.now();
  if (!Number.isFinite(issued) || !Number.isFinite(expires) || !present(request.nonce) || !present(request.idempotencyKey) || !present(context.cleanupHandlerId)) return closed(meta, "CHRONOS_EXPIRED", "contract", "Временное окно, nonce, идемпотентный ключ или обработчик cleanup не предъявлены.");
  if (Math.abs(issued - nowMs) > Number(policy.maxClockSkewMs || 0)) return closed(meta, "CLOCK_SKEW_EXCEEDED", "time", "Отклонение времени превышает политику.");
  if (expires <= nowMs || expires <= issued || expires - issued > Number(policy.maxTtlMs || 0)) return closed(meta, "CHRONOS_EXPIRED", "time", "Окно действия истекло или превышает допустимый TTL.");
  const store = environment.nonceStore || defaultNonceStore;
  if (store.has(request.nonce) || store.has("idempotency:" + request.idempotencyKey)) return closed(meta, "NONCE_REUSED", "time", "Nonce или идемпотентный ключ уже использован.");
  store.add(request.nonce); store.add("idempotency:" + request.idempotencyKey);
  return result(meta, { lifecycleState:"PREPARED", output:{ phase:"arm", issuedAt:request.issuedAt, expiresAt:request.expiresAt, nonce:request.nonce, idempotencyKey:request.idempotencyKey, cleanupHandlerId:context.cleanupHandlerId }, evidence:["trusted-time-source", "fresh-nonce", "bounded-ttl", "declared-cleanup-handler"] });
}

function runInvariant(request, context, policy, meta) {
  const integrity = context.integrityEvidence || {};
  if (!present(request.seal) || integrity.sealVerified !== true) return closed(meta, "SEAL_INVALID", "integrity", "Контрольная печать не подтверждена внешним проверяющим механизмом.", { invariantVerdict:"rupture" });
  if (request.signature && integrity.signatureVerified !== true) return closed(meta, "SIGNATURE_INVALID", "integrity", "Криптографическая подпись не подтверждена внешним механизмом.", { invariantVerdict:"rupture" });
  if ((policy.requireSignature === true || request.signature) && integrity.signerTrusted !== true) return closed(meta, "SIGNER_UNTRUSTED", "trust", "Ключ не принят явным реестром доверия.", { invariantVerdict:"review" });
  if (!list(policy.compatibleVersions).includes(request.version)) return closed(meta, "VERSION_INCOMPATIBLE", "version", "Версия не разрешена политикой совместимости.");
  if (!present(request.author) || !present(request.source) || !list(request.provenance).length) return closed(meta, "PROVENANCE_MISSING", "provenance", "Автор, источник или цепь происхождения не предъявлены.", { invariantVerdict:"review" });
  const criteria = list(request.invariantCriteria);
  if (!present(request.invariant) || !criteria.length) return closed(meta, "EVIDENCE_INSUFFICIENT", "evidence", "Критерий инварианта или свидетельства отсутствуют.", { outcome:"suspended", invariantVerdict:"review" });
  if (criteria.some(item => item.verdict === "rupture")) return closed(meta, "INVARIANT_RUPTURE", "invariant", "Хотя бы один критический критерий фиксирует подмену основания.", { invariantVerdict:"rupture" });
  if (criteria.some(item => item.verdict !== "preserved")) return closed(meta, "EVIDENCE_INSUFFICIENT", "evidence", "Не все критерии получили вердикт preserved.", { outcome:"suspended", invariantVerdict:"review" });
  return result(meta, { invariantVerdict:"preserved", output:{ author:request.author, version:request.version, source:request.source, provenance:request.provenance, decision:"admit" }, evidence:["seal-verified-externally", ...(request.signature ? ["signature-verified-externally", "signer-trusted"] : []), "compatible-version", "explicit-invariant-criteria"] });
}

export function runEngine(engineId, request = {}, context = {}, policy = {}, environment = {}) {
  const meta = executionMeta(engineId, request, environment);
  if (!ENGINE_IDS.includes(engineId)) return closed(meta, "ENGINE_UNKNOWN", "contract", "Неизвестный идентификатор движка.", { outcome:"failed" });
  try {
    if (engineId === "QP-01") return runPoint(request, context, policy, meta);
    if (engineId === "QR-01") return runResonance(request, context, policy, meta);
    if (engineId === "QG-01") return runGeometry(request, context, policy, meta);
    if (engineId === "QA-01") return runAxis(request, context, policy, meta);
    if (engineId === "QC-01") return runChronos(request, context, policy, meta, environment);
    return runInvariant(request, context, policy, meta);
  } catch (error) {
    return closed(meta, "ENGINE_RUNTIME_FAILURE", "runtime", "Исполнение завершилось непредвиденным техническим отказом.", { outcome:"failed", causedBy:error?.name || "Error", cleanupRequired:true });
  }
}
