const test = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');
const {createDraftStore, fieldValue, projectJobs, sameInputs} = require('../workbench/static/draft-state.js');

test('drafts are isolated by account, project and action, with defensive copies', () => {
  const store = createDraftStore();
  const values = {prompt:'雨后的街道 🌧️', asset_ids:['a']};
  store.set('main', 'one', 'SAVE', values);
  values.asset_ids.push('b');
  assert.deepEqual(store.get('main', 'one', 'SAVE').asset_ids, ['a']);
  for (const args of [['other','one','SAVE'], ['main','two','SAVE'], ['main','one','PROBE']]) {
    assert.equal(store.get(...args), null);
  }
  store.get('main', 'one', 'SAVE').asset_ids.push('c');
  assert.deepEqual(store.get('main', 'one', 'SAVE').asset_ids, ['a']);
  store.remove('main', 'one', 'SAVE');
  assert.equal(store.get('main', 'one', 'SAVE'), null);
});

test('field precedence preserves empty inputs, zero, and deliberate asset deselection', () => {
  assert.equal(fieldValue({name:'prompt'}, {prompt:''}, {prompt:'saved'}), '');
  assert.equal(fieldValue({name:'count',default:6}, null, {count:0}), 0);
  assert.equal(fieldValue({name:'count',default:6}, null, null), 6);
  assert.deepEqual(fieldValue({name:'asset_ids'}, {asset_ids:[]}, {asset_ids:['a']}), []);
  assert.equal(fieldValue({name:'confirm',type:'checkbox'}, {confirm:true}, {confirm:true}), false);
});

test('task history never falls back to a different project', () => {
  const jobs = [{video_id:'one'}, {video_id:'two'}, {video_id:''}];
  assert.deepEqual(projectJobs(jobs, 'one'), [jobs[0]]);
  assert.deepEqual(projectJobs(jobs, 'missing'), []);
  assert.deepEqual(projectJobs(jobs, ''), [jobs[2]]);
});

test('save completion only clears the exact inputs submitted, not edits made while saving', () => {
  assert.equal(sameInputs({prompt:'A',asset_ids:[]}, {asset_ids:[],prompt:'A'}), true);
  assert.equal(sameInputs({prompt:'B',asset_ids:[]}, {prompt:'A',asset_ids:[]}), false);
  assert.equal(sameInputs({asset_ids:[]}, {asset_ids:['one']}), false);
});

const source = fs.readFileSync(require.resolve('../workbench/static/app.js'), 'utf8');
const createCode = source.slice(source.indexOf('async function createProject('), source.indexOf('async function trashProject('));
function createHarness(api) {
  const button = {disabled:false, textContent:'创建并进入制作'};
  const error = {hidden:true, textContent:''};
  const form = {dataset:{nextView:'studio',account:'main'}, querySelector: selector => selector === '#create-error' ? error : button};
  const event = {currentTarget:form, preventDefault(){}};
  const navigations = [];
  const messages = [];
  const context = {api, navigationId:1, cache:{}, drafts:createDraftStore(), FormData:class {entries(){return [['title','中文标题'],['videoId','new']];}},
    showToast: message => messages.push(message), navigate: (...args) => navigations.push(args)};
  vm.createContext(context);
  vm.runInContext(createCode, context);
  return {context, button, error, event, navigations, messages};
}

test('create success survives event.currentTarget becoming null after await', async () => {
  let resolve;
  const h = createHarness(() => new Promise(done => {resolve = done;}));
  const pending = h.context.createProject(h.event);
  h.event.currentTarget = null;
  resolve({id:'new',title:'中文标题'});
  await pending;
  assert.equal(h.navigations.length, 1);
  assert.equal(h.navigations[0][0], 'studio');
  assert.equal(h.context.cache.studioVideoId, 'new');
  assert.equal(h.error.hidden, true);
});

test('create failure preserves form and re-enables retry with inline error', async () => {
  const h = createHarness(async () => {throw new Error('项目 ID 已存在');});
  await h.context.createProject(h.event);
  assert.equal(h.button.disabled, false);
  assert.equal(h.error.textContent, '项目 ID 已存在');
  assert.equal(h.error.hidden, false);
  assert.equal(h.navigations.length, 0);
});

test('double submit is ignored, and late success cannot navigate another page', async () => {
  let resolve;
  let calls = 0;
  const h = createHarness(() => {calls++; return new Promise(done => {resolve = done;});});
  const pending = h.context.createProject(h.event);
  await h.context.createProject(h.event);
  h.context.navigationId = 2;
  resolve({id:'new',title:'新项目'});
  await pending;
  assert.equal(calls, 1);
  assert.equal(h.navigations.length, 0);
});
