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
assert.throws(() => extractInvariant({ invariant: { constructId: "broken" } }), /author/);

const broken = structuredClone(example);
broken.forms[1].invariant.axisDefinition = "Подмена";
assert.equal((await verifyPayload(broken)).pass, false);

console.log("TZAR-PRODUCT-001: 9 assertions passed");
