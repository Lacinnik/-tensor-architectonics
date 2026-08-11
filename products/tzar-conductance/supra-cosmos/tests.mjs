import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";
import { analyzeRgba, buildHypotheses, createResearchRecord, gamma, invariantMetrics, normalizeWcs, validateImageDescriptor, validateResearchRecord } from "./core.mjs";

assert.equal(validateImageDescriptor({ name: "field.jpg", size: 1024, type: "image/jpeg" }).valid, true);
assert.equal(validateImageDescriptor({ name: "field.svg", size: 1024, type: "image/svg+xml" }).valid, false);
assert.equal(validateImageDescriptor({ name: "large.jpg", size: 25 * 1024 * 1024, type: "image/jpeg" }).valid, false);
assert.equal(normalizeWcs({ centerRaDeg: "", centerDecDeg: "", fieldWidthDeg: "", fieldHeightDeg: "" }), null);
assert.deepEqual(normalizeWcs({ centerRaDeg: "120.5", centerDecDeg: "-44", fieldWidthDeg: "8", fieldHeightDeg: "6" }), { centerRaDeg: 120.5, centerDecDeg: -44, fieldWidthDeg: 8, fieldHeightDeg: 6 });
assert.throws(() => normalizeWcs({ centerRaDeg: 361, centerDecDeg: 0, fieldWidthDeg: 1, fieldHeightDeg: 1 }), /WCS/);
assert.equal(gamma({ alpha: 1, i_y: .5, c_m: .5, relation: .8 }), 20);

const image = (phase = 0) => {
  const width = 48, height = 48, data = new Uint8ClampedArray(width * height * 4);
  for (let y = 0; y < height; y += 1) for (let x = 0; x < width; x += 1) {
    const index = (y * width + x) * 4;
    const star = ((x * 7 + y * 11 + phase) % 41 === 0) ? 245 : 14 + ((x + y) % 8);
    data[index] = star; data[index + 1] = star; data[index + 2] = star + (star > 200 ? 8 : 0); data[index + 3] = 255;
  }
  return { data, width, height };
};
const analysisA = analyzeRgba(image(0));
const analysisB = analyzeRgba(image(3));
assert.ok(analysisA.sourceCount > 0);
assert.equal(analysisA.histogram.length, 24);
const metrics = invariantMetrics(analysisA, analysisB);
assert.ok(metrics.similarity >= 0 && metrics.similarity <= 1);
assert.ok(metrics.baseline >= 0 && metrics.baseline <= 1);
assert.ok(metrics.excess >= 0 && metrics.excess <= 1);
const hypotheses = buildHypotheses(metrics, analysisA, analysisB, "ru");
assert.equal(hypotheses.length, 5);
assert.deepEqual(hypotheses.map(item => item.rank), [1, 2, 3, 4, 5]);
const record = createResearchRecord({ object: "Тестовое звёздное поле", metrics, analysisA, analysisB, hypotheses });
assert.equal(record.tensor.Q, null);
assert.equal(record.result.Q, null);
assert.equal(record.time.physicalAxis, "excluded");
assert.equal(record.privacy.imagesUploaded, false);
assert.equal(validateResearchRecord(record).valid, true);
const tampered = structuredClone(record); tampered.object = "Подменённый объект";
assert.equal(validateResearchRecord(tampered).valid, false);

const html = await readFile(new URL("./index.html", import.meta.url), "utf8");
const app = await readFile(new URL("./app.mjs", import.meta.url), "utf8");
const worker = await readFile(new URL("./worker.mjs", import.meta.url), "utf8");
const serviceWorker = await readFile(new URL("./sw.js", import.meta.url), "utf8");
assert.match(html, /O → S → I → R<sub>g<\/sub> @ C/);
assert.match(html, /local-first · Q=null/);
assert.match(app, /createResearchRecord/);
assert.match(worker, /analyzeRgba/);
assert.match(serviceWorker, /supra-cosmos-v0\.4\.0/);
assert.doesNotMatch(html, /data:image\//);

console.log("SUPRA-XR-COSMOS: 26 assertions passed");
