/* Drafts never submit production jobs or preserve approval checkboxes. */
(function (root) {
  function createDraftStore() {
    const entries = new Map();
    const key = (account, project, action) => JSON.stringify([account, project, action]);
    return {
      set(account, project, action, values) {
        entries.set(key(account, project, action), structuredClone(values));
      },
      get(account, project, action) {
        const value = entries.get(key(account, project, action));
        return value === undefined ? null : structuredClone(value);
      },
      remove(account, project, action) { entries.delete(key(account, project, action)); },
    };
  }
  function fieldValue(field, draft, saved) {
    // Approval checkboxes must always be explicitly checked for this execution.
    if (field.type === 'checkbox') return false;
    return draft?.[field.name] ?? saved?.[field.name] ?? field.default ?? '';
  }
  function projectJobs(jobs, projectId) {
    return jobs.filter(job => (job.video_id || '') === (projectId || ''));
  }
  function sameInputs(left, right) {
    const keys = new Set([...Object.keys(left || {}), ...Object.keys(right || {})]);
    return [...keys].every(key => JSON.stringify(left?.[key]) === JSON.stringify(right?.[key]));
  }
  function createPersistentDraftStore(request, {delay = 700, onChange = () => {}} = {}) {
    const entries = new Map();
    const keyFor = (account, project, action) => JSON.stringify([account, project, action]);
    const clone = value => structuredClone(value);
    const notify = (entry, reason = 'status') => onChange(clone({...entry, timer:undefined, loading:undefined, saving:undefined}), reason);
    function entryFor(account, project, action, initial = {}) {
      const key = keyFor(account, project, action);
      if (!entries.has(key)) entries.set(key, {key, account_id:account, video_id:project, action, values:clone(initial), touched:[], version:0, revision:0, loaded:false, dirty:false, status:'loading', updated_at:null, error:'', conflict:null});
      return entries.get(key);
    }
    function schedule(entry) {
      clearTimeout(entry.timer);
      if (!entry.loaded || entry.conflict || !entry.dirty || entry.saving || entry.status === 'error') return;
      entry.timer = setTimeout(() => save(entry), delay);
    }
    async function hydrate(entry) {
      if (entry.loaded || entry.loading) return entry.loading;
      entry.status = 'loading'; entry.error = ''; notify(entry);
      entry.loading = (async () => {
        try {
          const query = new URLSearchParams({account_id:entry.account_id, video_id:entry.video_id, action:entry.action});
          const record = await request(`/api/drafts?${query}`);
          const localValues = entry.values;
          const remoteValues = record.version > 0 ? (record.values || {}) : entry.values;
          entry.values = clone(remoteValues);
          entry.touched.forEach(name => { entry.values[name] = clone(localValues[name]); });
          entry.version = record.version || 0; entry.updated_at = record.updated_at;
          entry.loaded = true; entry.status = entry.dirty ? 'pending' : 'saved';
          notify(entry, 'hydrated'); schedule(entry);
        } catch (error) {
          entry.status = 'error'; entry.error = error.message; notify(entry);
        } finally { entry.loading = null; }
      })();
      return entry.loading;
    }
    async function save(entry) {
      clearTimeout(entry.timer);
      if (!entry.loaded) { await hydrate(entry); if (!entry.loaded) return; }
      if (entry.saving || entry.conflict || !entry.dirty) return entry.saving;
      const revision = entry.revision;
      const values = clone(entry.values);
      entry.status = 'saving'; entry.error = ''; notify(entry);
      entry.saving = (async () => {
        try {
          const record = await request('/api/drafts/save', {method:'POST', headers:{'Content-Type':'application/json'}, body:JSON.stringify({account_id:entry.account_id,video_id:entry.video_id,action:entry.action,values,expected_version:entry.version})});
          entry.version = record.version; entry.updated_at = record.updated_at;
          entry.dirty = entry.revision !== revision;
          entry.status = entry.dirty ? 'pending' : 'saved';
          if (!entry.dirty) entry.touched = [];
        } catch (error) {
          entry.error = error.message;
          if (error.code === 'DRAFT_CONFLICT' && error.current) {
            entry.conflict = clone(error.current); entry.status = 'conflict';
          } else entry.status = 'error';
        } finally { entry.saving = null; notify(entry); schedule(entry); }
      })();
      return entry.saving;
    }
    return {
      open(account, project, action, initial = {}) {
        const entry = entryFor(account, project, action, initial);
        hydrate(entry); return clone(entry.values);
      },
      get(account, project, action) { const entry = entries.get(keyFor(account, project, action)); return entry ? clone(entry.values) : null; },
      state(account, project, action) {
        const entry = entries.get(keyFor(account, project, action));
        return entry ? clone({...entry, timer:undefined, loading:undefined, saving:undefined}) : null;
      },
      set(account, project, action, values) {
        const entry = entryFor(account, project, action);
        if (sameInputs(entry.values, values)) return;
        const changed = new Set([...entry.touched, ...Object.keys(values).filter(name => !sameInputs({value:entry.values[name]}, {value:values[name]}))]);
        entry.touched = [...changed]; entry.values = clone(values); entry.revision += 1; entry.dirty = true;
        if (!['error','conflict','saving'].includes(entry.status)) entry.status = 'pending';
        notify(entry); if (!entry.loaded) hydrate(entry); else schedule(entry);
      },
      async retry(account, project, action) {
        const entry = entryFor(account, project, action);
        entry.error = ''; if (!entry.loaded) await hydrate(entry); else if (!entry.conflict) {entry.status = 'pending'; await save(entry);}
      },
      async resolve(account, project, action, choice) {
        const entry = entryFor(account, project, action);
        if (!entry.conflict) return;
        const remote = entry.conflict;
        entry.version = remote.version; entry.updated_at = remote.updated_at; entry.conflict = null; entry.error = '';
        if (choice === 'remote') {
          entry.values = clone(remote.values || {}); entry.dirty = false; entry.touched = []; entry.revision += 1; entry.status = 'saved'; notify(entry, 'remote');
        } else if (choice === 'local') { entry.status = 'pending'; await save(entry); }
      },
      flushAll() { return Promise.all([...entries.values()].filter(entry => entry.dirty).map(save)); },
      hasUnsaved() { return [...entries.values()].some(entry => entry.dirty || entry.saving); },
    };
  }
  const exports = {createDraftStore, createPersistentDraftStore, fieldValue, projectJobs, sameInputs};
  if (typeof module === 'object' && module.exports) module.exports = exports;
  else root.WorkbenchState = exports;
})(globalThis);
