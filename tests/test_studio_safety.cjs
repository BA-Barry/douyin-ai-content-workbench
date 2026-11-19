const test = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');

const source = fs.readFileSync(require.resolve('../workbench/static/app.js'), 'utf8');
const escape = value => String(value ?? '').replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
const helpers = source.slice(source.indexOf('function jobControlsMarkup('), source.indexOf('function wireJobControls('));
const context = {escape, URL}; vm.createContext(context); vm.runInContext(helpers,context);

test('pending actions expose current payload, option effects, exact IDs and official action link', () => {
  const html=context.jobControlsMarkup({job_id:'wb-a',status:'WAITING_USER',pending_actions:[{
    action_id:'a-current',resume_message_id:'message-current',message:'Confirm current cost',
    payload:{credits:120,model:'Seedance 2.5'}, action_url:'https://www.flova.ai/account/?view=quota',
    options:[{id:'confirm-current',label:'Confirm',effect:'resume',description:'Continue the same run'}, {id:'cancel-current',label:'Cancel',effect:'none'}]
  }]});
  for(const text of ['120','Seedance 2.5','data-pending-action="a-current"','data-option-id="confirm-current"','data-option-id="cancel-current"','平台动作：resume','平台动作：none','Continue the same run','href="https://www.flova.ai/account/?view=quota"']) assert.ok(html.includes(text),text);
  assert.ok(!html.includes('data-recover-job'));
});

test('pending descriptions and payload are escaped, not executable HTML', () => {
  const html=context.jobControlsMarkup({job_id:'wb-a',status:'WAITING_USER',pending_actions:[{
    action_id:'a',message:'<img src=x onerror=alert(1)>',description:'<script>alert(1)</script>',
    payload:{note:'<svg onload=alert(1)>'},options:[{id:'go',effect:'<b>resume</b>',description:'<iframe src=x>'}]
  }]});
  for(const unsafe of ['<script>','<img src=x','<svg','<iframe','<b>resume</b>']) assert.ok(!html.includes(unsafe),unsafe);
  assert.ok(html.includes('&lt;svg'));
});

test('only HTTPS official Flova action URLs become clickable', () => {
  const render=url=>context.jobControlsMarkup({job_id:'wb-a',pending_actions:[{action_id:'a',action_url:url}]});
  for(const url of ['javascript:alert(1)','https://flova.ai.evil.test/path','https://name:secret@flova.ai/path','http://flova.ai/path','//flova.ai/path']) assert.ok(!render(url).includes('href='),url);
  for(const url of ['https://www.flova.ai/path','https://flova.tv/path','https://help.flova.ai/path']) assert.ok(render(url).includes('href='),url);
});

test('Flova execution is exclusive to atmosphere videos; image and narrated routes cannot select it', () => {
  assert.equal(context.studioActionAvailable('GENERATE_FLOVA_VIDEO',{type:'ATMOSPHERE_VIDEO'}),true);
  for(const type of ['IMAGE_CAROUSEL','NARRATED_EXPLAINER',undefined]) assert.equal(context.studioActionAvailable('GENERATE_FLOVA_VIDEO',{type}),false);
  for(const action of ['COMPILE_VIDEO_TASK_PACKAGE','PROBE_MEDIA']) {
    assert.equal(context.studioActionAvailable(action,{type:'IMAGE_CAROUSEL'}),false);
    assert.equal(context.studioActionAvailable(action,{type:'NARRATED_EXPLAINER'}),true);
  }
});

test('direct Seedance and MiniMax targets cannot select the Flova execution action', () => {
  for(const providerTarget of ['SEEDANCE_2_0','SEEDANCE','MINIMAX_H3']) {
    const project={type:'ATMOSPHERE_VIDEO',skillPlan:{providerTarget}};
    assert.equal(context.studioActionAvailable('GENERATE_FLOVA_VIDEO',project),false,providerTarget);
    assert.equal(context.studioActionAvailable('COMPILE_VIDEO_TASK_PACKAGE',project),true,providerTarget);
  }
  assert.equal(context.studioActionAvailable('GENERATE_FLOVA_VIDEO',{type:'ATMOSPHERE_VIDEO',skillPlan:{providerTarget:'FLOVA'}}),true);
});

test('engineering-only projects cannot choose release or upload preparation', () => {
  for(const action of ['BUILD_RELEASE_PACKAGE','VALIDATE_RELEASE_PACKAGE','BUILD_PREPARE_JOB','BUILD_UPLOAD_PLAN']) {
    assert.equal(context.studioActionAvailable(action,{type:'IMAGE_CAROUSEL',pillar:'工具链测试不发布'}),false);
    assert.equal(context.studioActionAvailable(action,{type:'IMAGE_CAROUSEL',pillar:'现实治愈'}),true);
  }
  assert.equal(context.studioActionAvailable('SAVE_PRODUCTION_REQUEST',{type:'IMAGE_CAROUSEL',pillar:'工具链测试不发布'}),true);
});

const studioSource=source.slice(source.indexOf('async function showStudio('),source.indexOf('async function waitForJob('));
async function studioMarkup(projects,accountId,previousProject) {
  const stop=new Error('stop after initial HTML');
  const content={innerHTML:''};
  const ctx={content,escape,workflowSteps:[],actionPresentation:{},
    cache:{accounts:{activeAccountId:accountId},studioVideoId:previousProject},
    api:async url=>url==='/api/projects'?projects:(url==='/api/actions'?{items:[]}:(url==='/api/jobs?limit=60'?{items:[]}:{})),
    document:{querySelector(){throw stop;}}};
  vm.createContext(ctx);vm.runInContext(studioSource,ctx);
  await assert.rejects(ctx.showStudio(),error=>error===stop);
  return content.innerHTML;
}

test('production selector excludes other accounts even when sandbox API returns all projects', async () => {
  const projects=[
    {id:'main-project',title:'PRIVATE MAIN TITLE',accountId:'main',type:'IMAGE_CAROUSEL',state:'IDEA'},
    {id:'sandbox-project',title:'SANDBOX ONLY',accountId:'sandbox',type:'IMAGE_CAROUSEL',state:'IDEA'},
    {id:'unscoped-project',title:'UNSCOPED TITLE',type:'IMAGE_CAROUSEL',state:'IDEA'}
  ];
  const html=await studioMarkup(projects,'sandbox','main-project');
  assert.ok(html.includes('value="sandbox-project" selected'));
  assert.ok(!html.includes('PRIVATE MAIN TITLE'));assert.ok(!html.includes('main-project'));assert.ok(!html.includes('UNSCOPED TITLE'));
});

test('account with no projects starts local creation and never falls back to another account project', async () => {
  const html=await studioMarkup([{id:'other',title:'OTHER PRIVATE TITLE',accountId:'main',type:'IMAGE_CAROUSEL',state:'IDEA'}],'empty-account','other');
  assert.ok(!html.includes('OTHER PRIVATE TITLE'));
  assert.ok(html.includes('creation-route selected'));
  assert.ok(html.includes('<section id="project-create-panel" class="project-create-panel" >'));
});

test('video approval UI explicitly distinguishes authorized credit cap from unverified platform hard cap', () => {
  assert.ok(source.includes('积分上限是本次授权要求，不是平台硬限额'));
  assert.ok(source.includes('官方 CLI 暂无已验证的硬扣费上限'));
});
