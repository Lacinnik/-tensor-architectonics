import { reportMarkdown, sealReport, verifyPayload, verifyReportSeal } from "./core.mjs";
import { example } from "./example.mjs";
import { buildSemanticItems, parseAnchors, semanticReportMarkdown, SEMANTIC_MODEL, SEMANTIC_MODEL_REVISION, SEMANTIC_THRESHOLDS } from "./semantic.mjs";

const fields = ["constructId", "author", "axisTerm", "axisDefinition", "version", "status"];
const labels = { constructId:"ID конструкта",author:"Автор",axisTerm:"Осевой термин",axisDefinition:"Осевое определение",version:"Версия",status:"Статус" };
const geometries = ["Euclid","Lobachevsky","Riemann","Projective","Supra"];
const $ = (selector) => document.querySelector(selector);
const input=$("#payload"), result=$("#result"), status=$("#status"), formsHost=$("#forms"), sourceHost=$("#source-fields");
const exportJson=$("#export-json"), exportMarkdown=$("#export-markdown"), passportFile=$("#passport-file"), passportStatus=$("#passport-status");
let currentReport=null;
let currentReportKind="structural";
let semanticWorker=null;
let cancelSemanticJob=null;

const semanticExample={
  source:"Цифровой продукт проводит явно заданный инвариант через различные формы представления и обнаруживает его подмену.",
  anchors:["явно заданный инвариант","обнаруживает его подмену"],
  variants:[
    {label:"Сохранение",text:"Через разные формы представления цифровой продукт проводит явно заданный инвариант и обнаруживает его подмену."},
    {label:"Смысловой сдвиг",text:"В проектной работе явно заданный инвариант служит ориентиром, а экспертная проверка обнаруживает его подмену."},
    {label:"Подмена",text:"Программа автоматически доказывает истинность любой научной теории без участия человека."},
  ],
};

