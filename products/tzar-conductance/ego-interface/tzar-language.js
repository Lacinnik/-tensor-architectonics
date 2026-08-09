(function attachTzarLanguage(global) {
  "use strict";

  const MODEL_ID = "TZAR-LANGUAGE-001";
  const MODEL_VERSION = "0.2.0-candidate";
  const CORPUS = "Азбука Сингулярности:49 / Буки Перехода:24 / Передачи:7";
  const PROFILES = Object.freeze({
    tzar: Object.freeze({ id: "tzar", voice: "system", targetRelation: "проверить проводимость смысла при сохранении авторского инварианта", context: "TZAR Conductance" }),
    "tzar-qengine": Object.freeze({ id: "tzar-qengine", voice: "artifact", targetRelation: "вернуть проверяемый результат движка без самосертификации инварианта", context: "TZAR-QENGINE-001" }),
    "ego-interface": Object.freeze({ id: "ego-interface", voice: "subject", targetRelation: "различить голос эго и подтверждаемый субъектом кандидат истинного запроса", context: "TZAR-EGO-INTERFACE-001" }),
  });

  const AZ = [
    ["A1", "Азъ", "Присутствие × Пустота = Я. Центр и начало сборки формы."],
    ["A2", "Буки", "Масса внимания. Бытийность. Основание реальности."],
    ["A3", "Веди", "Видение и вектор внимания. Мост восприятия и смысла."],
    ["A4", "Глаголь", "Проявление. Речь как форма творения. Смысл × Воля."],
    ["A5", "Добро", "Выбор + Целостность = Созидание. Этический вектор."],
    ["A6", "Есть", "Наблюдение = Материализация. Удержание проявленного."],
    ["A7", "Живѣтє", "Жизнь-циркуляция. Связь и протекание энергии."],
    ["A8", "Зело", "Интенсивность ⊕. Концентрация энергии."],
    ["A9", "Земля", "Материальность. Заземление. Приём массы."],
    ["A10", "Иже", "Коммуникация. Архитектура взаимодействий."],
    ["A11", "И", "Вход. Принятие. Пустота + Доверие = Приём."],
    ["A12", "Како", "Качество. Структура. Уточнение формы."],
    ["A13", "Люди", "Встреча Я ↔ Ты. Создание межполевого пространства."],
    ["A14", "Мыслете", "Мышление. Сбор и навигация смыслов."],
    ["A15", "Наш", "Принадлежность. Интеграция в систему."],
    ["A16", "Он", "Перспектива. Различение. Другой как отражение."],
    ["A17", "Покой", "Центрирование. Я = 0. Сброс лишнего."],
    ["A18", "Рцы", "Манифестация. Прямая вибрация смысла."],
    ["A19", "Слово", "Мост: внутреннее → наружное. Связь миров."],
    ["A20", "Твердо", "Фиксация. Образ + Воля = Форма."],
    ["A21", "Ук", "Удержание. Сфокусированное движение. Намерение."],
    ["A22", "Ферт", "Светоносность. Излучение присутствия."],
    ["A23", "Хер", "Перекрёсток. Навигация. Выбор в многовариантности."],
    ["A24", "Ци", "Энергетический ток. Направление жизни."],
    ["A25", "Червь", "Глубинный импульс. Трансформация бессознательного."],
    ["A26", "Ша", "Широта. Расширение. Распаковка масштаба."],
    ["A27", "Ща", "Точечная глубина. Многогранность восприятия."],
    ["A28", "Твёрдый знак", "Порог. Пауза. Структурная граница."],
    ["A29", "Ы", "Внутренний ток. Тело говорит «я чувствую»."],
    ["A30", "Мягкий знак", "Мягкое касание. Ласка формы."],
    ["A31", "Э", "Эхо. Узнавание себя в другом."],
    ["A32", "Ю", "Проникающее Я. Сжатие и вхождение."],
    ["A33", "Я", "Совокупное Я. Резонансный источник."],
    ["A34", "⊕", "Суперпозиция. Смыслы в одной точке."],
    ["A35", "∴", "Следствие. Неизбежное проявление."],
    ["A36", "∞", "Волна. Дыхание вне формы."],
    ["A37", "Резон", "Ответ поля. Диалог реальности."],
    ["A38", "Явь", "Проявленность. Масса × Внимание."],
    ["A39", "Поле", "Невидимая матрица возможностей."],
    ["A40", "Точка", "Порог ⊕. Ноль + Воля = Запуск."],
    ["A41", "Архе", "Исток. Довременное основание."],
    ["A42", "Тень", "Скрытое притяжение. Алхимическая материя."],
    ["A43", "Врата", "Переход. Завершение + Готовность."],
    ["A44", "Лик", "Персонифицированный смысл. Образ Я."],
    ["A45", "Суть", "Ядровое качество. Снятие лишнего."],
    ["A46", "Глас", "Голос источника. Я + Истина."],
    ["A47", "Дыхание", "Вдох + Выдох = Ритм жизни."],
    ["A48", "Вибрация", "Частота присутствия. Движение = Влияние."],
    ["A49", "Свет", "Ясность. Знание × Любовь."],
  ];

  const BUKI = [
    ["B1", "⊕", "Суперпозиция", "Совпадение психики, поля и формы в одной точке."],
    ["B2", "∅", "Пустота", "Совершенная потенциальность. Основание любой трансформации."],
    ["B3", "τ", "Пластичность времени", "Изгиб, сжатие и развёртывание хроноса."],
    ["B4", "Ψ", "Волновая форма", "Состояние как волна с амплитудой, частотой и фазой."],
    ["B5", "C⊕", "⊕-Капитал", "Прожитые ⊕-состояния, структурированные в ценность."],
    ["B6", "Σ", "Сумма резонансов", "Кумулятивный отклик поля на ⊕-действие."],
    ["B7", "φ", "Фаза пробуждения", "Момент переключения восприятия."],
    ["B8", "Rᶠ", "Резонанс с будущим", "Навигационный тон ⊕-предчувствия."],
    ["B9", "∇", "Градиент", "Направление и скорость изменения ⊕-состояния."],
    ["B10", "IЯ", "Интеграция ядра", "Собранность и устойчивость Я в переходе."],
    ["B11", "⊗", "Точка кристаллизации", "Переход волны в структуру, рождение формы."],
    ["B12", "Fₛ", "Поток смысла", "Развёртывание смыслов через Я и поле."],
    ["B13", "λ", "Длина волны", "Радиус сохранения и распространения ⊕-состояния."],
    ["B14", "A", "Амплитуда переживания", "Интенсивность проживания и сила импульса."],
    ["B15", "∆S", "Изменение смысла", "Переход к новой смысловой структуре."],
    ["B16", "Q", "Качество отклика", "Способность системы преобразовать импульс в ответ."],
    ["B17", "T", "Текучесть", "Движение энергии сквозь контексты без разрушения."],
    ["B18", "Sᶠ", "Структурная форма", "Геометрия контейнера, удерживающего энергию."],
    ["B19", "Cₘ", "Контейнер смыслов", "Объём, в котором смысл удерживается и переваривается."],
    ["B20", "E⊕", "Энтропическая энергия", "Превращение хаоса в ⊕-устойчивость."],
    ["B21", "α", "Коэффициент соответствия", "Соответствие внутреннего Я и среды."],
    ["B22", "k", "Плотность восприятия", "Сжатие восприятия и острота перехода."],
    ["B23", "ω", "Частота обновления", "Скорость безопасной перезаписи ⊕-состояния."],
    ["B24", "⊕Σ", "Суперпозиция систем", "Наложение полей, рождающее новую систему."],
  ];

  const TRANSMISSIONS = [
    ["TX1", "⊙", "Ядро", "Центрация. Ноль. Сбор в присутствии.", "Назови одно основание, которое следующий ход обязан сохранить."],
    ["TX2", "◌", "Орбита", "Расширение поля без потери центра.", "Сделай одно касание с внешним полем из присутствия."],
    ["TX3", "≈", "Резонанс", "Настройка на явный отклик среды.", "Предъяви формулу другому голосу и зафиксируй его отклик."],
    ["TX4", "⌒", "Мост", "Перевод смысла в действие между сторонами.", "Назови две стороны разрыва и одно действие, которое касается обеих."],
    ["TX5", "◆", "Материализация", "Фокусированное действие и наблюдаемая форма.", "Создай один наблюдаемый артефакт, который можно предъявить сегодня."],
    ["TX6", "⊕", "Интеграция", "Удержание результата внутри целого.", "Укажи, куда входит результат и какое правило системы он меняет."],
    ["TX7", "↻", "Перезапуск", "Снятие инерции и новый заход с сохранённым ядром.", "Отдели сохраняемое ядро от формы, которую пора отпустить."],
  ];

  const EXTRA_SIGNALS = Object.freeze({
    A3: "видеть увидеть внимание вектор направление",
    A5: "честность этика ответственность целостность созидание",
    A10: "согласовать договориться коммуникация взаимодействие",
    A12: "уточнить выполнимый приоритет качество структура критерий",
    A13: "другой партнёр команда встреча совместно",
    A19: "сказать спросить назвать сообщить формулировка",
    A20: "зафиксировать договор срок обязательство форма",
    A21: "удержать намерение фокус следующий ход",
    A23: "выбор варианты ветви приоритет",
    A37: "отклик ответ обратная связь поле",
    A45: "ядро суть основание главное лишнее",
    B3: "срок время сегодня завтра ритм окно",
    B6: "отклик обратная связь возвращается сигнал",
    B9: "направление движение следующий ход",
    B10: "ядро устойчивость сохранить основание",
    B11: "готово сделать создать оформить результат",
    B12: "смысл речь вопрос формулировка сообщить",
    B15: "переосмыслить изменить смысл различить",
    B17: "гибкость обойти сопротивление текучесть",
    B18: "структура план порядок приоритет контейнер",
    B21: "соответствие согласовать честность среда",
    B24: "вместе система команда совместный",
    TX1: "остановиться сохранить основание ядро присутствие",
    TX2: "расширить распространить сообщение звонок пост касание",
    TX3: "наблюдать отклик ответ проверить спросить обратная связь",
    TX4: "согласовать договориться соединить мост стороны разговор",
    TX5: "сделать создать выпустить предъявить завершить артефакт",
    TX6: "встроить интегрировать закрепить обновить система правило",
    TX7: "перезапустить отпустить заново завершить форму ретроспектива",
  });

  const STOP = new Set("когда чтобы который которая которые этого этой через между после перед как мне моё мой моя свои себя сейчас одно один при без для или что чем над под уже ещё где быть был была были из от до по на во и а но с со у к ко о об не ни ли же".split(" "));

  function normalize(value) {
    return String(value ?? "").normalize("NFKC").toLocaleLowerCase("ru").replace(/ё/g, "е").replace(/\s+/g, " ").trim();
  }

  function tokens(value) {
    return (normalize(value).match(/[\p{L}\p{N}]+/gu) || []).filter(token => token.length >= 4 && !STOP.has(token));
  }

  function stem(value) {
    return value.slice(0, Math.min(6, value.length));
  }

  function item(id, symbol, title, description) {
    return { id, symbol, title, description };
  }

  const AZ_ITEMS = Object.freeze(AZ.map(([id, title, description]) => item(id, title, title, description)));
  const BUKI_ITEMS = Object.freeze(BUKI.map(([id, symbol, title, description]) => item(id, symbol, title, description)));
  const TX_ITEMS = Object.freeze(TRANSMISSIONS.map(([id, symbol, title, focus, action]) => ({ id, symbol, title, focus, action, description: `${focus} ${action}` })));

  function rank(corpus, weightedTexts, fallbackId, options = {}) {
    const input = weightedTexts.flatMap(([value, weight]) => tokens(value).map(token => [stem(token), weight]));
    const ranked = corpus.map(entry => {
      const source = tokens(`${entry.title} ${options.explicitOnly ? "" : entry.description} ${EXTRA_SIGNALS[entry.id] || ""}`).map(stem);
      const matches = [];
      let score = 0;
      for (const [needle, weight] of input) {
        if (source.includes(needle)) {
          score += weight;
          matches.push(needle);
        }
      }
      return { entry, score, matches: [...new Set(matches)] };
    }).sort((left, right) => right.score - left.score || left.entry.id.localeCompare(right.entry.id, "ru", { numeric: true }));
    if (!ranked[0]?.score) {
      const fallback = ranked.find(result => result.entry.id === fallbackId);
      fallback.score = 0;
      fallback.matches = ["fallback:author-review"];
      return [fallback, ...ranked.filter(result => result !== fallback)];
    }
    return ranked;
  }

  function clean(value, fallback) {
    const normalized = String(value ?? "").replace(/\s+/g, " ").trim().replace(/[.!?…]+$/, "");
    return normalized || fallback;
  }

  function sentence(value) {
    const cleanValue = clean(value, "");
    return cleanValue ? cleanValue[0].toLocaleUpperCase("ru") + cleanValue.slice(1) + "." : "";
  }

  function compile(state, options = {}) {
    const azRank = rank(AZ_ITEMS, [
      [state.coreNeed, 5], [state.supra, 4], [state.projective, 2], [state.position, 1], [state.innerLevel, 1],
    ], "A45");
    const bukaRank = rank(BUKI_ITEMS, [
      [state.coreNeed, 5], [state.euclid, 4], [state.nextExperiment, 2], [state.riemann, 2], [state.outerDomain, 1],
    ], "B12");
    const txRank = rank(TX_ITEMS, [
      [state.nextExperiment, 6], [state.coreNeed, 3], [state.riemann, 2], [state.lobachevsky, 1],
    ], "TX1", { explicitOnly: true });
    const az = azRank[0].entry;
    const buka = bukaRank[0].entry;
    const transmission = txRank[0].entry;
    const object = clean(state.object, "наблюдаемое событие");
    const image = clean(state.innerImage, "внутренний образ события");
    const need = clean(state.coreNeed, "различить следующий живой ход");
    const invariant = clean(state.supra, "авторское основание");
    const move = clean(state.nextExperiment, transmission.action);
    const feedback = clean(state.riemann, "наблюдаемый ответ поля");
    const trueRequest = `Как мне ${need}, различая факт «${object}» и мой образ «${image}», сохраняя «${invariant}», и проверить выбранный ход через «${move}»?`;
    const profile = PROFILES[options.profile] || PROFILES["ego-interface"];
    const voice = options.voice || profile.voice;
    const subjectTrace = clean(options.subjectTrace || state.subjectTrace || state.egoVoice, "явно предъявленный след субъекта");
    const targetRelation = clean(options.targetRelation || profile.targetRelation, "проверить следующий ход");
    const context = clean(options.context || profile.context, "локальный контур ТзАр");
    const observedQ = state.observedQ ?? null;
    if (observedQ !== null && observedQ !== 0 && observedQ !== 1) throw new Error("TZAR_LANGUAGE_Q_MUST_BE_OBSERVED_BINARY");
    const statements = {
      subject: [`Я различаю наблюдаемое — «${object}» — и возникший во мне образ — «${image}».`, `Моё действительное движение сейчас — ${need}.`, `Я сохраняю основание «${invariant}» и совершаю проверяемый ход: ${move}.`, `Ответом станет не обещание, а наблюдаемый отклик: ${feedback}.`],
      system: [`Контур различает объект «${object}» и отражённый образ «${image}».`, `Целевая связь — ${targetRelation}.`, `Сохраняемое основание — «${invariant}»; проверяемый ход — ${move}.`, `Наблюдаемый возврат: ${feedback}.`],
      artifact: [`Исполнение удерживает объект «${object}» отдельно от результата «${image}».`, `Контракт результата: ${targetRelation}.`, `Инвариант «${invariant}» не считается подтверждённым самим вычислением.`, `Следующая проверка: ${move}; возврат: ${feedback}.`],
    };
    const publicStatement = (statements[voice] || statements.subject).join(" ");
    const formula = `${az.title} × ${buka.symbol} ${buka.title} → ${transmission.symbol} ${transmission.title}`;
    return {
      modelId: MODEL_ID,
      modelVersion: MODEL_VERSION,
      profile: profile.id,
      status: "candidate-authorial-symbolic-compiler",
      corpus: CORPUS,
      formula,
      tensor: { O: object, S: subjectTrace, I: image, R_g: targetRelation, C: context, Q: observedQ, evidence: observedQ === null ? "HOLD-DATA" : "observed" },
      selection: { az, buka, transmission },
      layers: {
        distinction: `O: ${sentence(object)} I: ${sentence(image)}`,
        trueRequest,
        publicStatement,
        nextMove: sentence(move),
        feedbackCriterion: sentence(feedback),
      },
      ranking: {
        az: azRank.slice(0, 3).map(({ entry, score, matches }) => ({ id: entry.id, title: entry.title, score, matches })),
        buka: bukaRank.slice(0, 3).map(({ entry, score, matches }) => ({ id: entry.id, title: entry.title, score, matches })),
        transmission: txRank.slice(0, 3).map(({ entry, score, matches }) => ({ id: entry.id, title: entry.title, score, matches })),
      },
      boundary: {
        selection: "deterministic-corpus-ranking-requires-subject-confirmation",
        diagnosis: "not-performed",
        prediction: "not-performed",
        observedQ,
        subjectConfirmed: options.subjectConfirmed === true,
        display: "human-language-and-symbolic-passport-separated",
      },
    };
  }

  function bindEngines(language, results) {
    const byEngine = new Map(results.map(result => [result.engineId, result]));
    const roles = {
      "QP-01": "различение Объекта и Образа",
      "QR-01": "проверка связи внутренней и внешней структуры",
      "QG-01": "перевод формы при сохранении инварианта",
      "QA-01": "явное авторство и осевой допуск",
      "QC-01": "ограниченный хронос и защита от повтора",
      "QI-01": "инвариант, происхождение и печать",
    };
    return {
      ...language,
      engineBindings: Object.entries(roles).map(([engineId, role]) => {
        const result = byEngine.get(engineId);
        return {
          engineId,
          role,
          outcome: result?.outcome || "not-run",
          invariantVerdict: result?.invariantVerdict || "not-evaluated",
        };
      }),
    };
  }

  global.TzarLanguage = {
    MODEL_ID,
    MODEL_VERSION,
    CORPUS,
    PROFILES,
    AZ: AZ_ITEMS,
    BUKI: BUKI_ITEMS,
    TRANSMISSIONS: TX_ITEMS,
    compile,
    compileProduct(profileId, state, options = {}) {
      const profile = PROFILES[profileId];
      if (!profile) throw new Error(`TZAR_LANGUAGE_PROFILE_UNKNOWN:${profileId}`);
      return compile(state, { ...options, profile: profileId });
    },
    bindEngines,
  };
})(globalThis);
