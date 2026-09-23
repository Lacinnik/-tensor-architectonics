import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import vm from 'node:vm';

// Execute the shipped event handlers with DOM/storage doubles.
class Control {
  constructor(id) {
    this.id=id;this.name=id;this.value='';this.checked=false;this.type='text';
    this.dataset={};this.events={};
    this.classList={add(){},remove(){},toggle(){}};
  }
  addEventListener(name,fn){this.events[name]=fn;}
  setAttribute(){} removeAttribute(){} closest(){return null;}
  querySelector(){return null;} querySelectorAll(){return [];}
}
const controls=new Map(),data=new Map();
const get=id=>{if(!controls.has(id))controls.set(id,new Control(id));return controls.get(id);};
const groups=Object.fromEntries([['[data-step]',6],['[data-jump]',6],['[data-geometry-tab]',5],['[data-geometry-panel]',5]].map(([key,n])=>[key,Array.from({length:n},(_,i)=>get(key+i))]));
for(const id of ['confirmCandidate','saveDraft'])get(id).type='checkbox';
Object.defineProperty(get('ego-form'),'elements',{get:()=>[...controls.values()]});
const context={document:{getElementById:get,querySelectorAll:key=>groups[key]||[]},location:{search:''},
  URLSearchParams,HTMLInputElement:Control,HTMLTextAreaElement:Control,HTMLSelectElement:Control,
  setTimeout(){},clearTimeout(){},localStorage:{getItem:k=>data.get(k)||null,setItem:(k,v)=>data.set(k,v),removeItem:k=>data.delete(k)},
  TzarEgoCore:{synthesizeCandidate:()=> 'Новая проверяемая формулировка'},
};
vm.runInNewContext(readFileSync(new URL('./app.js',import.meta.url),'utf8'),context);
get('saveDraft').checked=true;
get('confirmCandidate').checked=true;
get('trueRequest').value='Изменённая формулировка автора';
get('ego-form').events.input({target:get('trueRequest')});
assert.equal(get('confirmCandidate').checked,false);
assert.equal(JSON.parse(data.get('tzar.ego-interface.draft.v1')).confirmCandidate,false);
get('confirmCandidate').checked=true;
get('ego-form').events.input({target:get('confirmCandidate')});
assert.equal(get('confirmCandidate').checked,true,'explicit confirmation remains possible');
get('generate-candidate').events.click();
assert.equal(get('trueRequest').value,'Новая проверяемая формулировка');
assert.equal(get('confirmCandidate').checked,false);
assert.equal(JSON.parse(data.get('tzar.ego-interface.draft.v1')).confirmCandidate,false);
console.log('✓ candidate edits and regeneration revoke previous confirmation before draft persistence');