function setStatus(text,tone="idle"){status.textContent=text;status.dataset.tone=tone}
function escapeHtml(value){return String(value).replace(/[&<>"']/g,(char)=>({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;","'":"&#39;"}[char]))}
function download(name,content,type){const url=URL.createObjectURL(new Blob([content],{type}));Object.assign(document.createElement("a"),{href:url,download:name}).click();URL.revokeObjectURL(url)}
function enableExports(){exportJson.disabled=false;exportMarkdown.disabled=false}
function fieldControl(field,value){
  const tag=field==="axisDefinition"?"textarea":"input";
  return `<label class="field"><span>${labels[field]}</span><${tag} data-field="${field}" ${tag==="input"?'type="text"':""}>${tag==="textarea"?escapeHtml(value):""}</${tag}></label>`;
}
function renderSource(invariant){
  sourceHost.innerHTML=fields.map(field=>fieldControl(field,invariant[field]||"")).join("");
  fields.filter(f=>f!=="axisDefinition").forEach(field=>sourceHost.querySelector(`[data-field="${field}"]`).value=invariant[field]||"");
}
function sourceInvariant(){return Object.fromEntries(fields.map(field=>[field,sourceHost.querySelector(`[data-field="${field}"]`).value.trim()]))}
function formCard(form,kind="positive"){
  const card=document.createElement("article");card.className="form-card";
  card.innerHTML=`<div class="form-card-head"><input class="form-label" value="${escapeHtml(form.label||"Новая форма")}" aria-label="Название формы"><button class="remove ghost" title="Удалить">×</button></div>
  <div class="form-meta"><select class="geometry">${geometries.map(g=>`<option ${g===(form.representation?.geometry||"Euclid")?"selected":""}>${g}</option>`).join("")}</select><select class="kind"><option value="positive" ${kind==="positive"?"selected":""}>Положительная форма</option><option value="negative" ${kind==="negative"?"selected":""}>Отрицательный контроль</option></select></div>
  <label class="field compact"><span>Осевое определение этой формы</span><textarea class="form-definition">${escapeHtml(form.invariant?.axisDefinition||sourceInvariant().axisDefinition)}</textarea></label>`;
  card.querySelector(".remove").onclick=()=>{card.remove();saveDraft()};
  card.querySelectorAll("input,textarea,select").forEach(el=>el.addEventListener("input",saveDraft));
  formsHost.append(card);
}
function payloadFromBuilder(){
  const invariant=sourceInvariant(), forms=[], negativeControls=[];
  formsHost.querySelectorAll(".form-card").forEach(card=>{
    const item={label:card.querySelector(".form-label").value.trim(),representation:{geometry:card.querySelector(".geometry").value,model:"visual-builder"},invariant:{...invariant,axisDefinition:card.querySelector(".form-definition").value.trim()}};
    (card.querySelector(".kind").value==="negative"?negativeControls:forms).push(item);
  });
  return {source:{invariant},forms,negativeControls};
}
function loadBuilder(payload){
  renderSource(payload.source?.invariant||payload.source||{});
  formsHost.innerHTML="";
  (payload.forms||[]).forEach(form=>formCard(form,"positive"));
  (payload.negativeControls||[]).forEach(form=>formCard(form,"negative"));
  saveDraft();
}
function saveDraft(){try{localStorage.setItem("tzar-product-001-draft",JSON.stringify(payloadFromBuilder()))}catch{}}
function render(report){
  const items=[...report.positive,...report.negative];
  result.innerHTML=`<div class="summary ${report.pass?"pass":"fail"}"><span class="summary-mark">${report.pass?"⊕":"×"}</span><div><small>Результат контура</small><strong>${report.pass?"ПРОВОДИМ":"ОБНАРУЖЕН РАЗРЫВ"}</strong><code class="seal" title="${report.seal}">печать · ${report.seal.slice(0,16)}…</code></div></div>
  <div class="ledger-head"><small>ХРОНОС ПЕРЕХОДОВ</small><span>${report.firstBreak?`первый разрыв: шаг ${report.firstBreak.index}`:"цепь непрерывна"}</span></div>
  <div class="ledger">${report.ledger.map(entry=>`<div class="transition ${entry.continuous?"pass":"fail"}"><b>${String(entry.index).padStart(2,"0")}</b><div><span>${escapeHtml(entry.label)} · ${entry.geometry}</span><code title="${entry.transitionHash}">${entry.transitionHash.slice(0,12)}…</code></div><em>${entry.continuous?"→":"×"}</em></div>`).join("")}</div>
  <div class="chain">${items.map((item,index)=>`<article class="node ${item.pass?"pass":"fail"}"><div class="node-top"><span>${String(index+1).padStart(2,"0")}</span><b>${item.pass?"PASS":"FAIL"}</b></div><h3>${escapeHtml(item.label)}</h3><p>${item.geometry} · ${item.kind==="negative"?"отрицательный контроль":"положительная форма"}</p><code title="${item.hash}">${item.hash.slice(0,16)}…</code>${item.differences.length?`<div class="diffs">${item.differences.map(diff=>`<div><b>${labels[diff.field]||diff.field}</b><span>ожидалось: ${escapeHtml(diff.expected)}</span><span>получено: ${escapeHtml(diff.actual)}</span></div>`).join("")}</div>`:""}</article>`).join("")}</div>`;
}

function semanticVariantCard(variant={}){
  const card=document.createElement("article");card.className="form-card semantic-card";
  card.innerHTML=`<div class="form-card-head"><input class="form-label" value="${escapeHtml(variant.label||"Новый вариант")}" aria-label="Название варианта"><button class="remove ghost" title="Удалить">×</button></div><label class="field compact"><span>Преобразованный текст</span><textarea class="variant-text" placeholder="Выразите исходную мысль в другой форме">${escapeHtml(variant.text||"")}</textarea></label>`;
  card.querySelector(".remove").onclick=()=>{card.remove();saveSemanticDraft()};
  card.querySelectorAll("input,textarea").forEach(node=>node.addEventListener("input",saveSemanticDraft));
  $("#semantic-variants").append(card);
}

function loadSemantic(data){
  $("#semantic-source").value=data.source||"";
  $("#semantic-anchors").value=(data.anchors||[]).join("\n");
  $("#semantic-variants").innerHTML="";
  (data.variants||[]).forEach(semanticVariantCard);
}

