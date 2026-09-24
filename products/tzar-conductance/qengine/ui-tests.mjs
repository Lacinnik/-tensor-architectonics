import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import vm from "node:vm";
import { ENGINE_IDS, runEngine } from "./qengine.mjs";

// Execute the shipped UI handlers; only browser surfaces are substituted.
const nodes = new Map();
function node(selector) {
  if (!nodes.has(selector)) nodes.set(selector, {
    value: "", textContent: "", innerHTML: "", disabled: false,
    handlers: {},
    addEventListener(event, handler) { this.handlers[event] = handler; },
    querySelector(child) { return node(`${selector} ${child}`); },
  });
  return nodes.get(selector);
}
let exports = 0;
const context = vm.createContext({
  ENGINE_IDS, runEngine, Blob,
  document: {
    querySelector: node,
    querySelectorAll: () => [],
    createElement: () => ({ click() { exports++; } }),
  },
  URL: { createObjectURL: () => "blob:test", revokeObjectURL() {} },
  TzarLanguage: { compileProduct: () => ({ observedQ: null }) },
});
const source = readFileSync(new URL("./app.mjs", import.meta.url), "utf8");
vm.runInContext(source.replace(/^import .*?;\s*/, ""), context);
const click = selector => node(selector).handlers.click();

for (const field of ["request", "context", "policy"]) {
  click("#load-example");
  click("#run");
  assert.equal(node("#export").disabled, false);
  assert.equal(JSON.parse(node("#result").textContent).outcome, "completed");
  click("#export");
  const priorExports = exports;
  const input = '<b>bad</b>';
  node(`#${field}`).value = input;
  click("#run");
  let parserMessage;
  try { JSON.parse(input); } catch (error) { parserMessage = error.message; }
  assert.equal(node("#summary p").textContent, `${field}: ${parserMessage}`);
  assert.ok(!node("#summary").innerHTML.includes("<b>bad</b>"));
  assert.equal(node("#status").textContent, "JSON не исполнен");
  assert.equal(node("#result").textContent, "");
  assert.equal(node("#export").disabled, true);
  click("#export");
  assert.equal(exports, priorExports, "invalid input must clear the previous export");
}
click("#load-example");
click("#run");
assert.equal(node("#export").disabled, false, "valid input recovers after errors");
console.log("QENGINE UI: literal error text, stale export clearing and recovery passed");
