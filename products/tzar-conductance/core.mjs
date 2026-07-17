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

async function digestString(value) {
  const bytes = new TextEncoder().encode(value);
  const digest = await globalThis.crypto.subtle.digest("SHA-256", bytes);
  return [...new Uint8Array(digest)].map((byte) => byte.toString(16).padStart(2, "0")).join("");
}

export async function fingerprint(invariant) {
  return digestString(canonicalString(invariant));
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
  const ledger = [];
  let parentHash = sourceHash;
  let chainContinuous = true;
  for (let index = 0; index < positive.length; index += 1) {
    const item = positive[index];
    chainContinuous = chainContinuous && item.pass;
    const transitionHash = await digestString(JSON.stringify({
      index,
      parentHash,
      currentHash: item.hash,
      label: item.label,
      geometry: item.geometry,
    }));
    ledger.push({
      index: index + 1,
      label: item.label,
      geometry: item.geometry,
      parentHash,
      currentHash: item.hash,
      transitionHash,
      continuous: chainContinuous,
    });
    parentHash = item.hash;
  }
  const firstBreak = ledger.find((entry) => !entry.continuous) ?? null;
  return {
    schema: "tzar-conductance-report/1.1.0",
    product: "TZAR-PRODUCT-001",
    theorem: "TZAR-THEOREM-001",
    generatedAt: new Date().toISOString(),
    source: { hash: sourceHash, invariant: sourceInvariant },
    positive,
    negative,
    ledger,
    firstBreak,
    pass: positive.every((item) => item.pass) && negative.every((item) => item.pass),
  };
}

export function reportMarkdown(report) {
  const rows = [...report.positive, ...report.negative]
    .map((item) => `| ${item.label} | ${item.geometry} | ${item.kind} | ${item.pass ? "PASS" : "FAIL"} | \`${item.hash}\` |`)
    .join("\n");
  const ledgerRows = report.ledger
    .map((entry) => `| ${entry.index} | ${entry.label} | ${entry.geometry} | ${entry.continuous ? "CONTINUOUS" : "BREAK"} | \`${entry.transitionHash}\` |`)
    .join("\n");
  return `# TZAR Conductance Report

- Product: \`${report.product}\`
- Theorem: \`${report.theorem}\`
- Generated: ${report.generatedAt}
- Result: **${report.pass ? "PASS" : "FAIL"}**

| Form | Geometry | Control | Result | SHA-256 |
|---|---|---|---|---|
${rows}

## Transition ledger

| Step | Form | Geometry | Continuity | Transition SHA-256 |
|---|---|---|---|---|
${ledgerRows}

First break: ${report.firstBreak ? `step ${report.firstBreak.index} — ${report.firstBreak.label}` : "not detected"}.
`;
}
