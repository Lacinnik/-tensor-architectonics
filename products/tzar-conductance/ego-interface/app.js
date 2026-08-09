(function startEgoInterface(global) {
  "use strict";

  const form = document.getElementById("ego-form");
  const panels = [...document.querySelectorAll("[data-step]")];
  const stepButtons = [...document.querySelectorAll("[data-jump]")];
  const geometryTabs = [...document.querySelectorAll("[data-geometry-tab]")];
  const geometryPanels = [...document.querySelectorAll("[data-geometry-panel]")];
  const mapNodes = [...document.querySelectorAll("[data-map-node]")];
  const rangeIds = ["alpha", "iy", "cm", "q", "t"];
  const draftKey = "tzar.ego-interface.draft.v1";
  const routeIds = ["euclid", "lobachevsky", "riemann", "projective", "supra"];
  const geometryCodes = ["Gᴱ", "Gᴸ", "Gᴿ", "Gᴾ", "Gˢ"];
  const embedded = new URLSearchParams(global.location.search).get("embed") === "platform";
  const meta = [
    {
      kicker: "КОНТУР 01 · ПРЕДЪЯВЛЕНИЕ",
      title: "Голос эго",
      description: "Формулировка принимается без спора и без признания её целым.",
      code: "ЭГО ≠ ЦЕЛОЕ",
      signature: "Исходная форма сохраняется как источник, а не как приговор.",
      active: "Gᴾ",
    },
    {
      kicker: "QP-01 · POINT ENGINE",
      title: "Точка",
      description: "Объект, внутренний образ, позиция и внимание предъявляются раздельно.",
      code: "O ⊕ I",
      signature: "Суперпозиция не сводится к сумме и не стирает происхождение компонентов.",
      active: "Gᴾ",
    },
    {
      kicker: "QG-01 · GEOMETRY ROUTE",
      title: "Пять режимов",
      description: "Одна форма проходит через разные отношения, не теряя происхождения.",
      code: "Gᴱ → Gᴸ → Gᴿ → Gᴾ → Gˢ",
      signature: "Меняется способ различения; критерий основания остаётся предъявленным.",
      active: "Gᴱ",
    },
    {
      kicker: "QR-01 · RESONANCE ENGINE",
      title: "Афферентный синтез",
      description: "Внутренний уровень и внешний домен собираются в проверяемую форму.",
      code: "⊕(Sₛ, Sₚ) → F",
      signature: "Возникающая формулировка остаётся кандидатом до явного подтверждения субъекта.",
      active: "Gᴿ",
    },
    {
      kicker: "QA-01 + QC-01",
      title: "Осевой допуск",
      description: "Критерии предъявляются явно, а сессия получает ограниченный хронос.",
      code: "Axis(Sₛ) · Hᵢ/Hₑ",
      signature: "Метрики не аутентифицируют, не диагностируют и не измеряют супру.",
      active: null,
    },
    {
      kicker: "QI-01 · INVARIANT & PROVENANCE",
      title: "Паспорт перехода",
      description: "Каждый движок возвращает структурированный след и отдельный вердикт инварианта.",
      code: "Π = provenance + σ + verdict",
      signature: "Успешное вычисление ещё не означает preserved без отдельной проверки.",
      active: "Gˢ",
    },
  ];

  let currentStep = 0;
  let geometryIndex = 0;
  let maxVisited = 0;
  let lastRun = null;
  let toastTimer = null;
  let storageWarningShown = false;

  if (embedded) document.documentElement.classList.add("is-embedded");

  function notifyPlatform(event, payload = {}) {
    if (!embedded || global.parent === global) return;
    const targetOrigin = global.location.origin === "null" ? "*" : global.location.origin;
    global.parent.postMessage({ type: "tzar:ego-interface", event, ...payload }, targetOrigin);
  }

  function byId(id) {
    return document.getElementById(id);
  }

  function value(id) {
    return byId(id)?.value?.trim() || "";
  }

  function checked(id) {
    return byId(id)?.checked === true;
  }

  function showToast(message) {
    const toast = byId("toast");
    toast.textContent = message;
    toast.hidden = false;
    clearTimeout(toastTimer);
    toastTimer = setTimeout(() => { toast.hidden = true; }, 3300);
  }

  function storageGet(key) {
    try {
      return global.localStorage.getItem(key);
    } catch {
      return null;
    }
  }

  function storageSet(key, payload) {
    try {
      global.localStorage.setItem(key, payload);
      return true;
    } catch {
      if (!storageWarningShown) {
        storageWarningShown = true;
        showToast("Браузер запретил локальное хранение. Сессия продолжится без черновика.");
      }
      return false;
    }
  }

  function storageRemove(key) {
    try {
      global.localStorage.removeItem(key);
    } catch {
      // Память формы остаётся только в текущем DOM, если хранилище недоступно.
    }
  }

  function setStep(index, options = {}) {
    const safe = Math.max(0, Math.min(panels.length - 1, index));
    currentStep = safe;
    maxVisited = Math.max(maxVisited, safe);
    panels.forEach((panel, panelIndex) => {
      const active = panelIndex === safe;
      panel.hidden = !active;
      panel.classList.toggle("is-active", active);
    });
    stepButtons.forEach((button, buttonIndex) => {
      if (buttonIndex === safe) button.setAttribute("aria-current", "step");
      else button.removeAttribute("aria-current");
      button.classList.toggle("is-complete", stepIsComplete(buttonIndex));
    });
    updateFieldMap();
    if (!options.silent) {
      document.querySelector(".workspace")?.scrollIntoView({ behavior: "smooth", block: "start" });
    }
  }

  function updateFieldMap() {
    const state = meta[currentStep];
    byId("field-kicker").textContent = state.kicker;
    byId("field-title").textContent = currentStep === 2 ? geometryTitle(geometryIndex) : state.title;
    byId("field-description").textContent = currentStep === 2 ? geometryDescription(geometryIndex) : state.description;
    byId("signature-code").textContent = currentStep === 2 ? geometryCodes[geometryIndex] : state.code;
    byId("signature-text").textContent = state.signature;
    mapNodes.forEach(node => {
      const code = node.dataset.mapNode;
      const active = currentStep === 2 ? code === geometryCodes[geometryIndex] : code === state.active;
      node.classList.toggle("is-active", active);
      const routeIndex = geometryCodes.indexOf(code);
      node.classList.toggle("is-complete", routeIndex >= 0 && Boolean(value(routeIds[routeIndex])));
    });
  }

  function geometryTitle(index) {
    return ["Евклид · граница", "Лобачевский · ветви", "Риман · возврат", "Проекция · позиция", "Супра · инвариант"][index];
  }

  function geometryDescription(index) {
    return [
      "Факты, ресурсы, порядок и критерий завершения.",
      "Несводимые продолжения, цена выбора и реальные развилки.",
      "Петли обратной связи, последствия и изменение траектории.",
      "Различение позиции, наблюдаемой формы и самого конструкта.",
      "Критерий соотносимости форм без превращения его в метрику.",
    ][index];
  }

  function setGeometry(index, options = {}) {
    geometryIndex = Math.max(0, Math.min(geometryPanels.length - 1, index));
    geometryTabs.forEach((tab, tabIndex) => {
      tab.setAttribute("aria-selected", String(tabIndex === geometryIndex));
      tab.classList.toggle("is-complete", Boolean(value(routeIds[tabIndex])));
    });
    geometryPanels.forEach((panel, panelIndex) => {
      const active = panelIndex === geometryIndex;
      panel.hidden = !active;
      panel.classList.toggle("is-active", active);
    });
    byId("geometry-count").textContent = `${geometryIndex + 1} / ${geometryPanels.length}`;
    byId("geometry-prev").disabled = geometryIndex === 0;
    byId("geometry-next").disabled = geometryIndex === geometryPanels.length - 1;
    updateFieldMap();
    if (!options.silent) geometryPanels[geometryIndex].querySelector("textarea")?.focus();
  }

  function markError(control, message) {
    const wrapper = control.closest(".field-label, .candidate-box, .check-row");
    wrapper?.classList.add("has-error");
    control.setAttribute("aria-invalid", "true");
    if (wrapper && !wrapper.querySelector(".field-error")) {
      const error = document.createElement("span");
      error.className = "field-error";
      error.textContent = message;
      wrapper.append(error);
    }
  }

  function clearError(control) {
    const wrapper = control.closest(".field-label, .candidate-box, .check-row");
    wrapper?.classList.remove("has-error");
    wrapper?.querySelector(".field-error")?.remove();
    control.removeAttribute("aria-invalid");
  }

  function validateStep(index, options = {}) {
    const panel = panels[index];
    if (!panel) return true;
    if (index === 3 && !value("trueRequest")) {
      byId("trueRequest").value = global.TzarEgoCore.synthesizeCandidate(collectState());
    }
    const required = [...panel.querySelectorAll("[required]")];
    const extra = [];
    if (index === 3) extra.push(byId("confirmCandidate"));
    if (index === 4) extra.push(
      byId("factVsProjection"),
      byId("nonCoercion"),
      byId("feedbackCanCorrect"),
      byId("subjectAuthorship"),
      byId("localSessionConfirmed")
    );
    let firstInvalid = null;
    [...required, ...extra].forEach(control => {
      const valid = control.type === "checkbox" ? control.checked : Boolean(control.value.trim());
      if (!valid) {
        markError(control, control.type === "checkbox" ? "Нужно явное подтверждение." : "Заполни это различение.");
        firstInvalid ||= control;
      } else {
        clearError(control);
      }
    });
    if (firstInvalid && options.focus !== false) {
      if (index === 2) {
        const routeIndex = routeIds.indexOf(firstInvalid.id);
        if (routeIndex >= 0) setGeometry(routeIndex, { silent: true });
      }
      firstInvalid.focus();
      showToast("Контур остановлен: не все обязательные различения предъявлены.");
    }
    return !firstInvalid;
  }

  function stepIsComplete(index) {
    if (index === 0) return Boolean(value("egoVoice"));
    if (index === 1) return ["object", "innerImage", "position", "attention"].every(id => Boolean(value(id)));
    if (index === 2) return routeIds.every(id => Boolean(value(id)));
    if (index === 3) return ["innerLevel", "outerDomain", "coreNeed", "nextExperiment", "trueRequest"].every(id => Boolean(value(id))) && checked("confirmCandidate");
    if (index === 4) return ["factVsProjection", "nonCoercion", "feedbackCanCorrect", "subjectAuthorship", "localSessionConfirmed"].every(checked);
    return lastRun?.status === "completed";
  }

  function collectState() {
    return {
      egoVoice: value("egoVoice"),
      whyNow: value("whyNow"),
      object: value("object"),
      innerImage: value("innerImage"),
      position: value("position"),
      attention: value("attention"),
      euclid: value("euclid"),
      lobachevsky: value("lobachevsky"),
      riemann: value("riemann"),
      projective: value("projective"),
      supra: value("supra"),
      innerLevel: value("innerLevel"),
      outerDomain: value("outerDomain"),
      coreNeed: value("coreNeed"),
      nextExperiment: value("nextExperiment"),
      trueRequest: value("trueRequest"),
      confirmCandidate: checked("confirmCandidate"),
      ttlMinutes: Number(value("ttlMinutes")),
      localSessionConfirmed: checked("localSessionConfirmed"),
      axisCriteria: {
        factVsProjection: checked("factVsProjection"),
        nonCoercion: checked("nonCoercion"),
        feedbackCanCorrect: checked("feedbackCanCorrect"),
        subjectAuthorship: checked("subjectAuthorship"),
      },
      metrics: Object.fromEntries(rangeIds.map(id => [id, Number(byId(id).value)])),
    };
  }

  function saveDraftIfAllowed() {
    if (!checked("saveDraft")) {
      storageRemove(draftKey);
      return;
    }
    const draft = {};
    [...form.elements].forEach(control => {
      if (!control.name) return;
      draft[control.name] = control.type === "checkbox" ? control.checked : control.value;
    });
    storageSet(draftKey, JSON.stringify(draft));
  }

  function restoreDraft() {
    const raw = storageGet(draftKey);
    if (!raw) return;
    try {
      const draft = JSON.parse(raw);
      [...form.elements].forEach(control => {
        if (!control.name || !(control.name in draft)) return;
        if (control.type === "checkbox") control.checked = Boolean(draft[control.name]);
        else control.value = draft[control.name];
      });
      rangeIds.forEach(updateRangeOutput);
      showToast("Локальный черновик восстановлен с этого устройства.");
    } catch {
      storageRemove(draftKey);
    }
  }

  function updateRangeOutput(id) {
    byId(`${id}-output`).value = Number(byId(id).value).toFixed(2);
  }

  async function executeContour() {
    if (![0, 1, 2, 3, 4].every(index => validateStep(index, { focus: false }))) {
      const firstBad = [0, 1, 2, 3, 4].find(index => !validateStep(index, { focus: false }));
      setStep(firstBad);
      validateStep(firstBad);
      return;
    }
    const runButton = byId("run-contour");
    const rerunButton = byId("rerun-contour");
    runButton.disabled = true;
    rerunButton.disabled = true;
    runButton.innerHTML = "Исполнение…";
    try {
      lastRun = await global.TzarEgoCore.runEgoContour(collectState());
      renderRun(lastRun);
      saveDraftIfAllowed();
    } catch (error) {
      lastRun = { status: "failed", reason: error.message, candidate: value("trueRequest"), engineResults: [] };
      renderRun(lastRun);
    } finally {
      runButton.disabled = false;
      rerunButton.disabled = false;
      runButton.innerHTML = "Исполнить шесть движков <span>→</span>";
    }
  }

  function renderRun(run) {
    byId("run-empty").hidden = true;
    byId("run-result").hidden = false;
    const verdict = byId("result-verdict");
    const completed = run.status === "completed";
    const suspended = run.status === "suspended" || run.status === "incomplete";
    verdict.className = `result-verdict ${suspended ? "is-suspended" : completed ? "" : "is-failed"}`;
    verdict.innerHTML = completed
      ? `<span>PRESERVED</span><div><b>Контур завершён с предъявленным инвариантом</b><p>Результат остаётся кандидатом и не заменяет твоего решения.</p></div>`
      : `<span>${suspended ? "REVIEW" : "FAILED"}</span><div><b>Контур остановлен на стадии ${escapeHtml(run.stage || "input")}</b><p>${escapeHtml(run.reason || "Недостаточно свидетельств для продолжения.")}</p></div>`;
    const language = run.language || run.passport?.result?.language;
    const selection = language?.selection || {};
    byId("result-statement").textContent = completed
      ? language?.layers?.publicStatement || run.candidate
      : "Публичное высказывание не выпущено: контур не завершён.";
    byId("result-formula").textContent = completed ? language?.formula || "—" : "—";
    byId("result-az").textContent = completed && selection.az ? `${selection.az.id} · ${selection.az.title}` : "—";
    byId("result-buka").textContent = completed && selection.buka ? `${selection.buka.id} · ${selection.buka.symbol} ${selection.buka.title}` : "—";
    byId("result-tx").textContent = completed && selection.transmission ? `${selection.transmission.id} · ${selection.transmission.symbol} ${selection.transmission.title}` : "—";
    byId("result-candidate").textContent = run.candidate || value("trueRequest") || "Формулировка не собрана.";
    byId("result-feedback").textContent = completed
      ? run.passport.result.feedbackLoop
      : "Вернись к незавершённому различению, измени формулировку и исполни контур снова.";
    byId("engine-results").innerHTML = (run.engineResults || []).map(item => {
      const detail = item.error?.code || `${item.lifecycleState} · ${item.invariantVerdict}`;
      return `<li class="is-${escapeHtml(item.outcome)}"><code>${escapeHtml(item.stage)}</code><p>${escapeHtml(detail)}</p><small>${escapeHtml(item.outcome)}</small></li>`;
    }).join("") || `<li class="is-suspended"><code>NO-RUN</code><p>Движки не запускались</p><small>review</small></li>`;
    byId("passport-json").textContent = JSON.stringify(run.passport || {
      status: run.status,
      stage: run.stage,
      reason: run.reason,
      seal: run.seal,
      engineResults: run.engineResults,
    }, null, 2);
    byId("export-passport").disabled = !run.passport;
    byId("finish-cycle").disabled = !run.passport;
    stepButtons[5].classList.toggle("is-complete", completed);
    notifyPlatform(completed ? "PRESERVED" : suspended ? "REVIEW" : "FAILED", {
      engineCount: new Set((run.engineResults || []).map(item => item.engineId)).size,
    });
  }

  function escapeHtml(value) {
    return String(value ?? "").replace(/[&<>'"]/g, char => ({
      "&": "&amp;", "<": "&lt;", ">": "&gt;", "'": "&#39;", '"': "&quot;",
    })[char]);
  }

  function downloadJson() {
    if (!lastRun?.passport) return;
    const blob = new Blob([JSON.stringify(lastRun.passport, null, 2)], { type: "application/json" });
    const url = URL.createObjectURL(blob);
    const link = document.createElement("a");
    link.href = url;
    link.download = `tzar-ego-passport-${lastRun.passport.operationId}.json`;
    link.click();
    URL.revokeObjectURL(url);
    showToast("Паспорт экспортирован. Он содержит введённый тобой контекст.");
  }

  async function copyCandidate() {
    const language = lastRun?.language || lastRun?.passport?.result?.language;
    const candidate = language?.layers?.publicStatement || lastRun?.candidate || value("trueRequest");
    if (!candidate) return;
    const copyText = language?.formula ? `${candidate}\n\nСингулярная формула: ${language.formula}` : candidate;
    try {
      await navigator.clipboard.writeText(copyText);
    } catch {
      const helper = document.createElement("textarea");
      helper.value = copyText;
      document.body.append(helper);
      helper.select();
      document.execCommand("copy");
      helper.remove();
    }
    showToast("Публичное высказывание и его формула скопированы.");
  }

  function finishCycle() {
    if (!lastRun?.passport) return;
    const confirmed = global.confirm("Завершить локальную сессию? Поля и сохранённый черновик будут логически очищены. Экспортируй паспорт заранее, если хочешь его сохранить.");
    if (!confirmed) return;
    const dispersed = global.TzarEgoCore.disperseContour(lastRun);
    storageRemove(draftKey);
    form.reset();
    rangeIds.forEach(updateRangeOutput);
    lastRun = null;
    byId("engine-results").innerHTML = `<li><code>${escapeHtml(dispersed.stage)}</code><p>${escapeHtml(dispersed.lifecycleState)} · logical release</p><small>${escapeHtml(dispersed.outcome)}</small></li>`;
    byId("result-verdict").className = "result-verdict";
    byId("result-verdict").innerHTML = `<span>DISPERSED</span><div><b>Логическое освобождение завершено</b><p>Это не гарантия физически необратимого удаления данных устройством.</p></div>`;
    byId("result-statement").textContent = "Содержимое сессии очищено.";
    byId("result-formula").textContent = "—";
    byId("result-az").textContent = "—";
    byId("result-buka").textContent = "—";
    byId("result-tx").textContent = "—";
    byId("result-candidate").textContent = "Содержимое сессии очищено.";
    byId("result-feedback").textContent = "Следующий цикл начнётся с новой Точки.";
    byId("passport-json").textContent = JSON.stringify(dispersed, null, 2);
    byId("export-passport").disabled = true;
    byId("finish-cycle").disabled = true;
    stepButtons.forEach(button => button.classList.remove("is-complete"));
    notifyPlatform("DISPERSED");
    showToast("Сессия логически освобождена. Можно начать новый цикл.");
  }

  stepButtons.forEach((button, index) => {
    button.addEventListener("click", () => {
      if (index <= currentStep || index <= maxVisited) {
        setStep(index);
        return;
      }
      for (let step = currentStep; step < index; step += 1) {
        if (!validateStep(step)) return;
      }
      setStep(index);
    });
  });

  document.querySelectorAll("[data-next]").forEach(button => {
    button.addEventListener("click", () => {
      if (validateStep(currentStep)) setStep(currentStep + 1);
    });
  });

  document.querySelectorAll("[data-prev]").forEach(button => {
    button.addEventListener("click", () => setStep(currentStep - 1));
  });

  geometryTabs.forEach((tab, index) => tab.addEventListener("click", () => setGeometry(index)));
  byId("geometry-prev").addEventListener("click", () => setGeometry(geometryIndex - 1));
  byId("geometry-next").addEventListener("click", () => setGeometry(geometryIndex + 1));

  byId("generate-candidate").addEventListener("click", () => {
    byId("trueRequest").value = global.TzarEgoCore.synthesizeCandidate(collectState());
    clearError(byId("trueRequest"));
    saveDraftIfAllowed();
    showToast("Формулировка собрана как кандидат. Измени её, если она не твоя.");
  });

  rangeIds.forEach(id => byId(id).addEventListener("input", () => updateRangeOutput(id)));
  byId("run-contour").addEventListener("click", executeContour);
  byId("rerun-contour").addEventListener("click", executeContour);
  byId("copy-candidate").addEventListener("click", copyCandidate);
  byId("export-passport").addEventListener("click", downloadJson);
  byId("finish-cycle").addEventListener("click", finishCycle);

  form.addEventListener("input", event => {
    if (event.target instanceof HTMLInputElement || event.target instanceof HTMLTextAreaElement || event.target instanceof HTMLSelectElement) {
      clearError(event.target);
    }
    routeIds.forEach((id, index) => geometryTabs[index].classList.toggle("is-complete", Boolean(value(id))));
    updateFieldMap();
    saveDraftIfAllowed();
  });
  form.addEventListener("change", saveDraftIfAllowed);

  restoreDraft();
  rangeIds.forEach(updateRangeOutput);
  setGeometry(0, { silent: true });
  setStep(0, { silent: true });
  notifyPlatform("READY");
  if (embedded && "ResizeObserver" in global) {
    const reportHeight = () => notifyPlatform("HEIGHT", { height: document.documentElement.scrollHeight });
    new ResizeObserver(reportHeight).observe(document.body);
    global.addEventListener("load", reportHeight, { once: true });
  }
})(globalThis);
