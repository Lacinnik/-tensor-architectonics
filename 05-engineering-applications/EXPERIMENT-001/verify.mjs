import { createHash } from "node:crypto";
import { readFileSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";

const here = dirname(fileURLToPath(import.meta.url));

function read(name) {
  return JSON.parse(readFileSync(join(here, "forms", name), "utf8"));
}

function sigma(form) {
  const value = form.invariant;
  return {
    constructId: value.constructId,
    author: value.author,
    axisTerm: value.axisTerm,
    axisDefinition: value.axisDefinition,
    version: value.version,
    status: value.status,
  };
}

function fingerprint(value) {
  return createHash("sha256").update(JSON.stringify(value)).digest("hex");
}

const positiveFiles = [
  "euclid-linear.json",
  "projective-graph.json",
  "supra-envelope.json",
];
const negativeFile = "negative-control.json";

const positives = positiveFiles.map((file) => ({
  file,
  invariant: sigma(read(file)),
}));
const negative = {
  file: negativeFile,
  invariant: sigma(read(negativeFile)),
};

const expected = fingerprint(positives[0].invariant);
const positiveResults = positives.map(({ file, invariant }) => ({
  file,
  fingerprint: fingerprint(invariant),
  pass: fingerprint(invariant) === expected,
}));
const negativeFingerprint = fingerprint(negative.invariant);
const negativePass = negativeFingerprint !== expected;

const result = {
  experiment: "TZAR-EXPERIMENT-001",
  theorem: "TZAR-THEOREM-001",
  positiveResults,
  negativeControl: {
    file: negative.file,
    fingerprint: negativeFingerprint,
    pass: negativePass,
  },
  pass: positiveResults.every((item) => item.pass) && negativePass,
};

console.log(JSON.stringify(result, null, 2));

if (!result.pass) process.exitCode = 1;
