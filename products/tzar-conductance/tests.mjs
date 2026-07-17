import assert from "node:assert/strict";
import { example } from "./example.mjs";
import { extractInvariant, verifyPayload, verifyReportSeal } from "./core.mjs";
import { buildSemanticItems, classifySemantic, cosineSimilarity, inspectAnchors, parseAnchors } from "./semantic.mjs";

const report = await verifyPayload(example);
assert.equal(report.pass, true);
assert.equal(report.positive.length, 3);
assert.ok(report.positive.every((item) => item.pass));
assert.equal(report.negative.length, 1);
assert.equal(report.negative[0].pass, true);
assert.equal(new Set(report.positive.map((item) => item.hash)).size, 1);
assert.notEqual(report.positive[0].hash, report.negative[0].hash);
assert.equal(report.positive[0].differences.length, 0);
assert.equal(report.negative[0].differences[0].field, "axisDefinition");
assert.equal(report.ledger.length, 3);
assert.ok(report.ledger.every((entry) => entry.continuous));
assert.equal(report.firstBreak, null);
assert.equal((await verifyReportSeal(report)).valid, true);
assert.equal(new Set(report.ledger.map((entry) => entry.transitionHash)).size, 3);
assert.throws(() => extractInvariant({ invariant: { constructId: "broken" } }), /author/);

const broken = structuredClone(example);
broken.forms[1].invariant.axisDefinition = "Подмена";
assert.equal((await verifyPayload(broken)).pass, false);
const brokenReport = await verifyPayload(broken);
assert.equal(brokenReport.firstBreak.index, 2);
assert.equal(brokenReport.ledger[2].continuous, false);
const tamperedPassport = structuredClone(report);
tamperedPassport.positive[0].label = "Подменённая форма";
assert.equal((await verifyReportSeal(tamperedPassport)).valid, false);
assert.equal((await verifyReportSeal({})).valid, false);

assert.deepEqual(parseAnchors("  Осевой термин  \nосевой термин\nВторая опора"), ["осевой термин", "вторая опора"]);
assert.equal(inspectAnchors("Здесь есть ОСЕВОЙ   ТЕРМИН.", ["осевой термин"]).coverage, 1);
assert.deepEqual(inspectAnchors("Опора утрачена", ["осевой термин"]).missing, ["осевой термин"]);
assert.equal(cosineSimilarity([1, 0], [1, 0]), 1);
assert.equal(cosineSimilarity([1, 0], [0, 1]), 0);
assert.throws(() => cosineSimilarity([1], [1, 2]), /одинаковую/);
assert.equal(classifySemantic(0.9, inspectAnchors("опора", ["опора"])).code, "preserved");
assert.equal(classifySemantic(0.7, inspectAnchors("опора", ["опора"])).code, "review");
assert.equal(classifySemantic(0.4, inspectAnchors("опора", ["опора"])).code, "rupture");
assert.equal(classifySemantic(0.99, inspectAnchors("другой текст", ["опора"])).code, "critical-break");
const semanticItems = buildSemanticItems("Источник", [{ label: "A", text: "опора" }], [[1, 0], [0.8, 0.2]], ["опора"]);
assert.equal(semanticItems.length, 1);
assert.equal(semanticItems[0].verdict.code, "preserved");

console.log("TZAR-PRODUCT-001: 32 assertions passed");
