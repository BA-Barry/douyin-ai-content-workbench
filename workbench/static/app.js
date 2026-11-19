const content = document.querySelector('#content');
const pageTitle = document.querySelector('#page-title');
const pageEyebrow = document.querySelector('#page-eyebrow');
const pageSubtitle = document.querySelector('#page-subtitle');
const dialog = document.querySelector('#detail-dialog');
const detailBox = document.querySelector('#detail');
const confirmDialog = document.querySelector('#confirm-dialog');
const confirmForm = document.querySelector('#confirm-form');
const confirmTitle = document.querySelector('#confirm-title');
const confirmMessage = document.querySelector('#confirm-message');
const confirmTypedField = document.querySelector('#confirm-typed-field');
const confirmExpected = document.querySelector('#confirm-expected');
const confirmInput = document.querySelector('#confirm-input');
const confirmAckField = document.querySelector('#confirm-ack-field');
const confirmAck = document.querySelector('#confirm-ack');
const confirmAckLabel = document.querySelector('#confirm-ack-label');
const confirmHint = document.querySelector('#confirm-hint');
const confirmSubmit = document.querySelector('#confirm-submit');
const toast = document.querySelector('#toast');
const cache = {};
const initialLocation = new URLSearchParams(window.location.search);
cache.studioVideoId = initialLocation.get('project') || null;
cache.studioAction = initialLocation.get('task') || null;
const drafts = WorkbenchState.createDraftStore();
let navigationId = 0;
let confirmationState = null;
let jobDetailTimer = null;

const pageMeta = {
  studio: ['创作', '制作中心', '选择图片或视频，随后在同一个页面完成设置、制作、质检与发布准备。'],
  assets: ['内容资产', '素材库', '集中管理图片、视频和音频，并明确每份素材的参考用途。'],
  overview: ['运营驾驶舱', '总览', '掌握当前内容、需要你确认的节点和下一步。'],
  topics: ['实时情报', '选题情报中心', '从全域题库、抖音趋势、课程知识和账号历史中筛选机会。'],
  projects: ['内容资产', '内容项目', '查看每条作品的状态、素材、审核与发布证据。'],
  pipeline: ['流程治理', '流程总控', '18 个阶段逐项留痕，人工介入点清晰可见。'],
  release: ['外部动作', '发布与数据', '从最终验收到指标复盘，发布按钮仍由你掌控。'],
  skills: ['知识资产', 'Skill 管理', '分类查看、移入回收站或恢复可重复调用的制作能力。'],
  offline: ['本地优先', '离线与队列', '断网时继续选题、查看证据、规划制作并导出只读快照。'],
};

const workflowSteps = [
  ['01', '选题', '确定主题与受众'],
  ['02', '草案', '锁定内容与脚本'],
  ['03', '制作', '生成画面与声音'],
  ['04', '质检', '检查内容与技术'],
  ['05', '发布准备', '锁定素材与文案'],
  ['06', '发布复盘', '发布后读取指标'],
];

const actionPresentation = {
  SAVE_PRODUCTION_REQUEST: ['内容设置', '自动编排制作链', '只写内容要求；系统根据路线自动组合相关 Skills。'],
  COMPILE_VIDEO_TASK_PACKAGE: ['视频制作', '生成视频任务确认卡', '根据当前计划生成 Flova、Seedance 或 MiniMax H3 任务，不消耗积分。'],
  GENERATE_FLOVA_VIDEO: ['视频制作', '执行 Flova 视频任务', '按已批准的确认卡执行、恢复并回收视频；只允许已包含额度。'],
  PIXELLE_VIDEO_GENERATE: ['制作', '生成视频', '调用本地 Pixelle 任务引擎并把成片保存回项目。'],
  PROBE_MEDIA: ['质检', '检测成片', '检查尺寸、编码、黑帧、冻结、静音和响度。'],
  BUILD_RELEASE_PACKAGE: ['发布准备', '锁定发布包', '将最终素材顺序、文案、审核结果和哈希绑定。'],
  VALIDATE_RELEASE_PACKAGE: ['发布准备', '校验发布包', '确认批准后的素材与文案没有发生变化。'],
  BUILD_PREPARE_JOB: ['发布准备', '生成上传任务', '生成 prepare-only 任务，不打开平台、不上传。'],
  BUILD_UPLOAD_PLAN: ['发布准备', '查看上传命令', '生成不可执行的抖音图文或视频命令预览。'],
  PROJECT_TRACE: ['项目检查', '检查阶段证据', '查看研究、制作、审核、发布与指标证据缺口。'],
  METRICS_SUMMARY: ['数据', '汇总作品指标', '读取只追加指标快照并生成当前摘要。'],
  WORKFLOW_AUDIT: ['系统', '审计全部项目', '检查状态机、文件结构和唯一状态源。'],
};

function workflowStepForState(state = '') {
  if (['PUBLISHED','REVIEW_2H','REVIEW_24H','REVIEW_72H','CLOSED'].includes(state)) return 6;
  if (['READY_FOR_USER','USER_APPROVED','PREPARED_IN_DOUYIN'].includes(state)) return 5;
  if (state === 'QA_REVIEW') return 4;
  if (['BRIEF_APPROVED','PRODUCING'].includes(state)) return 3;
  if (['RESEARCHED','BRIEF_DRAFT'].includes(state)) return 2;
  return 1;
}

const jobTone = status => ({SUCCEEDED:'published',RUNNING:'working',QUEUED:'idea',BLOCKED:'review',WAITING_USER:'review',RECOVERABLE:'review',FAILED:'danger',CANCELLED:'idea'}[status] || 'idea');
const jobLabel = status => ({SUCCEEDED:'已完成',RUNNING:'执行中',QUEUED:'排队中',BLOCKED:'条件未满足',WAITING_USER:'等待你确认',RECOVERABLE:'可恢复原任务',FAILED:'执行失败',CANCELLED:'已取消'}[status] || status);
const dispatchTone = status => ({READY:'idea',WAITING_APPROVAL:'review',LEASED:'working',COMPLETED:'published',FAILED:'danger',CANCELLED:'idea',NOT_QUEUED:'idea'}[status] || 'idea');
const dispatchLabel = status => ({READY:'待 Codex 领取',WAITING_APPROVAL:'等待人工门',LEASED:'Codex 执行中',COMPLETED:'制作已交付',FAILED:'执行失败',CANCELLED:'已被新计划取代',NOT_QUEUED:'尚未排队'}[status] || status);
const optionLabel = value => ({INCLUDED_ONLY:'仅免费或订阅内额度，不充值', AUTO:'自动判断', FLOVA:'Flova 官方 CLI', JIMENG:'即梦 / Seedance 2.0', MINIMAX_H3:'MiniMax H3', NONE:'不需要素材', USE_EXISTING:'使用已有素材', GENERATE_KEYFRAMES:'先生成关键帧', GENERATE_ELEMENTS:'先生成画面元素', EXTRACT_FROM_REFERENCE:'从参考视频提取', MIXED:'混合素材', TEXT_TO_VIDEO:'文生视频', FIRST_FRAME_TO_VIDEO:'首帧图生视频', FIRST_LAST_FRAME:'首尾帧生成', MULTIMODAL_TO_VIDEO:'多模态参考生成', VIDEO_EDIT:'编辑已有视频', none:'不使用', 'sample-first':'先出声音样段', 'user-voice':'使用本人声音', platform_manual:'在平台选择配乐', local_cleared:'使用已有授权配乐'}[value] || value);

