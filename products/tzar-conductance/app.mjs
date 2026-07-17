import { reportMarkdown, verifyPayload } from "./core.mjs";
import { example } from "./example.mjs";

const input = document.querySelector("#payload");
const verifyButton = document.querySelector("#verify");
const exampleButton = document.querySelector("#example");
const resetButton = document.querySelector("#reset");
const exportJson = document.querySelector("#export-json");
const exportMarkdown = document.querySelector("#export-markdown");
const result = document.querySelector("#result");
const status = document.querySelector("#status");
let currentReport = null;

function setStatus(text, tone = "idle") {
  status.textContent = text;
  status.dataset.tone = tone;
}

function download(name, content, type) {
  const url = URL.createObjectURL(new Blob([content], { type }));
  const link = Object.assign(document.createElement("a"), { href: url, download: name });
  link.click();
  URL.revokeObjectURL(url);
}

function render(report) {
  const items = [...report.positive, ...report.negative];
  result.innerHTML = `
    <div class="summary ${report.pass ? "pass" : "fail"}">
      <span class="summary-mark">${report.pass ? "⊕" : "×"}</span>
      <div><small>Результат контура</small><strong>${report.pass ? "ПРОВОДИМ" : "ОБНАРУЖЕН РАЗРЫВ"}</strong></div>
    </div>
    <div class="chain">
      ${items.map((item, index) => `
        <article class="node ${item.pass ? "pass" : "fail"}">
          <div class="node-top"><span>${String(index + 1).padStart(2, "0")}</span><b>${item.pass ? "PASS" : "FAIL"}</b></div>
          <h3>${item.label}</h3>
          <p>${item.geometry} · ${item.kind === "negative" ? "отрицательный контроль" : "положительная форма"}</p>
          <code title="${item.hash}">${item.hash.slice(0, 16)}…</code>
        </article>`).join("")}
    </div>`;
}

async function run() {
  try {
    setStatus("Проверка…", "work");
    currentReport = await verifyPayload(JSON.parse(input.value));
    render(currentReport);
    exportJson.disabled = false;
    exportMarkdown.disabled = false;
    setStatus(currentReport.pass ? "Контур проводим" : "Контур разорван", currentReport.pass ? "pass" : "fail");
  } catch (error) {
    currentReport = null;
    result.innerHTML = `<div class="error"><strong>Невозможно выполнить проверку</strong><p>${error.message}</p></div>`;
    exportJson.disabled = true;
    exportMarkdown.disabled = true;
    setStatus("Ошибка входа", "fail");
  }
}

exampleButton.addEventListener("click", () => { input.value = JSON.stringify(example, null, 2); run(); });
resetButton.addEventListener("click", () => { input.value = ""; result.innerHTML = '<div class="empty">Загрузите пример или вставьте JSON-конструкт.</div>'; setStatus("Ожидание конструкта"); });
verifyButton.addEventListener("click", run);
exportJson.addEventListener("click", () => download("tzar-conductance-report.json", JSON.stringify(currentReport, null, 2), "application/json"));
exportMarkdown.addEventListener("click", () => download("tzar-conductance-report.md", reportMarkdown(currentReport), "text/markdown"));

input.value = JSON.stringify(example, null, 2);
run();
