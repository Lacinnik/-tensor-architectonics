const FIELDS = ["constructId", "author", "axisTerm", "axisDefinition", "version", "status"];

export function extractInvariant(form) {
  const source = form?.invariant ?? form;
  if (!source || typeof source !== "object") throw new Error("Форма не содержит объект invariant");
  const invariant = {};
  for (const field of FIELDS) {
    const value = source[field];
    if (typeof value !== "string" || value.trim() === "") {
      throw new Error(`Отсутствует обязательное поле invariant.${field}`);
    }
    invariant[field] = value.trim();
  }
  return invariant;
}

export function canonicalString(invariant) {
  return JSON.stringify(Object.fromEntries(FIELDS.map((field) => [field, invariant[field]])));
}

export async function fingerprint(invariant) {
  const bytes = new TextEncoder().encode(canonicalString(invariant));
  const digest = await globalThis.crypto.subtle.digest("SHA-256", bytes);
  return [...new Uint8Array(digest)].map((byte) => byte.toString(16).padStart(2, "0")).join("");
}

async function inspect(form, expected, kind) {
  const invariant = extractInvariant(form);
  const hash = await fingerprint(invariant);
  const differences = FIELDS
    .filter((field) => invariant[field] !== expected.invariant[field])
    .map((field) => ({ field, expected: expected.invariant[field], actual: invariant[field] }));
  return {
    label: form.label || form.representation?.model || "Без названия",
    geometry: form.representation?.geometry || "Unspecified",
    kind,
    hash,
    pass: kind === "negative" ? hash !== expected.hash : hash === expected.hash,
    differences,
    invariant,
  };
}

export async function verifyPayload(payload) {
  if (!payload || typeof payload !== "object") throw new Error("Ожидается JSON-объект");
  const sourceInvariant = extractInvariant(payload.source);
  const sourceHash = await fingerprint(sourceInvariant);
  const expected = { hash: sourceHash, invariant: sourceInvariant };
  const forms = Array.isArray(payload.forms) ? payload.forms : [];
  const negativeControls = Array.isArray(payload.negativeControls) ? payload.negativeControls : [];
  if (forms.length < 2) throw new Error("Нужно не менее двух положительных форм");
  if (negativeControls.length < 1) throw new Error("Нужен хотя бы один отрицательный контроль");
  const positive = await Promise.all(forms.map((form) => inspect(form, expected, "positive")));
  const negative = await Promise.all(negativeControls.map((form) => inspect(form, expected, "negative")));
  return {
    schema: "tzar-conductance-report/1.0.0",
    product: "TZAR-PRODUCT-001",
    theorem: "TZAR-THEOREM-001",
    generatedAt: new Date().toISOString(),
    source: { hash: sourceHash, invariant: sourceInvariant },
    positive,
    negative,
    pass: positive.every((item) => item.pass) && negative.every((item) => item.pass),
  };
}

export function reportMarkdown(report) {
  const rows = [...report.positive, ...report.negative]
    .map((item) => `| ${item.label} | ${item.geometry} | ${item.kind} | ${item.pass ? "PASS" : "FAIL"} | \`${item.hash}\` |`)
    .join("\n");
  return `# TZAR Conductance Report

- Product: \`${report.product}\`
- Theorem: \`${report.theorem}\`
- Generated: ${report.generatedAt}
- Result: **${report.pass ? "PASS" : "FAIL"}**

| Form | Geometry | Control | Result | SHA-256 |
|---|---|---|---|---|
${rows}
`;
}
