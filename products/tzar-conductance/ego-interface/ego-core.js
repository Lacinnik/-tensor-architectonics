(function attachTzarEgoCore(global) {
  "use strict";

  const CONSTRUCT_ID = "TZAR-EGO-INTERFACE-001";
  const CONSTRUCT_VERSION = "0.1.0-candidate";
  const ENGINE_CORPUS_VERSION = "0.2.0";
  const PROFILE = "Az/Бука/TX:ego-interface";

  function normalize(value) {
    return String(value ?? "").replace(/\s+/g, " ").trim();
  }

  function trimQuote(value, max = 96) {
    const normalized = normalize(value);
    return normalized.length > max ? normalized.slice(0, max - 1).trimEnd() + "…" : normalized;
  }

  function label(value, fallback) {
    return normalize(value) || fallback;
  }

  function synthesizeCandidate(state) {
    const need = label(state.coreNeed, "различить следующий живой ход");
    const situation = trimQuote(state.euclid || state.object, 86) || "предъявленной ситуации";
    const invariant = trimQuote(state.supra, 86) || "удерживаемое основание";
    const feedback = trimQuote(state.nextExperiment || state.riemann, 86) || "наблюдаемый отклик поля";
    return `Как мне ${need}, находясь в ситуации «${situation}», сохраняя «${invariant}», и проверить следующий ход через «${feedback}»?`;
  }

  function completeness(state) {
    const required = [
      "egoVoice",
      "object",
      "innerImage",
      "position",
      "attention",
      "euclid",
      "lobachevsky",
      "riemann",
      "projective",
      "supra",
      "innerLevel",
      "outerDomain",
      "coreNeed",
      "nextExperiment",
      "trueRequest",
    ];
    const missing = required.filter(key => !normalize(state[key]));
    const metricKeys = ["alpha", "iy", "cm", "q", "t"];
    const invalidMetrics = metricKeys.filter(key => !Number.isFinite(Number(state.metrics?.[key])));
    return { missing, invalidMetrics, complete: missing.length === 0 && invalidMetrics.length === 0 };
  }

  async function sha256(value) {
    const input = new TextEncoder().encode(value);
    if (global.crypto?.subtle) {
      const digest = await global.crypto.subtle.digest("SHA-256", input);
      return "sha256:" + Array.from(new Uint8Array(digest), byte => byte.toString(16).padStart(2, "0")).join("");
    }
    let hash = 2166136261;
    for (const byte of input) {
      hash ^= byte;
      hash = Math.imul(hash, 16777619);
    }
    return "fnv1a-fallback:" + (hash >>> 0).toString(16).padStart(8, "0");
  }

  function safeUuid(environment) {
    return environment.uuid?.() || global.crypto?.randomUUID?.() || `ego-${Date.now()}-${Math.random().toString(16).slice(2)}`;
  }

  function engineEnvironment(environment, nowIso) {
    return {
      ...environment,
      now: environment.now || (() => nowIso),
      nowMs: environment.nowMs || (() => Date.parse(nowIso)),
      nonceStore: environment.nonceStore || new Set(),
    };
  }

  function stageResult(stage, result) {
    return { stage, ...result };
  }

  function stopReason(result) {
    return result.error?.message || `${result.engineId}: ${result.outcome}`;
  }

  async function runEgoContour(inputState, environment = {}) {
    const qengine = global.TzarQEngine;
    if (!qengine?.runEngine) throw new Error("TZAR-QENGINE runtime не загружен.");

    const state = structuredClone(inputState);
    state.trueRequest = normalize(state.trueRequest) || synthesizeCandidate(state);
    state.metrics = Object.fromEntries(
      ["alpha", "iy", "cm", "q", "t"].map(key => [key, Number(state.metrics?.[key])])
    );
    const check = completeness(state);
    if (!check.complete) {
      return {
        status: "incomplete",
        reason: "Не заполнены обязательные различения.",
        missing: check.missing,
        invalidMetrics: check.invalidMetrics,
        candidate: state.trueRequest,
        engineResults: [],
      };
    }

    const nowIso = environment.now?.() || new Date().toISOString();
    const operationId = safeUuid(environment);
    const subjectRef = "subject:local:" + operationId.slice(-12);
    const runtimeEnv = engineEnvironment(environment, nowIso);
    const results = [];

    const basis = {
      constructId: CONSTRUCT_ID,
      constructVersion: CONSTRUCT_VERSION,
      engineCorpusVersion: ENGINE_CORPUS_VERSION,
      egoVoice: state.egoVoice,
      point: {
        object: state.object,
        innerImage: state.innerImage,
        position: state.position,
        attention: state.attention,
      },
      geometryRoute: {
        euclid: state.euclid,
        lobachevsky: state.lobachevsky,
        riemann: state.riemann,
        projective: state.projective,
        supra: state.supra,
      },
      matrix: {
        innerLevel: state.innerLevel,
        outerDomain: state.outerDomain,
      },
      algebra: {
        profile: PROFILE,
        relation: "F = (Az × Бука × TX) ⊕ (Объект ⊕ Образ) @ Геометрия | α, IЯ, Cm, Q, T",
      },
      trueRequest: state.trueRequest,
      nextExperiment: state.nextExperiment,
      metrics: state.metrics,
      createdAt: nowIso,
    };
    const inputSeal = await sha256(JSON.stringify(basis));

    const preflight = qengine.runEngine("QI-01", {
      operationId: operationId + ":preflight",
      invariant: state.supra,
      author: "Субъект локальной сессии",
      version: ENGINE_CORPUS_VERSION,
      source: CONSTRUCT_ID,
      seal: inputSeal,
      provenance: [
        "TZAR-DECLARATION-001",
        "TZAR-AXIOM-001",
        "TZAR-MATH-001",
        "TZAR-QENGINE-001",
        "local-explicit-input",
      ],
      invariantCriteria: [
        { id: "sigma-explicit", verdict: normalize(state.supra) ? "preserved" : "review" },
        { id: "subject-authorship", verdict: state.confirmCandidate === true ? "preserved" : "review" },
        {
          id: "ego-negative-control",
          verdict: normalize(state.trueRequest) !== normalize(state.egoVoice) ? "preserved" : "rupture",
        },
      ],
    }, {
      integrityEvidence: { sealVerified: true, verificationBoundary: "local-sha256-recomputation" },
    }, {
      requireSignature: false,
      compatibleVersions: [ENGINE_CORPUS_VERSION],
    }, runtimeEnv);
    results.push(stageResult("QI-01/preflight", preflight));
    if (preflight.outcome !== "completed" || preflight.invariantVerdict !== "preserved") {
      return stopped("preflight", stopReason(preflight), state, basis, inputSeal, results);
    }

    const ttlMinutes = Math.max(5, Math.min(120, Number(state.ttlMinutes) || 30));
    const expiresAt = new Date(Date.parse(nowIso) + ttlMinutes * 60_000).toISOString();
    const axis = qengine.runEngine("QA-01", {
      operationId: operationId + ":axis",
      subjectRef,
      role: "subject",
      operation: "reflect",
      scope: "local-non-protected",
      expiresAt,
      axisCriteria: [
        { id: "fact-vs-projection", met: state.axisCriteria?.factVsProjection === true },
        { id: "non-coercion", met: state.axisCriteria?.nonCoercion === true },
        { id: "feedback-can-correct", met: state.axisCriteria?.feedbackCanCorrect === true },
        { id: "subject-authorship", met: state.axisCriteria?.subjectAuthorship === true },
      ],
    }, {
      authenticationEvidence: {
        verified: state.localSessionConfirmed === true,
        provider: "local-explicit-session-confirmation",
        securityBoundary: "not-external-authentication",
      },
      axisEvidence: [],
    }, {
      allowedRoles: ["subject"],
      allowedOperations: ["reflect"],
      allowedScopes: ["local-non-protected"],
      explanationProtocol: "tzar-ego-axis-explicit-v1",
    }, runtimeEnv);
    results.push(stageResult("QA-01/axis", axis));
    if (axis.outcome !== "completed") {
      return stopped("axis", stopReason(axis), state, basis, inputSeal, results);
    }

    const nonce = "nonce:" + safeUuid(environment);
    const idempotencyKey = "ego:" + operationId;
    const chronos = qengine.runEngine("QC-01", {
      operationId: operationId + ":chronos-arm",
      phase: "arm",
      timeSource: "browser-session-clock",
      issuedAt: nowIso,
      expiresAt,
      nonce,
      idempotencyKey,
    }, {
      cleanupHandlerId: "ego-interface-logical-release-v1",
    }, {
      trustedTimeSources: ["browser-session-clock"],
      maxClockSkewMs: 5_000,
      maxTtlMs: 120 * 60_000,
    }, runtimeEnv);
    results.push(stageResult("QC-01/arm", chronos));
    if (chronos.outcome !== "completed") {
      return stopped("chronos", stopReason(chronos), state, basis, inputSeal, results);
    }

    const point = qengine.runEngine("QP-01", {
      operationId: operationId + ":point",
      object: state.object,
      innerConfiguration: state.innerImage,
      position: state.position,
      attention: state.attention,
      geometry: "Gᴾ",
      irreversibleLosses: ["свободный рассказ сведён к предъявленным различениям"],
    }, {}, {
      requireDistinctComponents: true,
    }, runtimeEnv);
    results.push(stageResult("QP-01/point", point));
    if (point.outcome !== "completed") {
      return stopped("point", stopReason(point), state, basis, inputSeal, results);
    }

    const resonanceCriteria = [
      { id: "object-image-distinct", match: normalize(state.object) !== normalize(state.innerImage) },
      { id: "position-named", match: Boolean(normalize(state.projective || state.position)) },
      { id: "feedback-loop-present", match: Boolean(normalize(state.riemann) && normalize(state.nextExperiment)) },
      { id: "supra-invariant-explicit", match: Boolean(normalize(state.supra)) },
    ];
    const resonance = qengine.runEngine("QR-01", {
      operationId: operationId + ":resonance",
      subjectStructure: `${state.innerLevel}; ${state.coreNeed}`,
      fieldStructure: `${state.outerDomain}; ${state.euclid}; ${state.lobachevsky}; ${state.riemann}`,
      point: `${state.object} ⊕ ${state.innerImage}`,
      geometry: "Gᴿ",
      criteria: resonanceCriteria,
      metrics: state.metrics,
      profile: PROFILE,
      requiredLoad: resonanceCriteria.length,
      proposedForm: state.trueRequest,
      claimedResonance: false,
    }, {}, {
      allowedProfiles: [PROFILE],
      containerCapacity: 8,
      minimumMatch: 0.75,
    }, runtimeEnv);
    results.push(stageResult("QR-01/resonance", resonance));
    if (resonance.outcome !== "completed") {
      return stopped("resonance", stopReason(resonance), state, basis, inputSeal, results);
    }

    const geometry = qengine.runEngine("QG-01", {
      operationId: operationId + ":geometry",
      construct: state.egoVoice,
      sourceGeometry: "Gᴾ",
      targetGeometry: "Gˢ",
      representationProfile: "local-projection",
      invariantCriterion: state.supra,
      transitionRule: "эго-проекция → кандидат истинного запроса",
      targetForm: state.trueRequest,
      invariantEvidence: [inputSeal, "explicit-subject-confirmation", preflight.operationId],
      transitionCount: 1,
      losses: ["требование немедленного ответа", "непроверенная проекция"],
      gains: ["явный инвариант", "проверяемый следующий ход", "контур обратной связи"],
    }, {
      preflightInvariantVerdict: preflight.invariantVerdict,
    }, {
      allowedTransitions: ["Gᴾ→Gˢ"],
      transitionBudget: 1,
    }, runtimeEnv);
    results.push(stageResult("QG-01/transition", geometry));
    if (geometry.outcome !== "completed" || geometry.invariantVerdict !== "preserved") {
      return stopped("geometry", stopReason(geometry), state, basis, inputSeal, results);
    }

    const outputSeal = await sha256(JSON.stringify({
      inputSeal,
      trueRequest: state.trueRequest,
      supra: state.supra,
      nextExperiment: state.nextExperiment,
      engineOperations: results.map(item => item.operationId),
    }));
    const postflight = qengine.runEngine("QI-01", {
      operationId: operationId + ":postflight",
      invariant: state.supra,
      author: "Субъект локальной сессии",
      version: ENGINE_CORPUS_VERSION,
      source: CONSTRUCT_ID,
      seal: outputSeal,
      provenance: results.map(item => `${item.stage}:${item.operationId}`),
      invariantCriteria: [
        { id: "transition-preserved", verdict: geometry.invariantVerdict },
        { id: "subject-confirmed", verdict: state.confirmCandidate ? "preserved" : "review" },
        { id: "feedback-operationalized", verdict: normalize(state.nextExperiment) ? "preserved" : "review" },
      ],
    }, {
      integrityEvidence: { sealVerified: true, verificationBoundary: "local-sha256-recomputation" },
    }, {
      requireSignature: false,
      compatibleVersions: [ENGINE_CORPUS_VERSION],
    }, runtimeEnv);
    results.push(stageResult("QI-01/postflight", postflight));
    if (postflight.outcome !== "completed" || postflight.invariantVerdict !== "preserved") {
      return stopped("postflight", stopReason(postflight), state, basis, outputSeal, results);
    }

    const passport = {
      schema: "tzar.ego-interface-passport/0.1.0",
      constructId: CONSTRUCT_ID,
      constructVersion: CONSTRUCT_VERSION,
      status: "candidate-local-reflection",
      operationId,
      subjectRef,
      createdAt: nowIso,
      expiresAt,
      inputSeal,
      outputSeal,
      lifecycleState: "ACTIVE",
      outcome: "completed",
      invariantVerdict: postflight.invariantVerdict,
      boundary: {
        diagnosis: "not-performed",
        authentication: "local-explicit-session-confirmation-not-external-authentication",
        integrity: "local-sha256-recomputation-not-author-signature",
        metrics: "user-supplied-recommendational-not-authorizing",
        deletion: "logical-release-only-after-explicit-finish",
      },
      source: {
        egoVoice: state.egoVoice,
        point: basis.point,
        geometryRoute: basis.geometryRoute,
        matrix: basis.matrix,
        algebra: basis.algebra,
      },
      result: {
        trueRequestCandidate: state.trueRequest,
        invariant: state.supra,
        nextExperiment: state.nextExperiment,
        feedbackLoop: `${state.nextExperiment} → наблюдаемый отклик → новая Точка`,
        metrics: state.metrics,
      },
      engineResults: results,
    };

    return {
      status: "completed",
      candidate: state.trueRequest,
      state,
      engineResults: results,
      passport,
    };
  }

  function stopped(stage, reason, state, basis, seal, engineResults) {
    return {
      status: "suspended",
      stage,
      reason,
      candidate: state.trueRequest,
      seal,
      basis,
      engineResults,
    };
  }

  function disperseContour(lastRun, environment = {}) {
    const qengine = global.TzarQEngine;
    if (!lastRun?.passport) throw new Error("Нет активного паспорта для завершения.");
    const nowIso = environment.now?.() || new Date().toISOString();
    const runtimeEnv = engineEnvironment(environment, nowIso);
    const result = qengine.runEngine("QC-01", {
      operationId: lastRun.passport.operationId + ":chronos-disperse",
      phase: "disperse",
    }, {
      cleanupEvidence: {
        completed: true,
        level: "ui-state-and-local-draft-logical-release",
        completedAt: nowIso,
      },
    }, {}, runtimeEnv);
    return stageResult("QC-01/disperse", result);
  }

  global.TzarEgoCore = {
    CONSTRUCT_ID,
    CONSTRUCT_VERSION,
    synthesizeCandidate,
    completeness,
    runEgoContour,
    disperseContour,
  };
})(globalThis);