function semanticDraft(){
  return {source:$("#semantic-source").value,anchors:parseAnchors($("#semantic-anchors").value),variants:[...document.querySelectorAll(".semantic-card")].map(card=>({label:card.querySelector(".form-label").value,text:card.querySelector(".variant-text").value}))};
}

function saveSemanticDraft(){
  try{localStorage.setItem("tzar-product-001-semantic-draft",JSON.stringify(semanticDraft()))}catch{}
}

function loadSemanticExample(){
  loadSemantic(semanticExample);saveSemanticDraft();
}

function semanticPayload(){
  const source=$("#semantic-source").value.trim();
  const anchors=parseAnchors($("#semantic-anchors").value);
  const variants=[...document.querySelectorAll(".semantic-card")].map(card=>({label:card.querySelector(".form-label").value.trim(),text:card.querySelector(".variant-text").value.trim()}));
  if(!source)throw new Error("Введите исходную мысль");
  if(variants.length<1)throw new Error("Добавьте хотя бы один вариант преобразования");
  if(variants.some(item=>!item.text))throw new Error("Каждый вариант должен содержать текст");
  return {source,anchors,variants};
}

function renderSemantic(report){
  const counts=report.items.reduce((acc,item)=>{acc[item.verdict.code]=(acc[item.verdict.code]||0)+1;return acc},{});
  const hasSignals=counts["critical-break"]||counts.rupture||counts["logical-risk"];
  const totalChunks=report.chunkCounts.reduce((sum,count)=>sum+count,0);
  result.innerHTML=`<div class="summary semantic-summary"><span class="summary-mark">≈</span><div><small>${report.items.length} преобразования · ${totalChunks} смысловых блоков</small><strong>${hasSignals?"ЕСТЬ СИГНАЛЫ ДЛЯ ПРОВЕРКИ":"ОЦЕНКА ПОСТРОЕНА"}</strong><code class="seal" title="${report.seal}">печать · ${report.seal.slice(0,16)}…</code></div></div>
  <div class="calibration"><span>ОПЕРАЦИОННАЯ КАЛИБРОВКА β</span><p>cos ≥ ${report.thresholds.preserved.toFixed(2)} · зона различения ≥ ${report.thresholds.review.toFixed(2)} · не является процентом смысла</p></div>
  <div class="semantic-results">${report.items.map((item,index)=>`<article class="semantic-result ${item.verdict.tone}"><div class="score"><span>${String(index+1).padStart(2,"0")}</span><strong>${item.similarity.toFixed(3)}<small>cos</small></strong></div><div class="semantic-result-body"><div class="verdict-row"><h3>${escapeHtml(item.label)}</h3><b>${item.verdict.label}</b></div><p>${escapeHtml(item.verdict.explanation)}</p><div class="meter"><i style="width:${Math.max(0,item.similarity*100)}%"></i></div><div class="anchor-map"><span>Точные опоры ${item.anchors.present.length}/${item.anchors.required.length}</span>${item.anchors.missing.map(anchor=>`<code>не найдено: ${escapeHtml(anchor)}</code>`).join("")}</div>${item.logicRisks.length?`<div class="logic-map"><b>Логические предупреждения</b>${item.logicRisks.map(risk=>`<code class="${risk.severity}">${escapeHtml(risk.label)} · ${risk.explanation}</code>`).join("")}</div>`:""}<div class="lexical-map"><span>Лексическая карта</span>${item.lexical.removed.length?`<code class="removed">исчезли: ${escapeHtml(item.lexical.removed.join(", "))}</code>`:""}${item.lexical.added.length?`<code class="added">появились: ${escapeHtml(item.lexical.added.join(", "))}</code>`:""}</div></div></article>`).join("")}</div>
  <div class="method-note"><b>Граница вывода</b><p>Коэффициент показывает близость векторов конкретной модели, а не долю сохранённого смысла. Логические предупреждения и лексическая карта помогают человеку проверить причину результата.</p></div>`;
}

