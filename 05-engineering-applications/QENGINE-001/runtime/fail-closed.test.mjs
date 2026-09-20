import test from 'node:test';
import assert from 'node:assert/strict';
import { runEngine } from '../../../products/tzar-conductance/qengine/qengine.mjs';
const invariant={invariant:'sigma',author:'A',version:'0.2.0',source:'source',seal:'seal',provenance:['p1'],invariantCriteria:[{verdict:'preserved'}]};
const integrity={integrityEvidence:{sealVerified:true,signatureVerified:true,signerTrusted:true}};
const geometry={construct:'C',sourceGeometry:'Gᴱ',targetGeometry:'Gᴾ',representationProfile:'visual-rendering',invariantCriterion:'sigma',transitionRule:'T',targetForm:'F',invariantEvidence:['e1']};
const clock={phase:'arm',timeSource:'clock',issuedAt:'2026-09-20T00:00:00Z',expiresAt:'2026-09-20T00:01:00Z',nonce:'n1',idempotencyKey:'i1'};
const timePolicy={trustedTimeSources:['clock'],maxClockSkewMs:1000,maxTtlMs:120000};
const environment=()=>({nowMs:()=>Date.parse(clock.issuedAt),nonceStore:new Set()});

test('required signature cannot be replaced by trusted flags without a signature',()=>{
  for(const signature of [undefined,null,'','   ']) {
    const result=runEngine('QI-01',{...invariant,signature},integrity,{requireSignature:true,compatibleVersions:['0.2.0']});
    assert.equal(result.outcome,'denied');assert.equal(result.error.code,'SIGNATURE_INVALID');
  }
});
test('unsigned invariant remains allowed only when signature is optional',()=>{
  assert.equal(runEngine('QI-01',invariant,integrity,{requireSignature:false,compatibleVersions:['0.2.0']}).outcome,'completed');
});
test('zero transition budget denies a transition rather than becoming one',()=>{
  const r=runEngine('QG-01',geometry,{preflightInvariantVerdict:'preserved'},{allowedTransitions:['Gᴱ→Gᴾ'],transitionBudget:0});
  assert.equal(r.error.code,'TRANSITION_BUDGET_EXCEEDED');
});
test('invalid transition counts and budgets never complete',()=>{
  for(const value of [undefined,null,'1',-1,NaN,Infinity,.5]){
    assert.notEqual(runEngine('QG-01',geometry,{preflightInvariantVerdict:'preserved'},{allowedTransitions:['Gᴱ→Gᴾ'],transitionBudget:value}).outcome,'completed');
  }
  for(const value of [null,'1',0,-1,NaN,Infinity,.5]){
    const r=runEngine('QG-01',{...geometry,transitionCount:value},{preflightInvariantVerdict:'preserved'},{allowedTransitions:['Gᴱ→Gᴾ'],transitionBudget:1});
    assert.notEqual(r.outcome,'completed');
  }
});
test('nonfinite clocks fail before consuming the nonce',()=>{
  for(const now of [NaN,Infinity,'2026-09-20',null]){
    const env=environment();env.nowMs=()=>now;
    assert.equal(runEngine('QC-01',clock,{cleanupHandlerId:'cleanup'},timePolicy,env).error.code,'CLOCK_UNTRUSTED');
    assert.equal(env.nonceStore.size,0);
  }
});
test('malformed clock policies cannot bypass TTL and skew checks',()=>{
  for(const key of ['maxClockSkewMs','maxTtlMs'])for(const value of [undefined,null,'invalid','120000',-1,NaN,Infinity]){
    const env=environment();const result=runEngine('QC-01',clock,{cleanupHandlerId:'cleanup'},{...timePolicy,[key]:value},env);
    assert.equal(result.error.code,'CHRONOS_POLICY_INVALID');assert.equal(env.nonceStore.size,0);
  }
});
test('valid time policy preserves arm and replay denial',()=>{
  const env=environment();assert.equal(runEngine('QC-01',clock,{cleanupHandlerId:'cleanup'},timePolicy,env).outcome,'completed');
  assert.equal(runEngine('QC-01',clock,{cleanupHandlerId:'cleanup'},timePolicy,env).error.code,'NONCE_REUSED');
});
test('all engines return structured rejection for non-object JSON inputs',()=>{
  for(const id of ['QP-01','QR-01','QG-01','QA-01','QC-01','QI-01'])for(const value of [null,[],1,'text']){
    assert.equal(runEngine(id,value).error.code,'ENGINE_INPUT_INVALID');
    assert.equal(runEngine(id,{},value).error.code,'ENGINE_INPUT_INVALID');
    assert.equal(runEngine(id,{},{},value).error.code,'ENGINE_INPUT_INVALID');
  }
});
test('declared load needs numeric capacity, including valid zero',()=>{
  const req={subjectStructure:'S',fieldStructure:'F',point:'P',geometry:'Gᴿ',criteria:[{id:'c',match:true}],metrics:{alpha:1,iy:1,cm:1,q:1,t:1},requiredLoad:1};
  for(const value of [undefined,null,'2',NaN,Infinity,-1]) assert.equal(runEngine('QR-01',req,{},{containerCapacity:value}).error.code,'RESONANCE_CAPACITY_INVALID');
  assert.equal(runEngine('QR-01',req,{},{containerCapacity:0}).error.code,'RESONANCE_OVERLOAD');
});
