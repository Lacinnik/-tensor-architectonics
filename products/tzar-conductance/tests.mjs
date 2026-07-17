import assert from "node:assert/strict";
import { example } from "./example.mjs";
import { extractInvariant, verifyPayload } from "./core.mjs";

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
assert.equal(new Set(report.ledger.map((entry) => entry.transitionHash)).size, 3);
assert.throws(() => extractInvariant({ invariant: { constructId: "broken" } }), /author/);

const broken = structuredClone(example);
broken.forms[1].invariant.axisDefinition = "Подмена";
assert.equal((await verifyPayload(broken)).pass, false);
const brokenReport = await verifyPayload(broken);
assert.equal(brokenReport.firstBreak.index, 2);
assert.equal(brokenReport.ledger[2].continuous, false);

console.log("TZAR-PRODUCT-001: 17 assertions passed");