const api = async (path, options = {}) => {
  const controller = new AbortController();
  const writing = options.method && options.method !== 'GET';
  const timer = setTimeout(() => controller.abort(), writing ? 120000 : 30000);
  try {
    const response = await fetch(path, {...options, signal: controller.signal});
    const type = response.headers.get('content-type') || '';
    const payload = type.includes('application/json') ? await response.json() : null;
    if (!response.ok) {
      const error = new Error(payload?.error || `请求失败：${response.status}`);
      error.status = response.status; error.code = payload?.code; error.current = payload?.current;
      throw error;
    }
    if (payload === null) throw new Error('接口返回了非预期内容，请检查工作台服务。');
    return payload;
  } catch (error) {
    if (error.name === 'AbortError' || error instanceof TypeError) {
      const reason = error.name === 'AbortError' ? '工作台响应超时' : '无法连接本地工作台';
      throw new Error(`${reason}。${writing ? '操作可能已提交，请先刷新记录核对，不要重复执行。' : '请双击「workbench / 打开工作台.cmd」，再重试连接。'}`);
    }
    throw error;
  } finally { clearTimeout(timer); }
};
const escape = (value = '') => String(value).replace(/[&<>"']/g, char => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#039;'}[char]));
const number = value => value === '' || value == null ? '—' : Number(value).toLocaleString('zh-CN');
const showToast = message => {
  toast.textContent = message;
  toast.classList.add('show');
  setTimeout(() => toast.classList.remove('show'), 3600);
};

const persistentActions = new Set(['SAVE_PRODUCTION_REQUEST', 'COMPILE_VIDEO_TASK_PACKAGE', 'GENERATE_FLOVA_VIDEO']);
const productionDrafts = WorkbenchState.createPersistentDraftStore(api, {onChange: (entry, reason) => {
  drafts.set(entry.account_id, entry.video_id, entry.action, entry.values);
  const form = document.querySelector('#job-form');
  if (!form || form.dataset.account !== entry.account_id || form.dataset.project !== entry.video_id || form.dataset.action !== entry.action) return;
  if (reason === 'hydrated' || reason === 'remote') {
    for (const field of form.elements) {
      if (!field.name || entry.values[field.name] === undefined) continue;
      if (field.name === 'asset_ids') field.checked = (entry.values.asset_ids || []).includes(field.value);
      else if (field.type !== 'checkbox') field.value = entry.values[field.name];
    }
  }
  renderDraftStatus(entry);
}});

function renderDraftStatus(entry) {
  const target = document.querySelector('#input-status');
  const controls = document.querySelector('#draft-actions');
  if (!target || !controls) return;
  const descriptions = {
    loading:'正在读取 G 盘草稿；可以继续输入。',
    pending:'有修改，等待自动保存到 G 盘…',
    saving:'正在保存草稿… 这不会启动制作。',
    saved:entry.version ? `草稿已保存到 G 盘${entry.updated_at ? ` · ${entry.updated_at}` : ''}。提交与执行状态见任务记录。` : '修改会自动保存到 G 盘；执行任务才会提交制作。',
    error:`草稿未能保存：${entry.error} 本页输入仍保留，请勿关闭页面。`,
    conflict:'另一个页面已更新此草稿。本页输入未覆盖，请选择保留哪一份。',
  };
  target.textContent = descriptions[entry.status] || '草稿等待保存';
  target.classList.toggle('draft-warning', ['error','conflict'].includes(entry.status));
  controls.innerHTML = entry.status === 'error' ? '<button type="button" class="button ghost" data-draft-choice="retry">重试保存</button>' : (entry.status === 'conflict' ? '<button type="button" class="button ghost" data-draft-choice="local">保留本页并重试</button><button type="button" class="button ghost" data-draft-choice="remote">载入另一页版本</button>' : '');
  controls.querySelectorAll('[data-draft-choice]').forEach(button => button.addEventListener('click', async () => {
    button.disabled = true;
    const args = [entry.account_id, entry.video_id, entry.action];
    if (button.dataset.draftChoice === 'retry') await productionDrafts.retry(...args);
    else await productionDrafts.resolve(...args, button.dataset.draftChoice);
  }));
}

function jobMediaMarkup(job, limit = 8) {
  return (job.media || []).filter(item => typeof item.url === 'string' && /^\/(?![\/\\])/.test(item.url)).slice(0, limit).map(item => `<figure class="job-media">${item.kind === 'video' ? `<video controls playsinline preload="metadata" src="${escape(item.url)}"></video>` : (item.kind === 'image' ? `<img loading="lazy" src="${escape(item.url)}" alt="${escape(item.name || '生成图片')}">` : '')}<figcaption>${escape(item.name || '本地产物')}<a href="${escape(item.url)}" target="_blank" rel="noreferrer">打开原文件</a></figcaption></figure>`).join('');
}

function jobControlsMarkup(job) {
  const pending = (job.pending_actions || []).map(action => {
    let actionUrl = '';
    try {
      const url = new URL(action.action_url);
      if (url.protocol === 'https:' && !url.username && !url.password && /(^|\.)flova\.(ai|tv)$/.test(url.hostname)) actionUrl = url.href;
    } catch (_) { /* Missing or non-official URLs are not actionable. */ }
    const payload = action.payload && Object.keys(action.payload).length ? `<details open class="pending-details"><summary>平台确认详情（包含费用或素材条件）</summary><pre>${escape(JSON.stringify(action.payload, null, 2))}</pre></details>` : '';
    return `<section class="pending-action"><b>${escape(action.message || action.title || '平台需要你的选择')}</b>${action.description ? `<p>${escape(action.description)}</p>` : ''}${payload}${actionUrl ? `<p><a href="${escape(actionUrl)}" target="_blank" rel="noreferrer">在 Flova 查看此操作</a></p>` : ''}<div>${(action.options || []).map(option => `<div class="pending-option"><button type="button" class="button ghost" data-resolve-job="${escape(job.job_id)}" data-pending-action="${escape(action.id || action.action_id)}" data-option-id="${escape(option.id || option.option_id)}">${escape(option.label || option.title || option.id || option.option_id)}</button>${option.effect ? `<small>平台动作：${escape(option.effect)}</small>` : ''}${option.description ? `<small>${escape(option.description)}</small>` : ''}</div>`).join('') || '<p>没有可用选项，请查看任务日志；不会自动继续。</p>'}</div></section>`;
  }).join('');
  return `${job.status === 'RECOVERABLE' ? `<button type="button" class="button ghost" data-recover-job="${escape(job.job_id)}">恢复原任务</button>` : ''}${pending}`;
}

function studioActionAvailable(actionId, project) {
  if (project?.pillar === '工具链测试不发布' && ['BUILD_RELEASE_PACKAGE','VALIDATE_RELEASE_PACKAGE','BUILD_PREPARE_JOB','BUILD_UPLOAD_PLAN'].includes(actionId)) return false;
  if (actionId === 'GENERATE_FLOVA_VIDEO') return project?.type === 'ATMOSPHERE_VIDEO' && !['SEEDANCE','SEEDANCE_2_0','MINIMAX_H3'].includes(project?.skillPlan?.providerTarget);
  if (['COMPILE_VIDEO_TASK_PACKAGE','PROBE_MEDIA'].includes(actionId)) return project?.type !== 'IMAGE_CAROUSEL';
  return true;
}

function wireJobControls(scope, onUpdate) {
  scope.querySelectorAll('[data-recover-job], [data-resolve-job]').forEach(button => button.addEventListener('click', async () => {
    const buttons = [...scope.querySelectorAll('[data-recover-job], [data-resolve-job]')];
    if (button.disabled) return;
    buttons.forEach(item => {item.disabled = true;});
    const jobId = button.dataset.recoverJob || button.dataset.resolveJob;
    const endpoint = button.dataset.recoverJob ? 'recover' : 'resolve';
    const body = endpoint === 'resolve' ? {action_id:button.dataset.pendingAction, option_id:button.dataset.optionId} : {};
    try {
      await api(`/api/jobs/${encodeURIComponent(jobId)}/${endpoint}`, {method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(body)});
      showToast(endpoint === 'recover' ? '正在恢复同一个任务，不会重新发起生成。' : '你的选择已提交，请查看任务状态。');
      await onUpdate(jobId);
    } catch (error) { showToast(error.message); buttons.forEach(item => {item.disabled = false;}); }
  }));
}

function rememberStudioInputs() {
  const form = document.querySelector('#job-form');
  if (form?.dataset.action) {
    const values = Object.fromEntries(new FormData(form).entries());
    values.asset_ids = new FormData(form).getAll('asset_ids');
    form.querySelectorAll('input[type="checkbox"]:not([name="asset_ids"])').forEach(input => delete values[input.name]);
    drafts.set(form.dataset.account, form.dataset.project, form.dataset.action, values);
    if (form.dataset.project && persistentActions.has(form.dataset.action)) productionDrafts.set(form.dataset.account, form.dataset.project, form.dataset.action, values);
  }
  const createForm = document.querySelector('#studio-create-project-form');
  if (createForm) {
    drafts.set(createForm.dataset.account, '', 'CREATE_PROJECT', Object.fromEntries(new FormData(createForm).entries()));
  }
}

function resetAccountContext() {
  cache.projects = null; cache.topics = null;
  cache.studioVideoId = null; cache.studioCreateMode = null;
  cache.studioVideoType = null; cache.projectDraft = null;
}

function syncConfirmation() {
  if (!confirmationState) return;
  const nameMatches = !confirmationState.expected || confirmInput.value === confirmationState.expected;
  const acknowledged = !confirmationState.acknowledgement || confirmAck.checked;
  confirmSubmit.disabled = !(nameMatches && acknowledged);
  if (confirmationState.expected && !nameMatches) {
    confirmHint.textContent = confirmInput.value ? '输入内容与目标名称不一致。' : '此操作可恢复，但必须准确输入目标名称。';
  } else if (confirmationState.acknowledgement && !acknowledged) {
    confirmHint.textContent = '请先确认这项影响，再继续。';
  } else {
    confirmHint.textContent = '确认条件已满足，可以继续。';
  }
}

function settleConfirmation(result) {
  if (!confirmationState) return;
  const resolve = confirmationState.resolve;
  confirmationState = null;
  if (confirmDialog.open) confirmDialog.close();
  resolve(result);
}

function requestConfirmation({title, message, expected = '', acknowledgement = '', submitLabel = '确认'}) {
  if (confirmationState) settleConfirmation(false);
  confirmTitle.textContent = title;
  confirmMessage.textContent = message;
  confirmExpected.textContent = expected;
  confirmInput.value = '';
  confirmTypedField.hidden = !expected;
  confirmInput.required = Boolean(expected);
  confirmAck.checked = false;
  confirmAckField.hidden = !acknowledgement;
  confirmAckLabel.textContent = acknowledgement;
  confirmSubmit.textContent = submitLabel;
  return new Promise(resolve => {
    confirmationState = {expected, acknowledgement, resolve};
    syncConfirmation();
    confirmDialog.showModal();
    window.setTimeout(() => (expected ? confirmInput : (acknowledgement ? confirmAck : confirmSubmit)).focus(), 0);
  });
}

confirmForm.addEventListener('input', syncConfirmation);
confirmForm.addEventListener('submit', event => {
  event.preventDefault();
  if (!confirmSubmit.disabled) settleConfirmation(true);
});
document.querySelector('#confirm-cancel').addEventListener('click', () => settleConfirmation(false));
confirmDialog.addEventListener('cancel', event => {
  event.preventDefault();
  settleConfirmation(false);
});
const stateBadge = item => `<span class="badge ${item.stateTone || 'idea'}">${escape(item.state)}</span>`;
const modeBadge = mode => ({manual: '<span class="mode manual">必须人工</span>', assisted: '<span class="mode assisted">人机协作</span>', conditional: '<span class="mode conditional">条件确认</span>', auto: '<span class="mode auto">自动执行</span>'}[mode] || '');

async function loadRuntime() {
  const data = await api('/api/offline');
  cache.runtime = data;
  const badge = document.querySelector('#runtime-badge');
  badge.textContent = data.runtimeMode === 'offline' ? '离线模式' : (data.offlineReady ? '本地就绪' : '本地缺项');
  badge.classList.toggle('offline', data.runtimeMode === 'offline');
  badge.classList.toggle('warning', !data.offlineReady);
  const creator = document.querySelector('#creator-center-link');
  creator.hidden = data.runtimeMode === 'offline';
}

async function loadAccounts() {
  const data = await api('/api/accounts');
  cache.accounts = data;
  const select = document.querySelector('#account-switch');
  select.innerHTML = data.profiles.map(profile => `<option value="${escape(profile.account_id)}" ${profile.account_id === data.activeAccountId ? 'selected' : ''}>${escape(profile.display_name)}</option>`).join('');
}

function projectRow(item) {
  const progress = item.stageProgress || {};
  const current = progress.current;
  return `<article class="project-row" data-project="${escape(item.id)}">
    <div class="project-main"><b>${escape(item.title)}</b><span>${escape(item.pillar || item.type)}</span></div>
    ${stateBadge(item)}
    <span class="row-meta">${progress.verified ?? 0}/${progress.total ?? 18} 项证据${progress.evidenceGaps ? ` · ${progress.evidenceGaps} 缺口` : ''}</span>
    <span class="row-action">${escape(current ? `${current.id} ${current.title}` : (item.nextAction || '等待下一步'))}</span>
  </article>`;
}

function projectCard(item) {
  const cover = item.cover ? `<img loading="lazy" src="${item.cover}" alt="${escape(item.title)}">` : '<span>暂无封面</span>';
  const progress = item.stageProgress || {};
  return `<article class="project-card" data-project="${escape(item.id)}">
    <div class="cover">${cover}<span class="cover-count">${item.imageCount || 0} 张</span></div>
    <div class="project-body">${stateBadge(item)}<h3>${escape(item.title)}</h3><p>${escape(item.hypothesis)}</p>
      <div class="stage-meter"><span style="width:${Number(progress.verifiedPercent || 0)}%"></span></div><div class="meta"><span>${progress.verified ?? 0}/${progress.total ?? 18} 项证据</span><span>${progress.evidenceGaps ? `${progress.evidenceGaps} 个历史缺口` : escape(item.qaStatus || '未质检')}</span></div>
      <button class="danger-link" data-trash-project="${escape(item.id)}" data-published="${item.state === 'PUBLISHED'}" type="button">移入回收站</button>
    </div>
  </article>`;
}

function wireProjectClicks() {
  document.querySelectorAll('[data-project]').forEach(node => node.addEventListener('click', event => {
    if (!event.target.closest('[data-trash-project]')) showDetail(node.dataset.project);
  }));
  document.querySelectorAll('[data-trash-project]').forEach(button => button.addEventListener('click', event => trashProject(event.currentTarget)));
}

async function overview(isCurrent = () => true) {
  const data = await api('/api/dashboard');
  if (!isCurrent()) return;
  cache.dashboard = data;
  const recommendation = data.topicRecommendation;
  content.innerHTML = `
    <section class="hero-grid">
      <div class="hero-card">
        <p class="eyebrow">${escape(data.account?.display_name || '当前账号')} · 账号承诺</p>
        <h2>${escape(data.account?.positioning || '先确定账号承诺')}</h2>
        <p>${escape(data.account?.audience || '')}</p>
        <button class="text-button" data-go="topics">进入选题助手 →</button>
      </div>
      <div class="decision-card">
        <span class="decision-label">下一候选</span>
        <h3>${escape(recommendation?.title || '等待选题池补充')}</h3>
        <p>${escape(recommendation?.audienceNeed || recommendation?.hook || '先完成当前作品的数据窗口，再决定下一变量。')}</p>
        <div class="score-line"><strong>${recommendation?.score || '—'}</strong><span>选题准备度</span></div>
      </div>
    </section>
    <div class="stats">
      <div class="stat"><span>内容项目</span><b>${data.counts.total}</b><small>registry 唯一状态源</small></div>
      <div class="stat"><span>已发布</span><b>${data.counts.published}</b><small>等待完整数据闭环</small></div>
      <div class="stat"><span>待推进</span><b>${data.counts.active}</b><small>不含已发布与暂停项</small></div>
      <div class="stat"><span>收藏候选</span><b>${data.counts.shortlist}</b><small>本地保存，尚未立项</small></div>
      <div class="stat"><span>人工介入阶段</span><b>${data.workflow.manual}</b><small>共 ${data.workflow.total} 个流程阶段</small></div>
    </div>
    <section class="offline-banner ${data.offline.ready ? 'ready' : 'warning'}"><div><b>${data.offline.ready ? '本地工作能力已就绪' : '本地工作能力存在缺项'}</b><p>选题、项目、证据、流程和离线快照不依赖外网；趋势刷新、平台指标与发布仍需联网。</p></div><button class="text-button" data-go="offline">查看离线边界 →</button></section>
    <div class="safety"><b>安全边界</b><span>${escape(data.safety)}</span></div>
    <section class="mini-radar"><span class="radar-pulse"></span><div><b>热点雷达 ${escape(data.trend.automation?.status || data.trend.collection_status || 'EMPTY')}</b><p>${escape(data.trend.automation?.status === 'PAUSED' ? '热点监控已关闭，保留历史快照供参考。' : (data.trend.source_summary || '等待采集'))}</p></div><button class="text-button" data-go="topics">查看选题情报 →</button></section>
    <div class="dashboard-grid">
      <section class="panel"><div class="panel-head"><div><span class="section-kicker">内容进度</span><h2>最近项目</h2></div><button class="text-button" data-go="projects">查看全部</button></div>${data.recent.map(projectRow).join('') || '<p class="empty">暂无内容</p>'}</section>
      <aside class="panel"><div class="panel-head"><div><span class="section-kicker">人工待办</span><h2>需要推进</h2></div></div>
        <div class="attention-list">${data.attention.map(item => `<button class="attention-item" data-project="${escape(item.id)}"><span>${stateBadge(item)}</span><b>${escape(item.title)}</b><p>${escape(item.nextAction || '暂无下一步')}</p></button>`).join('') || '<p class="empty">当前没有等待处理的制作项目。</p>'}</div>
      </aside>
    </div>`;
  wireProjectClicks();
  wireGoButtons();
}

async function showStudio(isCurrent = () => true) {
  const [allProjects, actionData, jobData, assetData, providerData] = await Promise.all([
    api('/api/projects'), api('/api/actions'), api('/api/jobs?limit=60'), api('/api/assets'), api('/api/video-providers')
  ]);
  if (!isCurrent()) return;
  const accountId = cache.accounts?.activeAccountId || '';
  // The exploration sandbox may browse all accounts; production drafts may not.
  const projects = allProjects.filter(project => project.accountId === accountId);
  const draft = cache.projectDraft || {};
  const createMode = cache.studioCreateMode || (!projects.length ? 'IMAGE_CAROUSEL' : '');
  const actions = actionData.items.filter(action => action.enabled !== false);
  const preferredId = createMode ? '' : (cache.studioVideoId && projects.some(item => item.id === cache.studioVideoId)
    ? cache.studioVideoId : (projects.find(item => !['PUBLISHED','CLOSED'].includes(item.state))?.id || projects[0]?.id || ''));
  const selectedActionId = cache.studioAction && actions.some(item => item.id === cache.studioAction)
    ? cache.studioAction : 'SAVE_PRODUCTION_REQUEST';
  const groups = [...new Set(actions.map(action => actionPresentation[action.id]?.[0] || action.category))];
  const actionButtons = groups.map(group => `<div class="task-group"><span>${escape(group)}</span><div>${actions.filter(action => (actionPresentation[action.id]?.[0] || action.category) === group).map(action => {
    const present = actionPresentation[action.id] || [group, action.label, action.description];
    return `<button type="button" class="task-choice ${action.id === selectedActionId ? 'selected' : ''}" data-action-id="${escape(action.id)}"><b>${escape(present[1])}</b><small>${escape(present[2])}</small></button>`;
  }).join('')}</div></div>`).join('');

  content.innerHTML = `<section class="studio-entry">
      <div class="studio-entry-copy"><h2>开始一项制作</h2><p>新建时只需选择作品类型；项目建立后，系统会自动锁定正确的图片或视频流程。</p></div>
      <div class="creation-choice" role="group" aria-label="选择新作品类型">
        <button class="creation-route ${createMode === 'IMAGE_CAROUSEL' ? 'selected' : ''}" data-create-route="IMAGE_CAROUSEL" type="button"><b>图片作品</b><small>提示词 → Codex 生成 → 高清导出</small></button>
        <button class="creation-route ${createMode === 'VIDEO' ? 'selected' : ''}" data-create-route="ATMOSPHERE_VIDEO" type="button"><b>视频作品</b><small>分镜 → 素材策略 → 生成与后期</small></button>
      </div>
      <label class="continue-project"><span>或继续已有项目</span><select id="studio-project"><option value="">选择一个项目</option>${projects.map(item => `<option value="${escape(item.id)}" ${item.id === preferredId ? 'selected' : ''}>${escape(item.title)} · ${escape(item.type)} · ${escape(item.state)}</option>`).join('')}</select></label>
    </section>
    <section id="project-create-panel" class="project-create-panel" ${createMode ? '' : 'hidden'}></section>
    <ol id="workflow-steps" class="workflow-steps" ${createMode ? 'hidden' : ''}>${workflowSteps.map(([id,title,desc], index) => `<li data-step="${index + 1}"><span>${id}</span><div><b>${title}</b><small>${desc}</small></div></li>`).join('')}</ol>
    <div class="creation-grid" ${createMode ? 'hidden' : ''}>
      <section id="task-builder" class="builder-shell">
        <div class="builder-head"><div><span class="section-kicker">任务设置</span><h2>这次要完成什么</h2></div><span class="save-state">所有产物写入 G 盘</span></div>
        <label class="current-task">当前任务<select id="studio-action">${actions.map(action => `<option value="${action.id}" ${action.id === selectedActionId ? 'selected' : ''}>${escape(actionPresentation[action.id]?.[1] || action.label)}</option>`).join('')}</select></label>
        <details class="task-tools"><summary>查看全部工具及用途</summary><div class="task-palette">${actionButtons}</div></details>
        <div id="action-description" class="action-summary"></div>
        <form id="job-form"><p id="input-status" class="input-status" role="status"></p><div id="draft-actions" class="draft-actions"></div><div id="job-fields" class="parameter-grid"></div>
          <p id="job-error" class="inline-error" role="alert" hidden></p>
          <div class="run-bar"><div><b id="run-title">准备执行</b><span id="run-help">动作会记录日志与产物；前置证据不足时会明确阻断。</span></div><button class="button primary-run" type="submit">执行当前任务</button></div>
        </form>
      </section>
      <aside class="preview-shell">
        <div class="preview-head"><div><span class="section-kicker">输出预览</span><h2 id="preview-project-title">尚未选择项目</h2></div><span id="preview-route" class="route-chip">—</span></div>
        <div id="media-preview" class="media-preview"><div><span>9:16</span><b>项目素材将在这里预览</b><small>选择项目后显示当前封面和阶段</small></div></div>
        <div id="project-evidence" class="project-evidence"></div>
        <section id="execution-summary" class="execution-summary" aria-label="当前制作状态"></section>
        <section id="auto-skill-plan" class="auto-skill-plan"></section>
        <section class="engine-console"><div><span class="engine-light"></span><div id="engine-console-copy"><b>生成路线等待项目</b><small>选择项目后显示图片或视频的实际执行入口。</small></div></div><div class="engine-console-actions"><button id="engine-route-link" data-scroll-target="task-builder" type="button">查看当前任务</button></div></section>
        <section id="provider-status" class="provider-status" hidden></section>
        <div id="latest-result" class="latest-result"><span>最近结果</span><p>执行任务后，这里会显示状态、摘要和产物。</p></div>
      </aside>
    </div>
    <div class="workbench-bottom" ${createMode ? 'hidden' : ''}>
      <section class="job-history panel"><div class="panel-head"><div><h2>当前项目执行记录</h2><p>仅显示所选项目的任务，避免混淆制作结果。</p></div><button id="refresh-jobs" class="button ghost" type="button">刷新</button></div><div id="job-list"></div></section>
      <aside class="next-gates panel"><div class="panel-head"><div><span class="section-kicker">人工确认</span><h2>不会被自动跨越</h2></div></div><ol><li>最终画面、视频与声音验收</li><li>付费模型、私人素材与声音克隆</li><li>进入抖音上传页前的确认</li><li>最终点击发布</li></ol><button class="button ghost wide" data-go="pipeline" type="button">查看完整 18 阶段规范</button></aside>
    </div>`;

  const projectSelect = document.querySelector('#studio-project');
  const actionSelect = document.querySelector('#studio-action');
  const projectCreatePanel = document.querySelector('#project-create-panel');
  const currentAction = () => actions.find(item => item.id === actionSelect.value);
  let jobs = jobData.items;
  let localPollTimer = null;
  let providerStatus = null;
  let providerLoading = false;
  const renderProviderStatus = () => {
    const item = projects.find(project => project.id === projectSelect.value);
    const holder = document.querySelector('#provider-status');
    holder.hidden = !item || item.type === 'IMAGE_CAROUSEL' || ['SEEDANCE','SEEDANCE_2_0','MINIMAX_H3'].includes(item.skillPlan?.providerTarget);
    if (holder.hidden) return;
    const known = providerStatus && !providerStatus.error;
    const message = providerStatus?.message || providerStatus?.error || '只读检查登录和额度，不会提交视频任务。';
    holder.innerHTML = `<div><b>Flova 账号条件</b><button class="text-button" type="button" data-provider-check ${providerLoading ? 'disabled' : ''}>${providerLoading ? '检查中…' : '检查状态'}</button></div><p>${escape(message)}</p>${known ? `<dl><div><dt>登录</dt><dd>${providerStatus.authenticated ? '已登录' : '未登录或无法确认'}</dd></div><div><dt>积分余额</dt><dd>${number(providerStatus.credits_balance)}</dd></div></dl><small>订阅权益以当前账号返回为准。零余额、权益未知或审批不完整时不会启动生成。</small>` : ''}${providerStatus?.checked_at ? `<small>检查于 ${escape(providerStatus.checked_at)}</small>` : ''}`;
    holder.querySelector('[data-provider-check]').addEventListener('click', checkProviderStatus);
  };
  const checkProviderStatus = async () => {
    if (providerLoading) return;
    providerLoading = true; renderProviderStatus();
    try { providerStatus = await api('/api/providers/flova/status'); }
    catch (error) { providerStatus = {error:error.message}; }
    finally { providerLoading = false; if (isCurrent()) renderProviderStatus(); }
  };
  const renderExecutionSummary = () => {
    if (!isCurrent()) return;
    const item = projects.find(project => project.id === projectSelect.value);
    const target = document.querySelector('#execution-summary');
    if (!item) { target.innerHTML = ''; return; }
    const visible = WorkbenchState.projectJobs(jobs, item.id);
    const job = visible.find(entry => entry.action_id === 'GENERATE_FLOVA_VIDEO' || entry.action === 'GENERATE_FLOVA_VIDEO');
    const dispatch = item.dispatch || {};
    const isImage = item.type === 'IMAGE_CAROUSEL';
    const state = isImage ? dispatchLabel(dispatch.state || 'NOT_QUEUED') : (job ? jobLabel(job.status) : '等待视频任务');
    const directProvider = ['SEEDANCE','SEEDANCE_2_0','MINIMAX_H3'].includes(item.skillPlan?.providerTarget);
    const owner = isImage ? (dispatch.workerId || 'Codex 图片执行任务') : (job?.provider?.name || (directProvider ? '独立平台入口尚未接通' : 'Flova 官方 CLI'));
    const message = isImage ? (dispatch.reason || '先保存制作要求、确认提示词，再等待 Codex 执行。') : (job?.progress?.message || '生成确认卡不等于视频已生成；先确认模型、时长和可用额度。');
    const next = isImage ? (dispatch.state === 'COMPLETED' ? '查看图片并进行审美验收。' : (dispatch.state === 'LEASED' ? '等待当前 Codex 任务回传图片。' : '按当前提示推进；不要重复提交相同任务。')) : (job?.next_action || (directProvider ? '检查任务确认卡；独立平台暂不从工作台执行。' : (item.videoTask?.ready ? '任务确认卡已准备；检查 Flova 额度并确认本次生成要求。' : '生成任务确认卡，再检查 Flova 账号条件。')));
    const taskCard = !isImage && item.videoTask?.ready ? `<h3>当前视频任务确认卡</h3><dl>${[['服务商',item.videoTask.provider],['模型提案',item.videoTask.model],['画幅',item.videoTask.aspectRatio],['时长',`${item.videoTask.duration ?? '待定'} 秒`],['分辨率',item.videoTask.resolution]].map(([label,value])=>`<div><dt>${escape(label)}</dt><dd>${escape(value || '待定')}</dd></div>`).join('')}</dl><p>仅为本地准备结果，不代表已批准、已扣费或已生成。</p>` : '';
    target.innerHTML = `<h3>当前制作状态</h3><dl><div><dt>步骤</dt><dd>${escape(state)}</dd></div><div><dt>执行方</dt><dd>${escape(owner)}</dd></div></dl><p>${escape(message)}</p><p><strong>下一步：</strong>${escape(typeof next === 'string' ? next : (next.message || next.label || '查看任务详情'))}</p>${taskCard}${!isImage && job ? jobControlsMarkup(job) : ''}`;
    wireJobControls(target, async () => { await loadProjectJobs(); });
    const mediaJob = visible.find(entry => (entry.media || []).length);
    if (mediaJob) {
      document.querySelector('#media-preview').innerHTML = jobMediaMarkup(mediaJob, 1);
    } else if (item.cover) {
      document.querySelector('#media-preview').innerHTML = `<img src="${escape(item.cover)}" alt="${escape(item.title)}"><span>${item.imageCount || 0} 张素材</span>`;
    }
  };
  const renderCreatePanel = () => {
    if (!createMode) return;
    const isImage = createMode === 'IMAGE_CAROUSEL';
    const suggestedVideoType = cache.studioVideoType || (String(draft.format || '').match(/讲解|口播|科普/) ? 'NARRATED_EXPLAINER' : 'ATMOSPHERE_VIDEO');
    const routeSteps = isImage
      ? [['主题与用途','受众、风格、图数和禁区'],['素材（可选）','无素材也可直接生成'],['自动提示词','组合视觉 Skills 与逐图要求'],['生成与审核','Codex 生成、整批审美复核'],['高清导出','规格、顺序与发布包']]
      : [['主题与分镜','逐秒节奏、镜头和台词'],['素材策略','判断是否需要图片锚点'],['任务确认卡','选择 Flova、Seedance 或 H3'],['镜头与后期','生成、Remotion / video-use 合成'],['视频 QA','连续性、首屏、声音与规格']];
    const hypothesis = draft.audienceNeed ? `在账号定位与制作质量保持不变时，以“${draft.title || '本主题'}”满足${draft.audienceNeed}，会提高收藏、停留或分享。` : '';
    const providerNote = !isImage ? `<aside class="studio-provider-note"><b>${escape(providerData.decision === 'FLOVA_CONTROLLED_PILOT' ? '当前建议：先走 Flova 受控试点' : providerData.decision || '视频服务待确认')}</b><p>${escape(providerData.decision_summary || '实际生成前再确认服务商、模型、费用和素材上传。')}</p><small>也可在项目中明确指定 Seedance 或 MiniMax H3；系统不会在未确认时提交生成。</small></aside>` : '';
    projectCreatePanel.innerHTML = `<div class="project-create-head"><div><h2>新建${isImage ? '图片' : '视频'}作品</h2><p>${isImage ? '主题和素材均可独立输入，项目建立后只显示图片生产动作。' : '先建立视频路线；是否生成图片锚点由后续素材策略决定。'}</p></div><button class="text-button" data-close-create type="button">收起</button></div>
      <div class="route-step-strip">${routeSteps.map(([title,desc], index) => `<article><span>${index + 1}</span><div><b>${title}</b><small>${desc}</small></div></article>`).join('')}</div>
      <div class="project-create-body"><form id="studio-create-project-form" data-next-view="studio" data-account="${escape(accountId)}">
        <input type="hidden" name="contentType" value="${isImage ? 'IMAGE_CAROUSEL' : escape(suggestedVideoType)}">
        <label>项目 ID<input name="videoId" required pattern="[A-Za-z0-9._-]+" placeholder="例如 ${isImage ? 'quiet-weekend-images-01' : 'city-morning-video-01'}"></label>
        <label>工作标题<input name="title" required value="${escape(draft.title || '')}" placeholder="这条作品的内部标题"></label>
        ${isImage ? '' : `<label>视频路线<select id="studio-video-type"><option value="ATMOSPHERE_VIDEO" ${suggestedVideoType === 'ATMOSPHERE_VIDEO' ? 'selected' : ''}>氛围视频</option><option value="NARRATED_EXPLAINER" ${suggestedVideoType === 'NARRATED_EXPLAINER' ? 'selected' : ''}>旁白讲解视频</option></select></label>`}
        <label>栏目 / 系列<input name="pillar" required value="${escape(draft.subdomain || draft.domain || '')}" placeholder="例如 现实治愈"></label>
        <label class="span-all">单变量假设<textarea name="hypothesis" required placeholder="保持哪些条件不变，验证哪个变量对哪个指标的影响？">${escape(hypothesis)}</textarea></label>
        <p id="create-error" class="inline-error span-all" role="alert" hidden></p>
        <div class="project-create-actions span-all"><span>创建只写入本地项目，不会生成、上传或发布。</span><button class="button dark" type="submit">创建并进入制作</button></div>
      </form>${providerNote}</div>`;
    const creationDraft = drafts.get(accountId, '', 'CREATE_PROJECT');
    if (creationDraft) {
      const form = document.querySelector('#studio-create-project-form');
      ['videoId', 'title', 'pillar', 'hypothesis'].forEach(name => {
        if (creationDraft[name] !== undefined) form.elements.namedItem(name).value = creationDraft[name];
      });
    }
    const typeSelect = document.querySelector('#studio-video-type');
    typeSelect?.addEventListener('change', event => {
      cache.studioVideoType = event.target.value;
      document.querySelector('#studio-create-project-form input[name="contentType"]').value = event.target.value;
    });
    document.querySelector('#studio-create-project-form').addEventListener('submit', createProject);
    document.querySelector('[data-close-create]').addEventListener('click', () => {
      rememberStudioInputs();
      cache.studioCreateMode = null;
      cache.projectDraft = null;
      navigate(projects.length ? 'studio' : 'projects');
    });
  };
  renderCreatePanel();
  const renderFields = () => {
    const action = currentAction();
    const selectedProject = projects.find(project => project.id === projectSelect.value);
    const isImageRoute = selectedProject?.type === 'IMAGE_CAROUSEL';
    const form = document.querySelector('#job-form');
    form.dataset.account = accountId;
    form.dataset.project = projectSelect.value;
    form.dataset.action = action.id;
    const durable = Boolean(projectSelect.value && persistentActions.has(action.id));
    const draftValues = (durable && productionDrafts.get(accountId, projectSelect.value, action.id)) || drafts.get(accountId, projectSelect.value, action.id);
    const savedValues = action.id === 'SAVE_PRODUCTION_REQUEST' ? selectedProject?.productionRequest?.parameters : (action.id === 'GENERATE_FLOVA_VIDEO' ? {model:selectedProject?.videoTask?.model || ''} : null);
    document.querySelector('#input-status').textContent = draftValues
      ? '已恢复本标签页输入；此操作参数未持久保存。'
      : (selectedProject?.productionRequest?.savedAt && savedValues
        ? `已载入上次保存：${selectedProject.productionRequest.savedAt}` : '修改后请执行当前任务；切换步骤会暂存本标签页输入。');
    document.querySelector('#draft-actions').innerHTML = '';
    document.querySelector('#input-status').classList.remove('draft-warning');
    document.querySelector('#job-error').hidden = true;
    const present = actionPresentation[action.id] || [action.category, action.label, action.description];
    cache.studioAction = action.id;
    const location = new URL(window.location.href);
    if (projectSelect.value) location.searchParams.set('project', projectSelect.value);
    else location.searchParams.delete('project');
    location.searchParams.set('task', action.id);
    window.history.replaceState(null, '', location);
    document.querySelectorAll('[data-action-id]').forEach(button => button.classList.toggle('selected', button.dataset.actionId === action.id));
    const autoRoute = action.id === 'SAVE_PRODUCTION_REQUEST' ? `<li>${isImageRoute ? '生成完整逐图提示词，再调用 Codex 图片生成与高清导出' : '先判断图片锚点，再组合分镜、视频生成与后期 Skills'}</li>` : '';
    document.querySelector('#action-description').innerHTML = `<div><span>${escape(present[0])}</span><h3>${escape(present[1])}</h3><p>${escape(action.description)}</p>${action.id === 'GENERATE_FLOVA_VIDEO' ? '<p class="inline-error">预算限制：填写的积分上限是本次授权要求，不是平台硬限额。官方 CLI 暂无已验证的硬扣费上限；本轮真实生成待额度，不充值或升级。</p>' : ''}</div><ul>${autoRoute}<li>${action.writes_project ? '会写入当前项目证据' : '只读检查或写入任务日志'}</li><li>${action.external_action ? '需要确认模型或接口配置' : '不执行平台外部动作'}</li></ul>`;
    const holder = document.querySelector('#job-fields');
    holder.innerHTML = action.fields.filter(field => {
      if (!selectedProject || action.id !== 'SAVE_PRODUCTION_REQUEST') return true;
      if (isImageRoute && ['duration_seconds','voice_mode','video_mode','video_provider','asset_strategy'].includes(field.name)) return false;
      return true;
    }).map(field => {
      const value = WorkbenchState.fieldValue(field, draftValues, savedValues);
      const full = ['textarea','checkbox'].includes(field.type) ? ' full' : '';
      if (field.type === 'asset_picker') {
        const available = assetData.items || [];
        const selectedAssets = draftValues?.asset_ids ?? selectedProject?.productionRequest?.assetIds ?? available.filter(asset => (asset.project_ids || []).includes(projectSelect.value)).map(asset => asset.id);
        if (!available.length) return `<section class="asset-picker full"><div><b>参考素材（可选）</b><button type="button" data-go="assets">打开素材库</button></div><p>当前素材库为空。图片项目可以只靠主题生成；视频项目也可以直接采用文生视频。</p></section>`;
        return `<fieldset class="asset-picker full"><legend>参考素材（可选）</legend><div class="asset-picker-head"><p>${isImageRoute ? '不选素材时，系统仅按主题生成完整提示词。' : '选择素材后，系统会按角色决定图生视频、多模态或运镜参考。'}</p><button type="button" data-go="assets">管理素材</button></div><div class="asset-picker-grid">${available.map(asset => `<label><input type="checkbox" name="asset_ids" value="${escape(asset.id)}" ${selectedAssets.includes(asset.id) ? 'checked' : ''}><span>${asset.kind === 'image' ? `<img src="${asset.preview_url}" alt="">` : `<i>${escape(asset.kind.toUpperCase())}</i>`}<b>${escape(asset.name)}</b><small>${escape(asset.role)}</small></span></label>`).join('')}</div></fieldset>`;
      }
      if (field.type === 'checkbox') return `<label class="studio-checkbox full"><input type="checkbox" name="${field.name}" value="true" ${field.required ? 'required' : ''}><span><b>执行前确认</b>${escape(field.label)}</span></label>`;
      if (field.type === 'textarea') return `<label class="studio-field full"><span>${escape(field.label)}</span><textarea name="${field.name}" ${field.required ? 'required' : ''} placeholder="写清主题、受众收益、画面风格和不可接受项">${escape(value)}</textarea></label>`;
      if (field.type === 'select') return `<label class="studio-field"><span>${escape(field.label)}</span><select name="${field.name}">${field.options.map(option => `<option value="${escape(option)}" ${option === value ? 'selected' : ''}>${escape(optionLabel(option))}</option>`).join('')}</select></label>`;
      const suggested = field.name === 'release_copy' ? `content/${projectSelect.value || '<id>'}/production/release_copy.md` : '';
      const placeholder = suggested || (field.name === 'media_path' ? `content/${projectSelect.value || '<id>'}/production/final.mp4` : '');
      return `<label class="studio-field"><span>${escape(field.label)}</span><input type="${field.type === 'number' ? 'number' : 'text'}" name="${field.name}" value="${escape(value === '' ? suggested : value)}" ${field.required ? 'required' : ''} placeholder="${escape(placeholder)}"></label>`;
    }).join('') || '<p class="no-fields full">此动作不需要额外参数，点击下方按钮即可执行。</p>';
    document.querySelector('#run-title').textContent = present[1];
    document.querySelector('#run-help').textContent = action.external_action ? '勾选配置确认后才会提交生成；不会触发抖音发布。' : (action.id === 'SAVE_PRODUCTION_REQUEST' ? (isImageRoute ? '保存后进入图片提示词、生成与高清导出链。' : '保存后先产出素材策略，再进入视频任务确认卡。') : '执行结果会保存到任务历史，并显示可打开的产物。');
    document.querySelector('.primary-run').textContent = `执行：${present[1]}`;
    if (durable) {
      const initial = Object.fromEntries(new FormData(form).entries());
      initial.asset_ids = new FormData(form).getAll('asset_ids');
      form.querySelectorAll('input[type="checkbox"]:not([name="asset_ids"])').forEach(input => delete initial[input.name]);
      productionDrafts.open(accountId, projectSelect.value, action.id, initial);
      renderDraftStatus(productionDrafts.state(accountId, projectSelect.value, action.id));
    }
    wireGoButtons();
  };
  const renderProjectSummary = () => {
    const item = projects.find(project => project.id === projectSelect.value);
    cache.studioVideoId = projectSelect.value;
    const currentStep = workflowStepForState(item?.state);
    document.querySelectorAll('#workflow-steps li').forEach((step, index) => {
      step.classList.toggle('done', index + 1 < currentStep);
      step.classList.toggle('current', index + 1 === currentStep);
    });
    document.querySelector('#preview-project-title').textContent = item?.title || '尚未选择项目';
    document.querySelector('#preview-route').textContent = item?.type || '—';
    actions.forEach(({id: actionId}) => {
      const unavailable = !studioActionAvailable(actionId, item);
      const button = document.querySelector(`[data-action-id="${actionId}"]`);
      if (button) button.hidden = unavailable;
      const option = actionSelect.querySelector(`option[value="${actionId}"]`);
      if (option) { option.hidden = unavailable; option.disabled = unavailable; }
    });
    document.querySelectorAll('.task-group').forEach(group => {
      group.hidden = [...group.querySelectorAll('.task-choice')].every(button => button.hidden);
    });
    if (!studioActionAvailable(actionSelect.value, item)) actionSelect.value = 'SAVE_PRODUCTION_REQUEST';
    const engineCopy = document.querySelector('#engine-console-copy');
    const engineLink = document.querySelector('#engine-route-link');
    if (engineCopy) engineCopy.innerHTML = !item
      ? '<b>生成路线等待项目</b><small>选择项目后显示图片或视频的实际执行入口。</small>'
      : (item.type === 'IMAGE_CAROUSEL'
        ? '<b>图片生成：Codex 内置图片生成</b><small>自动提示词和视觉 Skill 计划就绪后，由 Codex 任务生成并走高清导出。</small>'
        : (['SEEDANCE','SEEDANCE_2_0','MINIMAX_H3'].includes(item.skillPlan?.providerTarget) ? '<b>视频提示词与任务确认卡</b><small>当前独立平台入口尚未接通，不会从工作台发起模型生成。</small>' : '<b>视频生成：Flova 受控执行</b><small>Flova 可执行和恢复原任务；Seedance / MiniMax H3 独立入口目前仅生成确认卡。</small>'));
    if (engineLink) engineLink.textContent = item?.type === 'IMAGE_CAROUSEL' ? '前往图片任务' : (item ? '前往视频任务' : '查看当前任务');
    document.querySelector('#media-preview').innerHTML = item?.cover ? `<img src="${item.cover}" alt="${escape(item.title)}"><span>${item.imageCount || 0} 张素材</span>` : `<div><span>9:16</span><b>${item ? '当前还没有可预览封面' : '项目素材将在这里预览'}</b><small>${item ? '先运行制作任务或打开项目检查素材' : '选择项目后显示当前封面和阶段'}</small></div>`;
    document.querySelector('#project-evidence').innerHTML = item?.pillar === '工具链测试不发布'
      ? '<div><span>项目用途</span><b>工程测试 · 不发布</b></div><p>仅核验制作链和产物。本项目不进入发布准备，执行状态以下方任务记录为准。</p>'
      : (item ? `<div><span>项目状态</span>${stateBadge(item)}</div><div><span>当前阶段</span><b>${escape(item.stageProgress?.current ? `${item.stageProgress.current.id} ${item.stageProgress.current.title}` : '等待判断')}</b></div><div><span>证据就绪</span><b>${item.stageProgress?.verified || 0}/${item.stageProgress?.total || 18}</b></div><div class="evidence-meter"><i style="width:${Number(item.stageProgress?.verifiedPercent || 0)}%"></i></div>` : '');
    const plan = item?.skillPlan;
    const dispatch = item?.dispatch || {state:'NOT_QUEUED', reason:''};
    const plannedSkills = plan?.skills || [];
    const strategy = item?.assetStrategy || {};
    document.querySelector('#auto-skill-plan').innerHTML = item && plan?.status !== 'NOT_PLANNED'
      ? `<div class="auto-plan-head"><div><span>自动 Skill 编排</span><b>${escape(plan.status === 'READY_FOR_CODEX' ? '组合已生成' : plan.status)}</b></div><i>${plan.stepCount || 0} 步</i></div>${strategy.asset_strategy ? `<p>素材策略：<strong>${escape(strategy.asset_strategy)}</strong> · ${escape(strategy.generation_mode || '')}</p><small>${escape(strategy.reason || '')}</small>` : ''}${plan.selectedVisualSkill ? `<p>主视觉：<strong>${escape(plan.selectedVisualSkill)}</strong> · ${escape(plan.selectionReason || '')}</p>` : '<p>视频视觉由 Brief、素材与分镜自动决定。</p>'}${plan.providerTarget ? `<p>生成目标：<strong>${escape(plan.providerTarget)}</strong>${plan.promptCompiler ? ` · 编译器 ${escape(plan.promptCompiler)}` : ''} · 提示词包${plan.promptPackageReady ? '已生成' : '待生成'}</p>` : ''}${plan.providerSkillName ? `<p>私有执行 Skill：<strong>${escape(plan.providerSkillName)}</strong> · ${escape(plan.providerSkillVisibility || 'PRIVATE')}</p>` : ''}<div class="skill-chip-row">${plannedSkills.slice(0, 9).map(skill => `<span>${escape(skill)}</span>`).join('')}${plannedSkills.length > 9 ? `<span>＋${plannedSkills.length - 9}</span>` : ''}</div><div class="dispatch-line"><span class="badge ${dispatchTone(dispatch.state)}">${escape(dispatchLabel(dispatch.state))}</span><div><b>${escape(dispatch.reason || '等待保存制作计划')}</b><small>${dispatch.attempts ? `已尝试 ${dispatch.attempts} 次` : '尚未开始执行'}${dispatch.workerId ? ` · ${escape(dispatch.workerId)}` : ''}</small></div></div>${(plan.missing || []).length ? `<small class="plan-blocker">缺少：${escape(plan.missing.join('、'))}</small>` : '<small>提示词包须先人工批准；图片生成、视频服务、付费、私人上传、声音和正式发布继续遵守各自人工门。</small>'}`
      : `<div class="auto-plan-empty"><span>自动 Skill 编排</span><b>尚未生成</b><p>填写左侧内容要求并执行后，系统会按项目路线选择需要的组合，不再让你手动挑 Skill。</p></div>`;
    renderFields();
    renderExecutionSummary();
    renderProviderStatus();
  };
  const renderJobs = jobs => {
    if (!isCurrent()) return;
    const visible = WorkbenchState.projectJobs(jobs, projectSelect.value);
    document.querySelector('#job-list').innerHTML = visible.slice(0, 20).map(job => `<button class="job-line" data-job-id="${escape(job.job_id)}"><span class="badge ${jobTone(job.status)}">${escape(jobLabel(job.status))}</span><div><b>${escape(job.action_label)}</b><small>${escape(job.video_id || '全局任务')}</small></div><p>${escape(job.progress?.message || '')}</p><time>${escape(job.created_at)}</time><i>查看</i></button>`).join('') || '<p class="empty">当前项目还没有执行记录。</p>';
    document.querySelectorAll('[data-job-id]').forEach(button => button.addEventListener('click', () => showJobDetail(button.dataset.jobId)));
    renderLatestResult(visible[0]);
    renderExecutionSummary();
    clearTimeout(localPollTimer);
    const dispatch = projects.find(project => project.id === projectSelect.value)?.dispatch;
    if (visible.some(job => ['QUEUED','RUNNING'].includes(job.status)) || ['READY','LEASED'].includes(dispatch?.state)) {
      localPollTimer = setTimeout(() => { if (isCurrent()) loadProjectJobs(); }, 4000);
    }
  };
  const renderLatestResult = job => {
    if (!isCurrent()) return;
    if (!job) {
      document.querySelector('#latest-result').innerHTML = '<span>最近结果</span><p>当前项目尚无任务结果。</p>';
      return;
    }
    const artifactCount = (job.artifacts || []).length;
    const summary = job.progress?.message || job.stderr || job.stdout || '任务已记录';
    document.querySelector('#latest-result').innerHTML = `<div><span>最近结果</span><span class="badge ${jobTone(job.status)}">${escape(jobLabel(job.status))}</span></div><b>${escape(job.action_label)}</b><p>${escape(summary.slice(0, 260))}${summary.length > 260 ? '…' : ''}</p><button type="button" data-latest-job="${escape(job.job_id)}">查看日志与 ${artifactCount} 个产物</button>`;
    document.querySelector('[data-latest-job]')?.addEventListener('click', () => showJobDetail(job.job_id));
  };
  const loadProjectJobs = async () => {
    const projectId = projectSelect.value;
    const button = document.querySelector('#refresh-jobs');
    button.disabled = true;
    try {
      const [result, updatedProject] = await Promise.all([
        api(`/api/jobs?limit=60&videoId=${encodeURIComponent(projectId)}`),
        projectId ? api(`/api/projects/${encodeURIComponent(projectId)}`) : Promise.resolve(null),
      ]);
      if (isCurrent() && projectId === projectSelect.value) {
        if (updatedProject) {
          const index = projects.findIndex(item => item.id === projectId);
          if (index >= 0) projects[index] = updatedProject;
        }
        jobs = jobs.filter(job => job.video_id !== projectId).concat(result.items);
        renderJobs(jobs);
      }
    } catch (error) {
      if (isCurrent() && projectId === projectSelect.value) {
        document.querySelector('#job-list').innerHTML = `<p class="inline-error">任务记录未能刷新：${escape(error.message)}</p>`;
      }
    } finally { button.disabled = false; }
  };
  renderProjectSummary(); renderJobs(jobs); wireGoButtons(); wireCreateRouteButtons(); wireScrollTargets();
  document.querySelector('#job-form').addEventListener('input', rememberStudioInputs);
  document.querySelector('#job-form').addEventListener('change', rememberStudioInputs);
  actionSelect.addEventListener('change', () => { rememberStudioInputs(); renderFields(); });
  document.querySelectorAll('[data-action-id]').forEach(button => button.addEventListener('click', () => { rememberStudioInputs(); actionSelect.value = button.dataset.actionId; renderFields(); }));
  document.querySelectorAll('[data-engine-start]').forEach(button => button.addEventListener('click', async () => {
    button.disabled = true; button.textContent = '启动中…';
    try {
      await api(`/api/integrations/${encodeURIComponent(button.dataset.engineStart)}/start`, {method:'POST',headers:{'Content-Type':'application/json'},body:'{}'});
      showToast('本地生成引擎已启动。');
      setTimeout(() => navigate('studio'), 900);
    } catch (error) { showToast(error.message); button.disabled = false; button.textContent = '启动本地引擎'; }
  }));
  document.querySelectorAll('[data-engine-stop]').forEach(button => button.addEventListener('click', async () => {
    button.disabled = true; button.textContent = '停止中…';
    try {
      await api(`/api/integrations/${encodeURIComponent(button.dataset.engineStop)}/stop`, {method:'POST',headers:{'Content-Type':'application/json'},body:'{}'});
      showToast('本地生成引擎已停止。'); navigate('studio');
    } catch (error) { showToast(error.message); button.disabled = false; button.textContent = '停止'; }
  }));
  projectSelect.addEventListener('change', () => {
    rememberStudioInputs();
    if (projectSelect.value && cache.studioCreateMode) {
      cache.studioCreateMode = null;
      cache.projectDraft = null;
      cache.studioVideoId = projectSelect.value;
      navigate('studio');
      return;
    }
    renderProjectSummary();
    renderJobs(jobs);
    loadProjectJobs();
  });
  document.querySelector('#refresh-jobs').addEventListener('click', loadProjectJobs);
  if (!createMode) loadProjectJobs();
  document.querySelector('#job-form').addEventListener('submit', async event => {
    event.preventDefault();
    const action = currentAction();
    if (action.requires_project && !projectSelect.value) return showToast('请先选择内容项目。');
    rememberStudioInputs();
    const submittedProjectId = projectSelect.value;
    const stillCurrent = () => isCurrent() && projectSelect.value === submittedProjectId;
    const button = event.currentTarget.querySelector('button[type="submit"]');
    if (button.disabled) return;
    button.disabled = true; button.textContent = '正在创建…';
    const errorBox = document.querySelector('#job-error');
    errorBox.hidden = true;
    try {
      const formData = new FormData(event.currentTarget);
      const parameters = Object.fromEntries(formData.entries());
      parameters.asset_ids = formData.getAll('asset_ids');
      const created = await api('/api/jobs/create', {method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({actionId:action.id,videoId:submittedProjectId,parameters})});
      await api(`/api/jobs/${encodeURIComponent(created.job_id)}/run`, {method:'POST',headers:{'Content-Type':'application/json'},body:'{}'});
      showToast(`任务“${created.action_label}”已开始。`);
      const completed = await waitForJob(created.job_id, job => {
        jobs = [job, ...jobs.filter(item => item.job_id !== job.job_id)];
        if (stillCurrent()) renderJobs(jobs);
      }, stillCurrent);
      if (action.id === 'SAVE_PRODUCTION_REQUEST' && completed?.status === 'SUCCEEDED') {
        rememberStudioInputs();
        const currentDraft = drafts.get(accountId, submittedProjectId, action.id);
        if (WorkbenchState.sameInputs(currentDraft, parameters)) {
          drafts.remove(accountId, submittedProjectId, action.id);
          if (stillCurrent() && actionSelect.value === action.id) navigate('studio', false);
        } else {
          showToast('提交的要求已保存；你在执行期间新增的修改仍保留，尚未提交。');
        }
      }
    } catch (error) { showToast(error.message); errorBox.textContent = error.message; errorBox.hidden = false; }
    finally { button.disabled = false; button.textContent = `执行：${actionPresentation[currentAction().id]?.[1] || currentAction().label}`; }
  });
}

async function waitForJob(jobId, onProgress, isCurrent = () => true) {
  for (let attempt = 0; attempt < 80; attempt += 1) {
    if (!isCurrent()) return null;
    const job = await api(`/api/jobs/${encodeURIComponent(jobId)}`);
    if (!isCurrent()) return null;
    onProgress(job);
    if (!['QUEUED','RUNNING'].includes(job.status)) {
      showToast(job.status === 'SUCCEEDED' ? `${job.action_label}已完成。` : (job.progress?.message || job.stderr || `${job.action_label}：${jobLabel(job.status)}`));
      return job;
    }
    await new Promise(resolve => setTimeout(resolve, 500));
  }
  showToast('任务仍在运行，可稍后点击刷新查看。');
}

async function showJobDetail(jobId) {
  clearTimeout(jobDetailTimer);
  let job;
  try { job = await api(`/api/jobs/${encodeURIComponent(jobId)}`); }
  catch (error) { showToast(error.message); return; }
  const artifacts = (job.artifacts || []).map(path => {
    const name = path.split(/[\\/]/).pop();
    const href = path.startsWith(`workspace/workbench/jobs/${job.job_id}/`) ? `/job-asset/${encodeURIComponent(job.job_id)}/${encodeURIComponent(name)}` : '';
    return `<li><span class="file-status ok">✓</span><div><b>${escape(name)}</b><small>${escape(path)}</small></div>${href ? `<a href="${href}" target="_blank" rel="noreferrer">打开</a>` : ''}</li>`;
  }).join('');
  const handles = job.provider ? `<section class="provider-handles"><h3>同一个外部任务</h3><dl>${[['服务商',job.provider.name],['项目 ID',job.provider.project_id],['运行 ID',job.provider.stream_chat_id],['导出 ID',job.provider.export_task_id]].filter(([,value]) => value).map(([label,value]) => `<div><dt>${label}</dt><dd>${escape(value)}</dd></div>`).join('')}</dl><p>中断后恢复这些任务，不重新提交生成。</p></section>` : '';
  const nextAction = typeof job.next_action === 'string' ? job.next_action : (job.next_action?.message || '');
  detailBox.dataset.jobId = jobId;
  detailBox.innerHTML = `<div class="detail job-detail"><h2>${escape(job.action_label)}</h2><span class="badge ${jobTone(job.status)}">${escape(jobLabel(job.status))}</span><p>${escape(job.progress?.message || '')}</p>${job.evidence_mode && job.evidence_mode !== 'REAL' ? `<p class="inline-error">${escape(job.evidence_mode)}：这是模拟证据，不是真实模型生成。</p>` : ''}${nextAction ? `<p><strong>下一步：</strong>${escape(nextAction)}</p>` : ''}<div class="job-user-actions">${jobControlsMarkup(job)}</div><div class="detail-grid"><div><small>项目</small><b>${escape(job.video_id || '全局')}</b></div><div><small>返回码</small><b>${job.returncode ?? '—'}</b></div><div><small>开始</small><b>${escape(job.started_at || '—')}</b></div><div><small>完成</small><b>${escape(job.completed_at || '—')}</b></div></div>${handles}<div class="job-media-grid">${jobMediaMarkup(job)}</div><h3>执行日志</h3><pre class="job-log">${escape(job.stdout || job.stderr || '暂无日志')}</pre>${job.stderr && job.stdout ? `<h3>错误 / 阻断</h3><pre class="job-log error">${escape(job.stderr)}</pre>` : ''}<div class="detail-files"><h3>产物文件</h3><ul>${artifacts || '<li><div><b>无新增文件</b><small>该动作可能是只读检查，或尚未完成。</small></div></li>'}</ul></div><div class="safety"><b>发布边界</b><span>此制作任务不执行抖音上传或发布；模型任务可能按确认内容消耗平台额度。</span></div></div>`;
  wireJobControls(detailBox, async () => { await showJobDetail(jobId); });
  if (!dialog.open) dialog.showModal();
  if (['QUEUED','RUNNING'].includes(job.status)) jobDetailTimer = setTimeout(() => {
    if (dialog.open && detailBox.dataset.jobId === jobId) showJobDetail(jobId);
  }, 4000);
}

async function showTopics(isCurrent = () => true) {
  const [data, shortlist] = await Promise.all([api('/api/topic-intelligence'), api('/api/shortlist')]);
  if (!isCurrent()) return;
  cache.topics = data;
  cache.shortlist = shortlist;
  content.innerHTML = `
    <section class="intelligence-head">
      <div><span class="section-kicker">当前运营档案</span><h2>${escape(data.account.display_name)}</h2><p>${escape(data.account.positioning)}</p></div>
      <div class="intelligence-counts"><div><b>${data.counts.domains}</b><span>选题领域</span></div><div><b>${data.counts.candidates}</b><span>候选题目</span></div><div><b>${data.counts.accountFit}</b><span>适配当前账号</span></div><div><b>${data.counts.trendSignals}</b><span>实时趋势信号</span></div></div>
    </section>
    <section class="trend-radar ${data.trend.status.toLowerCase()}"><div><span class="radar-pulse"></span><div><b>抖音热点雷达 · ${escape(data.trend.status)}</b><p>${escape(data.trend.summary || '等待首次采集')}</p></div></div><aside><span>最近采集 ${escape(data.trend.capturedAt || '—')}</span><small>定时：${data.trend.schedule.map(escape).join(' / ') || '等待调度'}</small></aside></section>
    <section class="panel domain-explorer"><div class="panel-head"><div><span class="section-kicker">全域探索</span><h2>30 个内容方向</h2></div><span class="safe-chip">账号定位只做筛选，不限制浏览</span></div><div class="domain-cloud">${data.domains.map(domain => `<button class="domain-chip ${domain.accountFit ? 'fit' : ''}" data-domain="${escape(domain.domain)}"><b>${escape(domain.domain)}</b><span>${escape(domain.subdomain)}</span></button>`).join('')}</div></section>
    <section class="panel shortlist-panel"><div class="panel-head"><div><span class="section-kicker">本地队列</span><h2>已收藏候选</h2></div><span class="safe-chip">离线保存 · 不自动立项</span></div><div id="shortlist-items"></div></section>
    <section class="panel intelligence-feed"><div class="panel-head"><div><span class="section-kicker">候选情报流</span><h2>历史热点 + 常青题库 + 课程知识 + 历史选题</h2></div></div>
      <div class="intelligence-filters"><input id="topic-query" placeholder="搜索题目、领域、触发词或观众需求"><select id="topic-source"><option value="all">全部来源</option><option value="live_trend">抖音趋势</option><option value="evergreen_pool">长期题库</option></select><select id="topic-fit"><option value="all">显示全域候选</option><option value="fit">只看当前账号适配</option></select></div>
      <div id="candidate-feed" class="candidate-feed"></div>
    </section>`;
  const state = {query: '', source: 'all', fit: 'all', domain: ''};
  const savedIds = new Set(shortlist.items.map(item => item.candidate_id));
  const render = () => renderCandidateFeed(data.candidates, state, savedIds);
  renderShortlist(shortlist.items);
  document.querySelector('#topic-query').addEventListener('input', event => { state.query = event.target.value.trim().toLowerCase(); render(); });
  document.querySelector('#topic-source').addEventListener('change', event => { state.source = event.target.value; render(); });
  document.querySelector('#topic-fit').addEventListener('change', event => { state.fit = event.target.value; render(); });
  document.querySelectorAll('[data-domain]').forEach(button => button.addEventListener('click', () => {
    const selected = button.classList.toggle('selected');
    document.querySelectorAll('[data-domain]').forEach(item => { if (item !== button) item.classList.remove('selected'); });
    state.domain = selected ? button.dataset.domain : '';
    render();
  }));
  render();
}

function renderShortlist(items) {
  const holder = document.querySelector('#shortlist-items');
  if (!holder) return;
  holder.innerHTML = items.length ? items.map(item => `<article class="shortlist-item"><div><b>${escape(item.title)}</b><p>${escape(item.domain)} · ${escape(item.source)} · 准备度 ${number(item.score)}</p></div><div><button class="prefill-shortlist button ghost" data-candidate-id="${escape(item.candidate_id)}" type="button">转为项目草案</button><button class="remove-shortlist danger-link" data-candidate-id="${escape(item.candidate_id)}" type="button">移除</button></div></article>`).join('') : '<p class="empty">还没有收藏候选。先在下面的情报流中保存值得继续看的题目。</p>';
  holder.querySelectorAll('.prefill-shortlist').forEach(button => button.addEventListener('click', () => {
    const item = items.find(candidate => candidate.candidate_id === button.dataset.candidateId);
    if (!item) return;
    const draft = {title:item.title, domain:item.domain, subdomain:item.domain, format:item.format, audienceNeed:item.audience_need};
    beginProjectCreation(routeFromDraft(draft), draft);
  }));
  holder.querySelectorAll('.remove-shortlist').forEach(button => button.addEventListener('click', async () => {
    const candidateId = button.dataset.candidateId;
    try {
      await api('/api/shortlist/remove', {method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({candidateId})});
      showToast('候选已从本地队列移除。');
      showTopics();
    } catch (error) { showToast(error.message); }
  }));
}

function renderCandidateFeed(candidates, state, savedIds = new Set()) {
  const filtered = candidates.filter(item => {
    const haystack = [item.title, item.domain, item.subdomain, item.hook, item.audienceNeed, item.triggers].join(' ').toLowerCase();
    return (!state.query || haystack.includes(state.query)) && (state.source === 'all' || item.sourceType === state.source) && (state.fit === 'all' || item.accountFit) && (!state.domain || item.domain === state.domain);
  }).slice(0, 60);
  const holder = document.querySelector('#candidate-feed');
  holder.innerHTML = filtered.map(item => `<article class="candidate-card ${item.sourceType}"><div class="candidate-source"><span>${escape(item.source)}</span><em>${item.accountFit ? '适配当前账号' : '跨账号观察'}</em></div><h3>${escape(item.title)}</h3><p>${escape(item.hook || item.audienceNeed)}</p><div class="candidate-tags"><span>${escape(item.domain)}</span><span>${escape(item.subdomain)}</span><span>${escape(item.format)}</span><span>风险 ${escape(item.risk)}</span></div><div class="candidate-foot"><strong>${item.score}</strong><button class="save-topic ${savedIds.has(item.id) ? 'saved' : ''}" type="button" ${savedIds.has(item.id) ? 'disabled' : ''}>${savedIds.has(item.id) ? '已收藏' : '收藏候选'}</button><button class="copy-topic" type="button">复制</button><button class="prefill-project" type="button">项目草案</button></div></article>`).join('') || '<p class="empty">没有匹配的候选。</p>';
  holder.querySelectorAll('.save-topic').forEach((button, index) => button.addEventListener('click', async () => {
    const item = filtered[index];
    try {
      await api('/api/shortlist/save', {method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({candidateId:item.id,title:item.title,source:item.source,domain:item.domain,format:item.format,score:item.score,hook:item.hook,audienceNeed:item.audienceNeed,evidence:item.evidence,risk:item.risk})});
      savedIds.add(item.id); button.disabled = true; button.textContent = '已收藏'; button.classList.add('saved');
      showToast('候选已保存到本地队列；不会自动立项。');
      const shortlist = await api('/api/shortlist'); cache.shortlist = shortlist; renderShortlist(shortlist.items);
    } catch (error) { showToast(error.message); }
  }));
  holder.querySelectorAll('.copy-topic').forEach((button, index) => button.addEventListener('click', async () => {
    const item = filtered[index];
    await navigator.clipboard.writeText(`题目：${item.title}\n来源：${item.source}\n领域：${item.domain}/${item.subdomain}\n钩子：${item.hook}\n受众需求：${item.audienceNeed}\n证据：${item.evidence}\n风险：${item.risk}`);
    showToast('候选已复制；尚未立项。');
  }));
  holder.querySelectorAll('.prefill-project').forEach((button, index) => button.addEventListener('click', () => {
    const draft = filtered[index];
    beginProjectCreation(routeFromDraft(draft), draft);
  }));
}

async function showProjects(isCurrent = () => true) {
  const [items, trash] = await Promise.all([api('/api/projects'), api('/api/trash')]);
  if (!isCurrent()) return;
  cache.projects = items;
  const projectTrash = trash.filter(item => item.kind === 'project');
  content.innerHTML = `<div class="toolbar"><p>所有作品从同一个制作中心建立；项目创建后，图片和视频仍按各自路线独立推进。</p><div class="toolbar-actions"><button class="button ghost" data-create-route="IMAGE_CAROUSEL">新建图片作品</button><button class="button dark" data-create-route="ATMOSPHERE_VIDEO">新建视频作品</button><label class="search"><span>筛选</span><input id="project-search" placeholder="标题、栏目或状态"></label></div></div><div id="project-grid" class="project-grid">${items.map(projectCard).join('')}</div>${projectTrash.length ? `<section class="panel trash-panel"><div class="panel-head"><div><span class="section-kicker">可恢复</span><h2>项目回收站</h2></div></div>${projectTrash.map(item => `<article><div><b>${escape(item.registry_row?.title || item.video_id)}</b><span>${escape(item.trashed_at)}</span></div><button class="restore-button" data-kind="project" data-trash-id="${escape(item.trash_id)}">恢复</button></article>`).join('')}</section>` : ''}`;
  wireProjectClicks();
  wireCreateRouteButtons();
  wireRestoreButtons();
  document.querySelector('#project-search').addEventListener('input', event => {
    const query = event.target.value.trim().toLowerCase();
    document.querySelector('#project-grid').innerHTML = items.filter(item => [item.title, item.pillar, item.state, item.type].join(' ').toLowerCase().includes(query)).map(projectCard).join('') || '<p class="empty">没有匹配项目。</p>';
    wireProjectClicks();
  });
}

async function showPipeline(isCurrent = () => true) {
  const data = await api('/api/workflow');
  if (!isCurrent()) return;
  cache.workflow = data;
  const phases = [...new Set(data.stages.map(stage => stage.phase))];
  content.innerHTML = `
    <section class="pipeline-intro">
      <div><h2>从选题到复盘，每个阶段都要留下可核验结果</h2><p>这里不是操作日志，而是全项目统一执行标准。展开任一阶段即可查看留痕、通过条件与失败回退。</p></div>
      <dl><div><dt>阶段</dt><dd>${data.counts.total}</dd></div><div><dt>需要人工</dt><dd>${data.counts.manual}</dd></div><div><dt>自动执行</dt><dd>${data.counts.automated}</dd></div></dl>
    </section>
    <section class="production-boundary" aria-labelledby="production-boundary-title">
      <div class="boundary-heading"><h2 id="production-boundary-title">制作路线边界</h2><p>生成入口已经固定；后处理工具不会冒充生成模型。</p></div>
      <article class="boundary-route"><span class="route-type image">图片</span><div><h3>Codex 端生成</h3><p>提示词与风格 Skill → Codex 图片生成 → 批次审美复核 → 抖音高清导出</p></div><strong>当前主路线</strong></article>
      <article class="boundary-route"><span class="route-type video">视频</span><div><h3>Flova / Seedance / MiniMax H3</h3><p>Brief 与分镜 → 素材策略 → 任务确认卡 → 经确认的服务生成 → 后期与视频 QA</p></div><strong>需确认外部生成</strong></article>
      <aside><b>需要你确认</b><p>付费、私人素材上传、声音克隆、最终成片以及正式发布。</p></aside>
    </section>
    <section class="manual-map"><div class="manual-map-head"><div><h2>必须由你介入的节点</h2><p>其余步骤可由工作流主控推进；这些节点不会被自动跨越。</p></div><span class="mode manual">不得跳过</span></div><ul>${data.manualSummary.map(item => `<li>${escape(item)}</li>`).join('')}</ul></section>
    <div class="pipeline-toolbar"><div><b>18 阶段执行规范</b><span>按内容类型选择路线，证据门保持一致。</span></div><div class="filter-bar" role="group" aria-label="筛选流程阶段"><button class="filter active" data-filter="all">全部阶段</button><button class="filter" data-filter="manual">含人工介入</button><button class="filter" data-filter="auto">自动执行</button><button class="filter" data-filter="release">发布与数据</button></div></div>
    <div id="workflow-list" class="workflow-list">${phases.map((phase, phaseIndex) => { const stageItems = data.stages.filter(stage => stage.phase === phase); return `<section class="workflow-phase"><header class="phase-title"><span>阶段 ${phaseIndex + 1}</span><h2>${escape(phase)}</h2><p>${stageItems.length} 个证据门</p></header><div class="phase-stages">${stageItems.map((stage, index) => stageCard(stage, index === 0)).join('')}</div></section>`; }).join('')}</div>`;
  document.querySelectorAll('.filter').forEach(button => button.addEventListener('click', () => {
    document.querySelectorAll('.filter').forEach(item => item.classList.toggle('active', item === button));
    const mode = button.dataset.filter;
    document.querySelectorAll('.workflow-stage').forEach(stage => {
      const show = mode === 'all' || (mode === 'manual' && stage.dataset.manual === 'true') || (mode === 'auto' && stage.dataset.mode === 'auto') || (mode === 'release' && ['发布准备','正式发布','数据与复盘'].includes(stage.dataset.phase));
      stage.hidden = !show;
    });
    document.querySelectorAll('.workflow-phase').forEach(section => section.hidden = !section.querySelector('.workflow-stage:not([hidden])'));
  }));
}

function stageCard(stage, open = false) {
  return `<details class="workflow-stage" data-mode="${stage.mode}" data-manual="${Boolean(stage.manual)}" data-phase="${escape(stage.phase)}" ${open ? 'open' : ''}>
    <summary><span class="stage-id">${escape(stage.id)}</span><div class="stage-copy"><b>${escape(stage.title)}</b><small>${escape(stage.purpose)}</small></div><span class="stage-owner">${escape(stage.owner)}</span>${modeBadge(stage.mode)}<span class="chevron" aria-hidden="true"></span></summary>
    <div class="stage-detail"><div><span>必须留痕</span><p>${escape(stage.evidence)}</p></div><div><span>通过条件</span><p>${escape(stage.pass)}</p></div><div><span>失败回退</span><p>${escape(stage.rollback)}</p></div>${stage.manual ? `<div class="manual-detail"><span>人工介入</span><p>${escape(stage.manual)}</p></div>` : ''}</div>
  </details>`;
}

async function showRelease(isCurrent = () => true) {
  const [items, metrics] = await Promise.all([api('/api/projects'), api('/api/metrics')]);
  if (!isCurrent()) return;
  const relevant = items.filter(item => ['READY_FOR_USER','USER_APPROVED','PREPARED_IN_DOUYIN','PUBLISHED'].includes(item.state));
  const onlineAction = cache.runtime?.runtimeMode === 'offline' ? '<span class="mode manual">离线模式下不可打开平台</span>' : '<a class="button light" target="_blank" rel="noreferrer" href="https://creator.douyin.com/creator-micro/content/upload">打开发布页</a>';
  content.innerHTML = `
    <section class="release-guard"><div><span class="guard-icon">!</span><div><b>正式发布是唯一不可自动跨越的动作</b><p>工作台可以校验、准备上传并打开创作者中心；最终点击由你完成。</p></div></div>${onlineAction}</section>
    <div class="release-grid"><section class="panel"><div class="panel-head"><div><span class="section-kicker">发布队列</span><h2>可进入发布或监控阶段</h2></div></div>${relevant.map(projectRow).join('') || '<p class="empty">暂无项目。</p>'}</section>
    <aside class="panel release-checklist"><span class="section-kicker">发布前 6 项</span><h2>每次都要核对</h2><ol><li>当前成品与 QA 绑定同一 manifest</li><li>标题、文案、图片顺序和音乐策略已锁定</li><li>你看过最终画面 / 视频 / 声音</li><li>最终批准绑定 release package hash</li><li>Prepare-only 回执显示 publish_clicked=false</li><li>你手动发布后登记实际时间和曲目</li></ol></aside></div>
    <section class="panel metrics-panel"><div class="panel-head"><div><span class="section-kicker">只读监控</span><h2>指标快照</h2></div><span class="safe-chip">只追加 · 不互动</span></div>${metrics.length ? `<div class="metrics-table"><div class="metrics-head"><span>作品 / 检查点</span><span>播放</span><span>点赞</span><span>收藏</span><span>分享</span><span>采集时间</span></div>${metrics.slice(0, 24).map(metric => `<article><div><b>${escape(metric.title)}</b><span>${escape(metric.checkpoint || '未标记')}</span></div><strong>${number(metric.plays)}</strong><strong>${number(metric.likes)}</strong><strong>${number(metric.collects)}</strong><strong>${number(metric.shares)}</strong><time>${escape(metric.captured_at || '')}</time></article>`).join('')}</div>` : '<p class="empty">尚无可核验指标。字段不可见时保持为空，不会写成 0。</p>'}</section>`;
  wireProjectClicks();
}

const assetRoleLabels = {
  STYLE_REFERENCE: '风格参考', COMPOSITION_REFERENCE: '构图参考', CHARACTER_IDENTITY: '人物一致性',
  SCENE_IDENTITY: '场景一致性', CAMERA_MOTION_REFERENCE: '运镜参考', FIRST_FRAME: '首帧',
  LAST_FRAME: '尾帧', CONTENT_FACT_REFERENCE: '内容事实', SOURCE_TRANSFORM: '原始变换素材', AUDIO_REFERENCE: '声音参考',
};

function assetPreview(item) {
  if (item.status === 'TRASHED') return '<div class="asset-file-placeholder"><b>已在回收站</b><span>恢复后可重新预览和绑定</span></div>';
  if (item.kind === 'image') return `<img src="${item.preview_url}" alt="${escape(item.name)}" loading="lazy">`;
  if (item.kind === 'video') return `<video src="${item.preview_url}" controls preload="metadata"></video>`;
  return `<audio src="${item.preview_url}" controls preload="metadata"></audio>`;
}

function assetCard(item) {
  const projects = (item.project_ids || []).length ? `${item.project_ids.length} 个项目已使用` : '尚未绑定项目';
  return `<article class="media-asset-card ${item.status === 'TRASHED' ? 'trashed' : ''}" data-asset-kind="${escape(item.kind)}"><div class="asset-preview">${assetPreview(item)}</div><div class="asset-card-body"><div class="asset-card-title"><div><b>${escape(item.name)}</b><small>${escape(item.filename || '')}</small></div><span>${escape(assetRoleLabels[item.role] || item.role)}</span></div><dl><div><dt>权利</dt><dd>${escape(item.rights_status)}</dd></div><div><dt>用途</dt><dd>${escape(projects)}</dd></div><div><dt>保留</dt><dd>${escape(item.retain || '未填写')}</dd></div><div><dt>改变</dt><dd>${escape(item.change || '未填写')}</dd></div></dl><div class="asset-card-foot"><small>${Math.max(1, Math.round((item.size_bytes || 0) / 1024))} KB · ${escape((item.sha256 || '').slice(0, 10))}</small>${item.status === 'TRASHED' ? `<button class="text-button" type="button" data-restore-asset="${escape(item.id)}">恢复</button>` : `<button class="danger-link" type="button" data-trash-asset="${escape(item.id)}">移入回收站</button>`}</div></div></article>`;
}

async function showAssets(isCurrent = () => true) {
  const [assetData, projects] = await Promise.all([api('/api/assets?includeTrash=true'), api('/api/projects')]);
  if (!isCurrent()) return;
  const items = assetData.items || [];
  content.innerHTML = `<section class="asset-library-intro"><div><h2>素材库只负责保存和解释素材</h2><p>图片和视频制作共用这一个库，但进入项目后使用不同生产线。公开参考素材不会自动被当成可发布成品。</p></div><dl><div><dt>素材</dt><dd>${items.filter(item => item.status !== 'TRASHED').length}</dd></div><div><dt>已绑定</dt><dd>${items.filter(item => (item.project_ids || []).length).length}</dd></div><div><dt>回收站</dt><dd>${items.filter(item => item.status === 'TRASHED').length}</dd></div></dl></section>
    <section class="asset-import panel"><div class="panel-head"><div><h2>放入图片、视频或音频</h2><p class="muted">文件会复制到 G:\\抖音视频\\assets\\library，原始文件保持不变。</p></div><span class="safe-chip">最大 512 MB / 文件</span></div><form id="asset-upload-form"><label class="asset-drop full"><span>选择素材文件</span><input name="file" type="file" accept="image/*,video/*,audio/*" required><small>支持常见图片、MP4/MOV/WebM 与常见音频格式</small></label><label>素材名称<input name="name" placeholder="便于检索的名称"></label><label>素材权利<select name="rights_status"><option value="OWNED">自有或本人制作</option><option value="LICENSED">已取得许可</option><option value="PUBLIC_REFERENCE_ONLY">仅作公开参考</option><option value="PENDING_REVIEW">待确认</option></select></label><label>参考作用<select name="role">${Object.entries(assetRoleLabels).map(([value,label]) => `<option value="${value}">${escape(label)}</option>`).join('')}</select></label><label class="full">希望保留什么<textarea name="retain" placeholder="例如：暖色胶片质感、上下留白、低机位运镜"></textarea></label><label class="full">必须改变什么<textarea name="change" placeholder="例如：人物、地点、文字和贴纸排列全部改变"></textarea></label><label class="studio-checkbox full"><input name="external_upload_allowed" type="checkbox" value="true"><span><b>外部模型上传许可</b>允许把这份素材上传到已确认的 Seedance、MiniMax H3 或 Flova 任务。未勾选时系统会保持人工确认门。</span></label><button class="button dark full" type="submit">复制到素材库</button></form>
    <details class="path-import"><summary>登记电脑上已有的素材路径</summary><form id="asset-path-form"><label class="full">本地绝对路径<input name="path" required placeholder="G:\\抖音视频\\workspace\\reference.mp4"></label><label>素材权利<select name="rights_status"><option value="OWNED">自有或本人制作</option><option value="LICENSED">已取得许可</option><option value="PUBLIC_REFERENCE_ONLY">仅作公开参考</option><option value="PENDING_REVIEW">待确认</option></select></label><label>参考作用<select name="role">${Object.entries(assetRoleLabels).map(([value,label]) => `<option value="${value}">${escape(label)}</option>`).join('')}</select></label><button class="button ghost full" type="submit">复制并登记</button></form></details></section>
    <div class="asset-toolbar"><label class="search"><span>搜索</span><input id="asset-search" placeholder="名称、角色、保留或改变"></label><div class="asset-filters"><button class="filter active" data-asset-filter="ACTIVE">使用中</button><button class="filter" data-asset-filter="image">图片</button><button class="filter" data-asset-filter="video">视频</button><button class="filter" data-asset-filter="audio">音频</button><button class="filter" data-asset-filter="TRASHED">回收站</button></div></div><div id="asset-grid" class="media-asset-grid"></div>
    <section class="asset-binding-note"><b>如何用于项目</b><p>进入制作中心，在“保存要求并自动编排 Skills”中勾选素材。系统会写入项目绑定清单，并按项目路线判断文生、图生、多模态或条件性图片锚点。</p><div><button class="button dark" data-go="studio" type="button">进入制作中心</button></div></section>`;
  let filter = 'ACTIVE';
  const render = () => {
    const query = document.querySelector('#asset-search').value.trim().toLowerCase();
    const filtered = items.filter(item => {
      const statusMatch = filter === 'ACTIVE' ? item.status !== 'TRASHED' : filter === 'TRASHED' ? item.status === 'TRASHED' : item.status !== 'TRASHED' && item.kind === filter;
      return statusMatch && `${item.name} ${item.role} ${item.retain} ${item.change}`.toLowerCase().includes(query);
    });
    document.querySelector('#asset-grid').innerHTML = filtered.map(assetCard).join('') || '<p class="empty">当前分类没有素材。可以从上方放入文件。</p>';
    wireAssetActions();
  };
  const wireAssetActions = () => {
    document.querySelectorAll('[data-trash-asset]').forEach(button => button.addEventListener('click', async () => {
      const id = button.dataset.trashAsset;
      const approved = await requestConfirmation({title:'将素材移入回收站',message:'素材不会永久删除；已绑定项目会保留历史清单，但新任务不会再使用它。',expected:id,submitLabel:'确认移入素材回收站'});
      if (!approved) return;
      button.disabled = true;
      try { await api(`/api/assets/${encodeURIComponent(id)}/trash`, {method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({confirm:id})}); showToast('素材已移入回收站。'); navigate('assets'); }
      catch (error) { showToast(`素材未移动：${error.message}`); button.disabled = false; }
    }));
    document.querySelectorAll('[data-restore-asset]').forEach(button => button.addEventListener('click', async () => {
      const id = button.dataset.restoreAsset; button.disabled = true;
      try { await api(`/api/assets/${encodeURIComponent(id)}/restore`, {method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({confirm:id})}); showToast('素材已恢复。'); navigate('assets'); }
      catch (error) { showToast(`恢复失败：${error.message}`); button.disabled = false; }
    }));
  };
  document.querySelector('#asset-search').addEventListener('input', render);
  document.querySelectorAll('[data-asset-filter]').forEach(button => button.addEventListener('click', () => { filter = button.dataset.assetFilter; document.querySelectorAll('[data-asset-filter]').forEach(item => item.classList.toggle('active', item === button)); render(); }));
  document.querySelector('#asset-upload-form').addEventListener('submit', async event => {
    event.preventDefault(); const form = event.currentTarget; const button = form.querySelector('button[type="submit"]'); const data = new FormData(form); const file = data.get('file');
    if (!(file instanceof File) || !file.size) return showToast('请先选择素材文件。');
    const metadata = {filename:file.name,name:data.get('name') || file.name.replace(/\.[^.]+$/, ''),rights_status:data.get('rights_status'),role:data.get('role'),retain:data.get('retain'),change:data.get('change'),external_upload_allowed:data.get('external_upload_allowed') === 'true',source_type:'USER_UPLOAD'};
    button.disabled = true; button.textContent = '正在复制…';
    try { await api('/api/assets/import',{method:'POST',headers:{'X-Asset-Metadata':encodeURIComponent(JSON.stringify(metadata))},body:file}); showToast('素材已复制到 G 盘素材库。'); navigate('assets'); }
    catch (error) { showToast(`导入失败：${error.message}`); button.disabled = false; button.textContent = '复制到素材库'; }
  });
  document.querySelector('#asset-path-form').addEventListener('submit', async event => {
    event.preventDefault(); const form = event.currentTarget; const button = form.querySelector('button[type="submit"]'); const payload = Object.fromEntries(new FormData(form).entries()); button.disabled = true;
    try { await api('/api/assets/register-path',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(payload)}); showToast('已有文件已复制并登记。'); navigate('assets'); }
    catch (error) { showToast(`登记失败：${error.message}`); button.disabled = false; }
  });
  render(); wireGoButtons();
}

async function showSkills(isCurrent = () => true) {
  const [skills, trash] = await Promise.all([api('/api/skills'), api('/api/trash')]);
  if (!isCurrent()) return;
  const skillTrash = trash.filter(item => item.kind === 'skill');
  const categories = [...new Set(skills.map(item => item.category || '其他'))].sort((a, b) => a.localeCompare(b, 'zh-CN'));
  content.innerHTML = `<div class="toolbar skill-toolbar"><div><b>${skills.length} 个可管理 Skill</b><p>移入回收站后 Codex 将不再调用它；系统 Skill 不显示，也不会被工作台删除。</p></div><div class="skill-filters"><label><span>能力分类</span><select id="skill-category"><option value="all">全部分类</option>${categories.map(category => `<option value="${escape(category)}">${escape(category)}</option>`).join('')}</select></label><label class="search"><span>搜索</span><input id="skill-search" placeholder="名称或用途"></label></div></div><div id="skill-grid" class="skill-grid"></div>${skillTrash.length ? `<section class="panel trash-panel"><div class="panel-head"><div><span class="section-kicker">可恢复</span><h2>Skill 回收站</h2></div></div>${skillTrash.map(item => `<article><div><b>${escape(item.skill_name)}</b><span>${escape(item.trashed_at)}</span></div><button class="restore-button" data-kind="skill" data-trash-id="${escape(item.trash_id)}">恢复</button></article>`).join('')}</section>` : ''}`;
  const renderSkills = () => {
    const query = document.querySelector('#skill-search').value.trim().toLowerCase();
    const category = document.querySelector('#skill-category').value;
    const filtered = skills.filter(item => (category === 'all' || item.category === category) && `${item.name} ${item.description} ${item.compatibility}`.toLowerCase().includes(query));
    document.querySelector('#skill-grid').innerHTML = filtered.map(skillCard).join('') || '<p class="empty">没有匹配的 Skill。清除搜索或切换分类后重试。</p>';
    wireSkillTrash();
  };
  renderSkills(); wireRestoreButtons();
  document.querySelector('#skill-search').addEventListener('input', renderSkills);
  document.querySelector('#skill-category').addEventListener('change', renderSkills);
}

async function showOffline(isCurrent = () => true) {
  const [runtime, shortlist, items] = await Promise.all([api('/api/offline'), api('/api/shortlist'), api('/api/projects')]);
  if (!isCurrent()) return;
  cache.runtime = runtime;
  const projectQueue = items.filter(item => item.stageProgress?.current).sort((a, b) => (b.updatedAt || '').localeCompare(a.updatedAt || ''));
  content.innerHTML = `
    <section class="offline-hero ${runtime.offlineReady ? 'ready' : 'warning'}"><div><span class="section-kicker">LOCAL-FIRST</span><h2>${runtime.offlineReady ? '断网后仍可继续大部分内容工作' : '离线运行存在缺项'}</h2><p>${escape(runtime.policy)}</p></div><div class="offline-actions"><span class="network-chip">浏览器网络：${navigator.onLine ? '可用' : '离线'}</span><button id="export-offline" class="button dark" type="button">导出独立离线快照</button></div></section>
    <div class="offline-layout"><section class="panel"><div class="panel-head"><div><span class="section-kicker">完全本地</span><h2>可离线运行的模块</h2></div><span class="safe-chip">${runtime.localModules.filter(item => item.ready).length}/${runtime.localModules.length} 就绪</span></div><div class="capability-grid">${runtime.localModules.map(item => `<article class="offline-cap ${item.ready ? 'ready' : 'missing'}"><span>${item.ready ? '✓' : '!'}</span><div><b>${escape(item.label)}</b><p>${escape(item.mode)}</p><small>${escape(item.path)}</small></div></article>`).join('')}</div></section>
      <aside class="panel"><div class="panel-head"><div><span class="section-kicker">缓存可读</span><h2>断网时保留</h2></div></div>${runtime.cachedModules.map(item => `<article class="cache-row"><div><b>${escape(item.label)}</b><p>${escape(item.note)}</p></div><span>${escape(item.freshness || '暂无')}</span></article>`).join('')}</aside></div>
    <section class="panel"><div class="panel-head"><div><span class="section-kicker">联网边界</span><h2>必须连接平台的环节</h2></div><span class="mode manual">不会离线伪装完成</span></div><div class="online-boundaries">${runtime.onlineModules.map(item => `<article><b>${escape(item.label)}</b><p>${escape(item.reason)}</p><small>${escape(item.guard)}</small></article>`).join('')}</div></section>
    <div class="offline-layout queue-layout"><section class="panel"><div class="panel-head"><div><span class="section-kicker">选题队列</span><h2>已收藏，尚未立项</h2></div><span>${shortlist.items.length} 项</span></div>${shortlist.items.map(item => `<article class="queue-row"><div><b>${escape(item.title)}</b><p>${escape(item.domain)} · ${escape(item.source)}</p></div><strong>${number(item.score)}</strong></article>`).join('') || '<p class="empty">暂无收藏候选。</p>'}</section>
      <section class="panel"><div class="panel-head"><div><span class="section-kicker">制作队列</span><h2>按当前门推进</h2></div><span>${projectQueue.length} 项</span></div>${projectQueue.slice(0,12).map(item => `<article class="queue-row" data-project="${escape(item.id)}"><div><b>${escape(item.title)}</b><p>${escape(item.stageProgress.current.id)} ${escape(item.stageProgress.current.title)} · ${escape(item.stageProgress.current.status === 'waiting_user' ? '等待你确认' : '可推进')}</p></div><strong>${item.stageProgress.verified}/${item.stageProgress.total}</strong></article>`).join('') || '<p class="empty">当前没有待推进项目。</p>'}</section></div>
    <section class="snapshot-result"><div><b>独立快照路径</b><code>${escape(runtime.snapshotPath)}</code><p>快照是单个 HTML 文件，不需要启动工作台，也不会请求网络；重新导出即可刷新。</p></div><a id="open-offline-snapshot" class="button ghost" href="/offline/workbench_offline.html" target="_blank" ${runtime.snapshotExists ? '' : 'hidden'}>打开最近快照</a></section>`;
  document.querySelector('#export-offline').addEventListener('click', async event => {
    const button = event.currentTarget; button.disabled = true; button.textContent = '正在导出…';
    try {
      const result = await api('/api/offline/export', {method:'POST',headers:{'Content-Type':'application/json'},body:'{}'});
      showToast(`离线快照已更新：${result.path}`);
      const link = document.querySelector('#open-offline-snapshot'); link.hidden = false; link.href = result.url;
    } catch (error) { showToast(error.message); }
    finally { button.disabled = false; button.textContent = '导出独立离线快照'; }
  });
  wireProjectClicks();
}
const skillCard = skill => `<article class="skill-card"><div class="skill-icon">S</div><div class="skill-card-copy"><span class="skill-category">${escape(skill.category || '其他')}</span><code>${escape(skill.name)}</code><p>${escape(skill.description || '本地可复用技能')}</p>${skill.compatibility ? `<small>${escape(skill.compatibility)}</small>` : ''}<div class="skill-card-actions">${skill.license ? `<span>许可：${escape(skill.license)}</span>` : '<span>许可未在 Skill 中声明</span>'}<button class="danger-link" data-trash-skill="${escape(skill.name)}" type="button">移入回收站</button></div></div></article>`;

async function showDetail(id) {
  clearTimeout(jobDetailTimer);
  delete detailBox.dataset.jobId;
  const item = await api('/api/projects/' + encodeURIComponent(id));
  const images = item.images.map(src => `<img src="${src}" alt="${escape(item.title)}">`).join('');
  const artifacts = Object.entries(item.artifacts).map(([key, value]) => `<li><span class="file-status ${value.exists ? 'ok' : 'missing'}">${value.exists ? '✓' : '—'}</span><div><b>${escape(key)}</b><small>${escape(value.path)}</small></div></li>`).join('');
  const progress = item.stageProgress || {stages:[],verified:0,total:18,evidenceGaps:0};
  const statusLabel = {complete:'证据齐全',evidence_gap:'历史缺口',ready:'可推进',waiting_user:'等待你确认',pending:'尚未到达'};
  const stages = progress.stages.map(stage => `<article class="detail-stage ${stage.status}"><span>${escape(stage.id)}</span><div><b>${escape(stage.title)}</b><p>${escape(statusLabel[stage.status] || stage.status)}${stage.missing?.length ? ` · 缺 ${stage.missing.map(escape).join('、')}` : ''}</p></div>${modeBadge(stage.mode)}</article>`).join('');
  detailBox.innerHTML = `<div class="detail"><p class="eyebrow">${escape(item.id)}</p><h2>${escape(item.title)}</h2>${stateBadge(item)}<p class="detail-hypothesis">${escape(item.hypothesis)}</p>
    <div class="detail-grid"><div><small>路线</small><b>${escape(item.type || '—')}</b></div><div><small>当前状态</small><b>${escape(item.state)}</b></div><div><small>证据就绪度</small><b>${progress.verified}/${progress.total}</b></div><div><small>历史证据缺口</small><b>${progress.evidenceGaps || 0}</b></div></div>
    <div class="detail-actions"><button class="button dark" data-studio-action="SAVE_PRODUCTION_REQUEST" data-studio-project="${escape(item.id)}">保存制作参数</button><button class="button ghost" data-studio-action="PROJECT_TRACE" data-studio-project="${escape(item.id)}">证据追踪</button><button class="button ghost" data-studio-action="METRICS_SUMMARY" data-studio-project="${escape(item.id)}">指标摘要</button></div>
    ${images ? `<div class="gallery">${images}</div>` : '<p class="empty">尚无可预览素材。</p>'}<div class="detail-files"><h3>关键产物</h3><ul>${artifacts}</ul></div><div class="detail-workflow"><h3>18 阶段就绪度</h3>${stages}</div><button class="button danger" data-trash-project="${escape(item.id)}" data-published="${item.state === 'PUBLISHED'}">移入项目回收站</button></div>`;
  dialog.showModal();
  wireProjectClicks();
  document.querySelectorAll('[data-studio-action]').forEach(button => button.addEventListener('click', () => {
    cache.studioCreateMode = null;
    cache.projectDraft = null;
    cache.studioVideoId = button.dataset.studioProject;
    cache.studioAction = button.dataset.studioAction;
    dialog.close();
    navigate('studio');
  }));
}

async function createProject(event) {
  event.preventDefault();
  const form = event.currentTarget;
  const nextView = form.dataset.nextView || 'projects';
  const button = form.querySelector('button[type="submit"]');
  if (button.disabled) return;
  const originalLabel = button.textContent;
  const payload = Object.fromEntries(new FormData(form).entries());
  payload.accountId = form.dataset.account || cache.accounts?.activeAccountId;
  const errorBox = form.querySelector('#create-error');
  if (errorBox) errorBox.hidden = true;
  const originNavigationId = navigationId;
  button.disabled = true; button.textContent = '正在创建…';
  try {
    const item = await api('/api/projects/create', {method:'POST', headers:{'Content-Type':'application/json'}, body:JSON.stringify(payload)});
    showToast(`项目“${item.title}”已创建，当前停在 IDEA。`);
    drafts.remove(form.dataset.account || cache.accounts?.activeAccountId || '', '', 'CREATE_PROJECT');
    if (originNavigationId !== navigationId) return;
    cache.studioVideoId = item.id;
    cache.studioAction = 'SAVE_PRODUCTION_REQUEST';
    cache.studioCreateMode = null;
    cache.studioVideoType = null;
    cache.projectDraft = null;
    navigate(nextView, false);
  } catch (error) {
    showToast(error.message); button.disabled = false; button.textContent = originalLabel;
    if (errorBox) { errorBox.textContent = error.message; errorBox.hidden = false; }
  }
}

async function trashProject(button) {
  const id = button.dataset.trashProject;
  const isPublished = button.dataset.published === 'true';
  const approved = await requestConfirmation({
    title: '将项目移入回收站',
    message: '只移除本地工作流项目，不会删除抖音上的作品。项目可从 G 盘回收站恢复。',
    expected: id,
    acknowledgement: isPublished ? '我知道：这是已发布项目，移入后将停止本地指标监控。' : '',
    submitLabel: '确认移入项目回收站',
  });
  if (!approved) return;
  const publishedAcknowledged = isPublished;
  button.disabled = true;
  try {
    await api(`/api/projects/${encodeURIComponent(id)}/trash`, {method:'POST', headers:{'Content-Type':'application/json'}, body:JSON.stringify({confirm:id,publishedAcknowledged})});
    if (dialog.open) dialog.close();
    showToast('项目已移入 G 盘回收站，可在项目页恢复。');
    navigate('projects');
  } catch (error) { showToast(`项目未移动：${error.message}`); }
  finally { button.disabled = false; }
}

function wireSkillTrash() {
  document.querySelectorAll('[data-trash-skill]').forEach(button => button.addEventListener('click', async () => {
    const name = button.dataset.trashSkill;
    const approved = await requestConfirmation({
      title: '将 Skill 移入回收站',
      message: 'Skill 将从 Codex 可调用列表中移除，并保存在 G 盘回收站中，可随时恢复。',
      expected: name,
      submitLabel: '确认移入 Skill 回收站',
    });
    if (!approved) return;
    button.disabled = true;
    try {
      await api(`/api/skills/${encodeURIComponent(name)}/trash`, {method:'POST', headers:{'Content-Type':'application/json'}, body:JSON.stringify({confirm:name})});
      showToast('Skill 已移入 G 盘回收站。'); navigate('skills');
    } catch (error) { showToast(`Skill 未移动：${error.message}`); }
    finally { button.disabled = false; }
  }));
}

function wireRestoreButtons() {
  document.querySelectorAll('.restore-button').forEach(button => button.addEventListener('click', async () => {
    const trashId = button.dataset.trashId;
    const approved = await requestConfirmation({
      title: '从回收站恢复',
      message: '恢复后会重新出现在原来的项目或 Skill 列表中。',
      submitLabel: '确认恢复',
    });
    if (!approved) return;
    button.disabled = true;
    try {
      await api('/api/trash/restore', {method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({kind:button.dataset.kind,trashId,confirm:trashId})});
      showToast('已恢复。'); navigate(button.dataset.kind === 'project' ? 'projects' : 'skills');
    } catch (error) { showToast(`恢复失败：${error.message}`); }
    finally { button.disabled = false; }
  }));
}

function wireGoButtons() {
  document.querySelectorAll('[data-go]').forEach(button => { button.onclick = () => navigate(button.dataset.go); });
}

function routeFromDraft(draft = {}) {
  const format = String(draft.format || '').toLowerCase();
  if (/讲解|口播|科普|课程/.test(format)) return 'NARRATED_EXPLAINER';
  if (/视频|短剧|动画|vlog/.test(format)) return 'ATMOSPHERE_VIDEO';
  return 'IMAGE_CAROUSEL';
}

function beginProjectCreation(route, draft) {
  rememberStudioInputs();
  if (draft) {
    drafts.remove(cache.accounts?.activeAccountId || '', '', 'CREATE_PROJECT');
    cache.projectDraft = draft;
  }
  cache.studioCreateMode = route === 'IMAGE_CAROUSEL' ? 'IMAGE_CAROUSEL' : 'VIDEO';
  cache.studioVideoType = route === 'IMAGE_CAROUSEL' ? null : route;
  navigate('studio', false);
}

function wireCreateRouteButtons() {
  document.querySelectorAll('[data-create-route]').forEach(button => button.addEventListener('click', () => {
    beginProjectCreation(button.dataset.createRoute);
  }));
}

function wireScrollTargets() {
  document.querySelectorAll('[data-scroll-target]').forEach(button => button.addEventListener('click', () => {
    document.getElementById(button.dataset.scrollTarget)?.scrollIntoView({behavior:'smooth', block:'start'});
  }));
}

const views = {studio: showStudio, assets: showAssets, overview, topics: showTopics, projects: showProjects, pipeline: showPipeline, release: showRelease, skills: showSkills, offline: showOffline};

function showConnectionError(error, view = 'studio') {
  content.innerHTML = `<section class="error-state" role="alert"><h2>工作台暂时无法读取数据</h2><p>${escape(error.message)}</p><p>如果本地服务未启动，请双击 <code>G:\\抖音视频\\workbench\\打开工作台.cmd</code>。无需重新创建项目。</p><button id="retry-connection" class="button dark" type="button">重试连接</button></section>`;
  document.querySelector('#retry-connection').onclick = () => initialize(view);
}

function navigate(view, preserveInputs = true) {
  if (!views[view]) return;
  if (preserveInputs) rememberStudioInputs();
  const thisNavigation = ++navigationId;
  const button = document.querySelector(`[data-view="${view}"]`);
  document.querySelectorAll('.nav-item').forEach(item => {
    const active = item === button;
    item.classList.toggle('active', active);
    if (active) item.setAttribute('aria-current', 'page');
    else item.removeAttribute('aria-current');
  });
  const [eyebrow, title, subtitle] = pageMeta[view];
  pageEyebrow.textContent = eyebrow;
  pageTitle.textContent = title;
  pageSubtitle.textContent = subtitle;
  content.innerHTML = '<div class="loading"><span></span>正在读取…</div>';
  return views[view](() => thisNavigation === navigationId).catch(error => {
    if (thisNavigation === navigationId) showConnectionError(error, view);
  });
}

document.querySelector('.sidebar').addEventListener('click', event => {
  const button = event.target.closest('[data-view]');
  if (button) {
    navigate(button.dataset.view);
    if (window.matchMedia('(max-width: 760px)').matches) setMobileMenu(false);
  }
});
function setMobileMenu(open) {
  document.querySelector('.sidebar').classList.toggle('mobile-open', open);
  document.querySelector('#mobile-menu-toggle').setAttribute('aria-expanded', String(open));
}
document.querySelector('#mobile-menu-toggle').addEventListener('click', () => {
  setMobileMenu(document.querySelector('#mobile-menu-toggle').getAttribute('aria-expanded') !== 'true');
});
document.querySelector('.close').addEventListener('click', () => dialog.close());
dialog.addEventListener('close', () => { clearTimeout(jobDetailTimer); delete detailBox.dataset.jobId; });
window.addEventListener('beforeunload', event => {
  if (productionDrafts.hasUnsaved()) {
    event.preventDefault();
    event.returnValue = '';
  }
});
document.addEventListener('visibilitychange', () => {
  if (document.visibilityState === 'hidden') productionDrafts.flushAll();
});
document.querySelector('#account-switch').addEventListener('change', async event => {
  rememberStudioInputs();
  const select = event.currentTarget;
  select.disabled = true;
  try {
    await api('/api/accounts/select', {method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({accountId:select.value})});
    resetAccountContext();
    await loadAccounts();
    showToast('运营档案已切换；平台账号登录不会自动改变。');
    navigate(document.querySelector('.nav-item.active')?.dataset.view || 'studio', false);
  } catch (error) { showToast(error.message); select.value = cache.accounts?.activeAccountId || ''; }
  finally { select.disabled = false; }
});
document.querySelector('#account-create').addEventListener('click', async () => {
  const displayName = window.prompt('新账号档案名称：'); if (!displayName) return;
  const accountId = window.prompt('账号档案 ID（英文、数字、短横线）：'); if (!accountId) return;
  const positioning = window.prompt('一句话账号定位：'); if (!positioning) return;
  const audience = window.prompt('核心受众：') || '待补充';
  try {
    await api('/api/accounts/create',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({displayName,accountId,positioning,audience,allowedDomains:['ALL']})});
    rememberStudioInputs(); resetAccountContext();
    await loadAccounts(); showToast('新账号档案已创建并切换。平台登录仍需你手动完成。'); navigate('overview', false);
  } catch (error) { showToast(error.message); }
});
document.querySelector('#audit').addEventListener('click', async event => {
  const button = event.currentTarget;
  button.disabled = true;
  button.textContent = '审计中…';
  try {
    const created = await api('/api/jobs/create', {method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({actionId:'WORKFLOW_AUDIT',videoId:'',parameters:{}})});
    await api(`/api/jobs/${encodeURIComponent(created.job_id)}/run`, {method:'POST',headers:{'Content-Type':'application/json'},body:'{}'});
    let result = created;
    for (let attempt = 0; attempt < 60; attempt += 1) {
      result = await api(`/api/jobs/${encodeURIComponent(created.job_id)}`);
      if (!['QUEUED','RUNNING'].includes(result.status)) break;
      await new Promise(resolve => setTimeout(resolve, 200));
    }
    showToast(result.status === 'SUCCEEDED' ? (result.stdout || '项目审计通过') : (result.stderr || result.stdout || '项目审计失败'));
  } catch (error) { showToast(error.message); }
  finally { button.disabled = false; button.textContent = '运行项目审计'; }
});

async function initialize(view = 'studio') {
  const thisNavigation = ++navigationId;
  content.innerHTML = '<div class="loading"><span></span>正在连接本地工作台…</div>';
  try {
    await Promise.all([loadRuntime(), loadAccounts()]);
    if (thisNavigation === navigationId) return navigate(view, false);
  } catch (error) { if (thisNavigation === navigationId) showConnectionError(error, view); }
}
initialize();
