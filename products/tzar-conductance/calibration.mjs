export const CALIBRATION_LABELS = Object.freeze(["preserved", "review", "rupture"]);

export function validateCalibrationCorpus(corpus) {
  const errors = [];
  if (corpus?.schema !== "tzar-semantic-calibration-corpus/1.0.0") errors.push("Неизвестная схема корпуса");
  if (!corpus?.id) errors.push("Отсутствует ID корпуса");
  if (!Array.isArray(corpus?.cases) || !corpus.cases.length) errors.push("Корпус не содержит случаев");
  const ids = new Set();
  for (const [index, item] of (corpus?.cases || []).entries()) {
    if (!item.id) errors.push(`Случай ${index + 1}: отсутствует ID`);
    else if (ids.has(item.id)) errors.push(`Повтор ID: ${item.id}`);
    else ids.add(item.id);
    for (const field of ["sourceConstruct", "source", "variant", "rationale"]) {
      if (typeof item[field] !== "string" || !item[field].trim()) errors.push(`${item.id || index + 1}: отсутствует ${field}`);
    }
    if (!CALIBRATION_LABELS.includes(item.candidateLabel)) errors.push(`${item.id || index + 1}: неизвестная метка`);
  }
  return { valid: errors.length === 0, errors, caseCount: corpus?.cases?.length || 0 };
}

export function calibrationSummary(corpus, decisions = {}) {
  const cases = corpus?.cases || [];
  const reviewed = cases.filter((item) => CALIBRATION_LABELS.includes(decisions[item.id]));
  const agreement = reviewed.filter((item) => decisions[item.id] === item.candidateLabel).length;
  const labels = Object.fromEntries(CALIBRATION_LABELS.map((label) => [label, reviewed.filter((item) => decisions[item.id] === label).length]));
  return {
    total: cases.length,
    reviewed: reviewed.length,
    remaining: cases.length - reviewed.length,
    agreement,
    agreementRate: reviewed.length ? agreement / reviewed.length : null,
    labels,
    complete: reviewed.length === cases.length && cases.length > 0,
  };
}

export function buildAuthorReview(corpus, decisions, author = "Александр Лацинник") {
  const summary = calibrationSummary(corpus, decisions);
  return {
    schema: "tzar-semantic-calibration-review/1.0.0",
    corpusId: corpus.id,
    corpusSchema: corpus.schema,
    status: summary.complete ? "author-reviewed" : "author-review-draft",
    author,
    reviewedAt: new Date().toISOString(),
    decisions: corpus.cases.filter((item) => decisions[item.id]).map((item) => ({
      caseId: item.id,
      label: decisions[item.id],
      candidateLabel: item.candidateLabel,
      agreesWithCandidate: decisions[item.id] === item.candidateLabel,
    })),
    summary,
  };
}