function analyzeInWorker(texts,onProgress){
  return new Promise((resolve,reject)=>{
    const worker=new Worker(new URL("./semantic-worker.mjs",import.meta.url),{type:"module"});
    semanticWorker=worker;
    cancelSemanticJob=()=>{worker.terminate();semanticWorker=null;cancelSemanticJob=null;const error=new Error("Вычисление отменено пользователем");error.name="AbortError";reject(error)};
    worker.onmessage=(event)=>{
      if(event.data?.type==="progress")onProgress(event.data.message);
      if(event.data?.type==="result"){worker.terminate();semanticWorker=null;cancelSemanticJob=null;resolve({vectors:event.data.vectors,chunkCounts:event.data.chunkCounts})}
      if(event.data?.type==="error"){worker.terminate();semanticWorker=null;cancelSemanticJob=null;reject(new Error(event.data.message))}
    };
    worker.onerror=(event)=>{worker.terminate();semanticWorker=null;cancelSemanticJob=null;reject(new Error(event.message||"Фоновый поток модели завершился с ошибкой"))};
    worker.postMessage({type:"analyze",texts});
  });
}

async function runSemantic(){
  const button=$("#analyze-semantic");
  try{
    const payload=semanticPayload();
    saveSemanticDraft();
    button.dataset.running="true";button.querySelector("span").textContent="Отменить вычисление";button.querySelector("b").textContent="×";
    setStatus("Подготовка модели…","work");
    result.innerHTML='<div class="model-loading"><span></span><strong>Запуск локального смыслового ядра</strong><p id="model-progress">Первая загрузка может занять некоторое время.</p></div>';
    const embedded=await analyzeInWorker([payload.source,...payload.variants.map(item=>item.text)],message=>{const node=$("#model-progress");if(node)node.textContent=message;setStatus(message,"work")});
    const vectors=embedded.vectors;
    const items=buildSemanticItems(payload.source,payload.variants,vectors,payload.anchors,SEMANTIC_THRESHOLDS);
    currentReport=await sealReport({schema:"tzar-semantic-report/0.2.0",product:"TZAR-PRODUCT-001",mode:"semantic-audit-beta",model:SEMANTIC_MODEL,modelRevision:SEMANTIC_MODEL_REVISION,transformers:"4.0.1",generatedAt:new Date().toISOString(),source:payload.source,anchors:payload.anchors,thresholds:SEMANTIC_THRESHOLDS,chunkCounts:embedded.chunkCounts,items});
    currentReportKind="semantic";
    renderSemantic(currentReport);enableExports();
    const hasSignal=items.some(item=>item.verdict.tone!=="pass");
    setStatus(hasSignal?"Нужна ручная проверка":"Высокая модельная близость",hasSignal?"review":"pass");
  }catch(error){
    currentReport=null;exportJson.disabled=true;exportMarkdown.disabled=true;
    if(error.name==="AbortError"){result.innerHTML='<div class="empty">Вычисление отменено. Введённые тексты сохранены в браузере.</div>';setStatus("Вычисление отменено","idle")}
    else{result.innerHTML=`<div class="error"><strong>Смысловая проверка не выполнена</strong><p>${escapeHtml(error.message)}</p><p>Проверьте соединение при первой загрузке модели и повторите запуск.</p></div>`;setStatus("Смысловой контур недоступен","fail")}
  }finally{button.dataset.running="false";button.querySelector("span").textContent="Провести смысл через контур";button.querySelector("b").textContent="→"}
}
async function run(payload=payloadFromBuilder()){
  try{setStatus("Проверка…","work");currentReport=await verifyPayload(payload);currentReportKind="structural";render(currentReport);enableExports();input.value=JSON.stringify(payload,null,2);saveDraft();setStatus(currentReport.pass?"Контур проводим":"Контур разорван",currentReport.pass?"pass":"fail")}
  catch(error){currentReport=null;result.innerHTML=`<div class="error"><strong>Невозможно выполнить проверку</strong><p>${escapeHtml(error.message)}</p></div>`;exportJson.disabled=true;exportMarkdown.disabled=true;setStatus("Ошибка входа","fail")}
}
function switchMode(mode){document.body.dataset.mode=mode;document.querySelectorAll(".mode").forEach(b=>b.classList.toggle("active",b.dataset.mode===mode));$("#output-title").textContent=mode==="semantic"?"Карта смысловой проводимости":"Карта структурной проводимости";if(mode==="json")input.value=JSON.stringify(payloadFromBuilder(),null,2)}

