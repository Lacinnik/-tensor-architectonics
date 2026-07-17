import { reportMarkdown, verifyPayload } from "./core.mjs";
import { example } from "./example.mjs";

const fields = ["constructId", "author", "axisTerm", "axisDefinition", "version", "status"];
const labels = { constructId:"ID конструкта",author:"Автор",axisTerm:"Осевой термин",axisDefinition:"Осевое определение",version:"Версия",status:"Статус" };
const geometries = ["Euclid","Lobachevsky","Riemann","Projective","Supra"];
const $ = (selector) => document.querySelector(selector);
const input=$("#payload"), result=$("#result"), status=$("#status"), formsHost=$("#forms"), sourceHost=$("#source-fields");
const exportJson=$("#export-json"), exportMarkdown=$("#export-markdown");
let currentReport=null;

function setStatus(text,tone="idle"){status.textContent=text;status.dataset.tone=tone}
function escapeHtml(value){return String(value).replace(/[&<>"']/g,(char)=>({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;","'":"&#39;"}[char]))}
function download(name,content,type){const url=URL.createObjectURL(new Blob([content],{type}));Object.assign(document.createElement("a"),{href:url,download:name}).click();URL.revokeObjectURL(url)}
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
  result.innerHTML=`<div class="summary ${report.pass?"pass":"fail"}"><span class="summary-mark">${report.pass?"⊕":"×"}</span><div><small>Результат контура</small><strong>${report.pass?"ПРОВОДИМ":"ОБНАРУЖЕН РАЗРЫВ"}</strong></div></div>
  <div class="ledger-head"><small>ХРОНОС ПЕРЕХОДОВ</small><span>${report.firstBreak?`первый разрыв: шаг ${report.firstBreak.index}`:"цепь непрерывна"}</span></div>
  <div class="ledger">${report.ledger.map(entry=>`<div class="transition ${entry.continuous?"pass":"fail"}"><b>${String(entry.index).padStart(2,"0")}</b><div><span>${escapeHtml(entry.label)} · ${entry.geometry}</span><code title="${entry.transitionHash}">${entry.transitionHash.slice(0,12)}…</code></div><em>${entry.continuous?"→":"×"}</em></div>`).join("")}</div>
  <div class="chain">${items.map((item,index)=>`<article class="node ${item.pass?"pass":"fail"}"><div class="node-top"><span>${String(index+1).padStart(2,"0")}</span><b>${item.pass?"PASS":"FAIL"}</b></div><h3>${escapeHtml(item.label)}</h3><p>${item.geometry} · ${item.kind==="negative"?"отрицательный контроль":"положительная форма"}</p><code title="${item.hash}">${item.hash.slice(0,16)}…</code>${item.differences.length?`<div class="diffs">${item.differences.map(diff=>`<div><b>${labels[diff.field]||diff.field}</b><span>ожидалось: ${escapeHtml(diff.expected)}</span><span>получено: ${escapeHtml(diff.actual)}</span></div>`).join("")}</div>`:""}</article>`).join("")}</div>`;
}
async function run(payload=payloadFromBuilder()){
  try{setStatus("Проверка…","work");currentReport=await verifyPayload(payload);render(currentReport);exportJson.disabled=false;exportMarkdown.disabled=false;input.value=JSON.stringify(payload,null,2);saveDraft();setStatus(currentReport.pass?"Контур проводим":"Контур разорван",currentReport.pass?"pass":"fail")}
  catch(error){currentReport=null;result.innerHTML=`<div class="error"><strong>Невозможно выполнить проверку</strong><p>${escapeHtml(error.message)}</p></div>`;exportJson.disabled=true;exportMarkdown.disabled=true;setStatus("Ошибка входа","fail")}
}
function switchMode(mode){document.body.dataset.mode=mode;document.querySelectorAll(".mode").forEach(b=>b.classList.toggle("active",b.dataset.mode===mode));if(mode==="json")input.value=JSON.stringify(payloadFromBuilder(),null,2)}

$("#verify").onclick=()=>run();
$("#verify-json").onclick=()=>{try{const payload=JSON.parse(input.value);loadBuilder(payload);run(payload)}catch(error){setStatus("Ошибка JSON","fail");result.innerHTML=`<div class="error"><strong>JSON не прочитан</strong><p>${escapeHtml(error.message)}</p></div>`}};
$("#example").onclick=()=>{loadBuilder(structuredClone(example));run()};
$("#reset").onclick=()=>{loadBuilder(structuredClone(example));setStatus("Пример восстановлен")};
$("#add-form").onclick=()=>formCard({label:"Новая форма",representation:{geometry:"Euclid"},invariant:sourceInvariant()},"positive");
$("#add-negative").onclick=()=>formCard({label:"Отрицательный контроль",representation:{geometry:"Projective"},invariant:{...sourceInvariant(),axisDefinition:sourceInvariant().axisDefinition+" [изменено]"}},"negative");
document.querySelectorAll(".mode").forEach(button=>button.onclick=()=>switchMode(button.dataset.mode));
exportJson.onclick=()=>download("tzar-conductance-report.json",JSON.stringify(currentReport,null,2),"application/json");
exportMarkdown.onclick=()=>download("tzar-conductance-report.md",reportMarkdown(currentReport),"text/markdown");
sourceHost.addEventListener("input",saveDraft);

let initial=example;try{const saved=localStorage.getItem("tzar-product-001-draft");if(saved)initial=JSON.parse(saved)}catch{}
loadBuilder(structuredClone(initial));run();
