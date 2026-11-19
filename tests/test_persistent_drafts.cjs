const test = require('node:test');
const assert = require('node:assert/strict');
const {createPersistentDraftStore} = require('../workbench/static/draft-state.js');

const sleep = ms => new Promise(resolve => setTimeout(resolve, ms));
function deferred() { let resolve, reject; const promise = new Promise((yes, no) => {resolve=yes;reject=no;}); return {promise,resolve,reject}; }
async function until(check) { for (let i=0; i<100; i++) {if(check()) return; await sleep(5);} assert.ok(check(), 'state did not settle'); }
const args = ['main','project-one','SAVE_PRODUCTION_REQUEST'];
function remoteHarness() {
  const records = new Map(); const calls = [];
  const key = v => JSON.stringify([v.account_id,v.video_id,v.action]);
  const request = async (url, options) => {
    calls.push({url,options});
    const body = options ? JSON.parse(options.body) : Object.fromEntries(new URL(url,'http://localhost').searchParams);
    const current = records.get(key(body)) || {values:{},version:0,updated_at:null};
    if (!options) return structuredClone(current);
    assert.equal(url, '/api/drafts/save');
    if(body.expected_version!==current.version) throw Object.assign(new Error('conflict'), {code:'DRAFT_CONFLICT',current:structuredClone(current)});
    const saved = {values:body.values,version:current.version+1,updated_at:'2026-09-28T12:00:00+08:00'};
    records.set(key(body), saved); return structuredClone(saved);
  };
  return {records,calls,request,store: () => createPersistentDraftStore(request,{delay:5})};
}

test('a new store restores previously saved drafts after reload, without submitting a generation job', async () => {
  const h=remoteHarness(); const first=h.store(); first.open(...args);
  await until(()=>first.state(...args).loaded);
  first.set(...args,{prompt:'雨后海岸',image_count:1,asset_ids:[]}); await first.flushAll();
  assert.equal(first.state(...args).dirty,false);
  const refreshed=h.store(); refreshed.open(...args,{prompt:'old default'});
  await until(()=>refreshed.state(...args).loaded);
  assert.deepEqual(refreshed.get(...args),{prompt:'雨后海岸',image_count:1,asset_ids:[]});
  assert.equal(refreshed.state(...args).version,1);
  assert.ok(h.calls.every(call=>call.url.startsWith('/api/drafts')));
});

test('account, project and action keys persist independently', async () => {
  const h=remoteHarness(); const store=h.store();
  const keys=[args,['second',args[1],args[2]],[args[0],'project-two',args[2]],[args[0],args[1],'PROBE_MEDIA']];
  for(let i=0;i<keys.length;i++) {store.open(...keys[i]); await until(()=>store.state(...keys[i]).loaded); store.set(...keys[i],{prompt:String(i)});}
  await store.flushAll();
  for(let i=0;i<keys.length;i++) assert.deepEqual(store.get(...keys[i]),{prompt:String(i)});
  assert.equal(h.records.size,4);
});

test('loading a draft cannot overwrite typing or deliberate empty values entered during loading', async () => {
  const response=deferred(); const h=remoteHarness();
  const remote={values:{prompt:'remote',image_count:12,asset_ids:['remote']},version:1};
  h.records.set(JSON.stringify(args),remote);
  const store=createPersistentDraftStore((url,options)=>options?h.request(url,options):response.promise,{delay:5});
  store.open(...args,{prompt:'initial',image_count:6,asset_ids:['old']});
  store.set(...args,{prompt:'',image_count:6,asset_ids:[]});
  response.resolve(remote);
  await until(()=>store.state(...args).loaded);
  assert.equal(store.get(...args).prompt,''); assert.deepEqual(store.get(...args).asset_ids,[]);
  assert.equal(store.get(...args).image_count,12);
  await store.flushAll();
});

test('edits during an in-flight save survive and are sent with the new version', async () => {
  const h=remoteHarness(); const pending=deferred(); let first=true;
  const store=createPersistentDraftStore(async(url,options)=>{
    if(options && first) {first=false; await pending.promise;}
    return h.request(url,options);
  },{delay:5});
  store.open(...args); await until(()=>store.state(...args).loaded);
  store.set(...args,{prompt:'A'}); const saving=store.flushAll();
  await until(()=>store.state(...args).status==='saving');
  store.set(...args,{prompt:'B'}); pending.resolve(); await saving;
  await until(()=>store.state(...args).status==='saved');
  assert.deepEqual(store.get(...args),{prompt:'B'});
  const posts=h.calls.filter(c=>c.options).map(c=>JSON.parse(c.options.body));
  assert.deepEqual(posts.map(p=>[p.values.prompt,p.expected_version]),[['A',0],['B',1]]);
});

test('failed save retains values and explicit retry recovers without background retry storms', async () => {
  const h=remoteHarness(); let failed=true; let postCount=0;
  const store=createPersistentDraftStore(async(url,options)=>{
    if(options) {postCount++; if(failed) throw new Error('offline');}
    return h.request(url,options);
  },{delay:5});
  store.open(...args); await until(()=>store.state(...args).loaded);
  store.set(...args,{prompt:'keep me'}); await store.flushAll();
  assert.equal(store.state(...args).status,'error'); assert.equal(store.hasUnsaved(),true);
  await sleep(30); assert.equal(postCount,1);
  failed=false; await store.retry(...args);
  assert.equal(store.state(...args).status,'saved'); assert.deepEqual(store.get(...args),{prompt:'keep me'});
});

test('two-tab conflict preserves local text until the user chooses remote', async () => {
  const h=remoteHarness(); const first=h.store(); const second=h.store();
  first.open(...args); second.open(...args); await until(()=>first.state(...args).loaded&&second.state(...args).loaded);
  first.set(...args,{prompt:'remote winner'}); await first.flushAll();
  second.set(...args,{prompt:'local unsaved'}); await second.flushAll();
  assert.equal(second.state(...args).status,'conflict'); assert.deepEqual(second.get(...args),{prompt:'local unsaved'});
  const count=h.calls.length; await sleep(30); assert.equal(h.calls.length,count);
  await second.resolve(...args,'remote');
  assert.deepEqual(second.get(...args),{prompt:'remote winner'}); assert.equal(second.hasUnsaved(),false);
});

test('explicit keep-local conflict choice uses the latest remote version', async () => {
  const h=remoteHarness(); const first=h.store(); const second=h.store();
  first.open(...args); second.open(...args); await until(()=>first.state(...args).loaded&&second.state(...args).loaded);
  first.set(...args,{prompt:'A'}); await first.flushAll(); second.set(...args,{prompt:'B'}); await second.flushAll();
  await second.resolve(...args,'local');
  assert.equal(second.state(...args).status,'saved'); assert.equal(second.state(...args).version,2);
  assert.deepEqual(second.get(...args),{prompt:'B'});
});

test('late hydrate of old project does not change the active project data', async () => {
  const pending=deferred(); const other=['main','project-two',args[2]];
  const store=createPersistentDraftStore(url=>url.includes('project-one')?pending.promise:Promise.resolve({values:{prompt:'new'},version:1}),{delay:5});
  store.open(...args); store.open(...other); await until(()=>store.state(...other).loaded);
  pending.resolve({values:{prompt:'old'},version:1}); await until(()=>store.state(...args).loaded);
  assert.deepEqual(store.get(...other),{prompt:'new'}); assert.deepEqual(store.get(...args),{prompt:'old'});
});