$("#verify").onclick=()=>run();
$("#analyze-semantic").onclick=()=>cancelSemanticJob?cancelSemanticJob():runSemantic();
$("#semantic-example").onclick=()=>loadSemanticExample();
$("#add-variant").onclick=()=>{semanticVariantCard();saveSemanticDraft()};
$("#verify-json").onclick=()=>{try{const payload=JSON.parse(input.value);loadBuilder(payload);run(payload)}catch(error){setStatus("Ошибка JSON","fail");result.innerHTML=`<div class="error"><strong>JSON не прочитан</strong><p>${escapeHtml(error.message)}</p></div>`}};
$("#example").onclick=()=>{loadBuilder(structuredClone(example));run()};
$("#reset").onclick=()=>{loadBuilder(structuredClone(example));setStatus("Пример восстановлен")};
$("#add-form").onclick=()=>formCard({label:"Новая форма",representation:{geometry:"Euclid"},invariant:sourceInvariant()},"positive");
$("#add-negative").onclick=()=>formCard({label:"Отрицательный контроль",representation:{geometry:"Projective"},invariant:{...sourceInvariant(),axisDefinition:sourceInvariant().axisDefinition+" [изменено]"}},"negative");
$("#verify-passport").onclick=()=>passportFile.click();
passportFile.onchange=async()=>{
  const file=passportFile.files[0];if(!file)return;
  try{
    const passport=JSON.parse(await file.text());
    const check=await verifyReportSeal(passport);
    passportStatus.className=`passport-status ${check.valid?"pass":"fail"}`;
    passportStatus.innerHTML=`<b>${check.valid?"ПАСПОРТ ЦЕЛ":"ПАСПОРТ ИЗМЕНЁН"}</b><span>${escapeHtml(check.reason)}</span><code>${escapeHtml((check.calculated||"").slice(0,20))}…</code>`;
    setStatus(check.valid?"Паспорт проверен":"Подмена паспорта",check.valid?"pass":"fail");
  }catch(error){
    passportStatus.className="passport-status fail";
    passportStatus.innerHTML=`<b>ПАСПОРТ НЕ ПРОЧИТАН</b><span>${escapeHtml(error.message)}</span>`;
  }finally{passportFile.value=""}
};
document.querySelectorAll(".mode").forEach(button=>button.onclick=()=>switchMode(button.dataset.mode));
exportJson.onclick=()=>download(currentReportKind==="semantic"?"tzar-semantic-report.json":"tzar-conductance-report.json",JSON.stringify(currentReport,null,2),"application/json");
exportMarkdown.onclick=()=>download(currentReportKind==="semantic"?"tzar-semantic-report.md":"tzar-conductance-report.md",currentReportKind==="semantic"?semanticReportMarkdown(currentReport):reportMarkdown(currentReport),"text/markdown");
sourceHost.addEventListener("input",saveDraft);
$("#semantic-source").addEventListener("input",saveSemanticDraft);
$("#semantic-anchors").addEventListener("input",saveSemanticDraft);

let initial=example;try{const saved=localStorage.getItem("tzar-product-001-draft");if(saved)initial=JSON.parse(saved)}catch{}
loadBuilder(structuredClone(initial));
let initialSemantic=semanticExample;try{const saved=localStorage.getItem("tzar-product-001-semantic-draft");if(saved)initialSemantic=JSON.parse(saved)}catch{}
loadSemantic(initialSemantic);
switchMode("semantic");
currentReport=null;exportJson.disabled=true;exportMarkdown.disabled=true;
result.innerHTML='<div class="empty">Исходная мысль и три преобразования уже загружены. Запустите смысловую проверку.</div>';
setStatus("Смысловой контур готов","idle");
