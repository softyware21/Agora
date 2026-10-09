const $ = id => document.getElementById(id);
const token = document.querySelector('meta[name="agora-token"]').content;
let mode = 'new', parent = null, selected = null, detail = null, planPayload = null;
let state = {job: {}, runs: []}, initialized = false, polling = false, historySignature = '', detailSignature = '';
const names = {agreed: 'Agreed', disputed: 'Disputed', insufficient_information: 'Needs information', unverified: 'Unverified'};

async function api(path, payload) {
  const options = {headers: {'X-Agora-Token': token}};
  if (payload !== undefined) Object.assign(options, {method: 'POST', headers: {...options.headers, 'Content-Type': 'application/json'}, body: JSON.stringify(payload)});
  const response = await fetch(path, options);
  const data = await response.json();
  if (!response.ok) throw new Error(data.error || 'The request could not be completed.');
  return data;
}
function node(tag, text, className) {
  const item = document.createElement(tag);
  if (text !== undefined) item.textContent = text;
  if (className) item.className = className;
  return item;
}
function error(message) { $('error').textContent = message; $('error').hidden = !message; }
async function act(work) { error(''); try { await work(); } catch (e) { error(e.message); } }
function invalidate() { planPayload = null; $('plan').hidden = true; }
function selection() {
  return {codex: $('codex-model').value.trim() || null, claude: $('claude-model').value.trim() || null,
    summary_provider: $('summary-provider').value, summary_model: $('summary-model').value.trim() || null};
}
function payload() {
  return {mode, parent, question: $('question').value, rules: $('rules').value, rounds: Number($('rounds').value),
    source_urls: $('sources').value.split('\n').map(s => s.trim()).filter(Boolean), note: $('note').value,
    model_selection: selection(), timeout: Number($('timeout').value), deadline: Number($('deadline').value)};
}
function edit(nextMode = 'new', record = null, id = null) {
  mode = nextMode; parent = id; selected = null; detailSignature = ''; invalidate(); error('');
  $('editor').hidden = false; $('discussion').hidden = true;
  $('editor-title').textContent = mode === 'new' ? 'What deserves a second perspective?' : mode === 'resume' ? 'Pick up where you left off.' : 'What should we reconsider?';
  $('editor-intro').textContent = mode === 'new' ? 'Give two models something to work through. See where they agree, where they differ, and what still needs evidence.' : mode === 'resume' ? 'Completed answers and model settings stay in place. Only unfinished calls will run.' : 'Add new information or change the conditions. Earlier answers stay in the original record.';
  $('question').value = record?.question || ''; $('question').readOnly = mode !== 'new';
  $('rules').value = record?.rules ?? state.default_rules ?? '';
  $('note').value = ''; $('note-wrap').hidden = mode !== 'continue'; $('sources').value = '';
  $('rounds').value = mode === 'resume' ? String(record.rounds) : '1';
  $('rounds-label').textContent = mode === 'continue' ? 'Additional review rounds' : 'Review rounds';
  const models = record?.model_selection || {};
  $('codex-model').value = models.codex || ''; $('claude-model').value = models.claude || '';
  $('summary-provider').value = models.summary_provider || 'codex'; $('summary-model').value = models.summary_model || '';
  $('timeout').value = '180'; $('deadline').value = '600';
  for (const control of $('setup').querySelectorAll('input,textarea,select')) control.disabled = mode === 'resume' && !['timeout','deadline'].includes(control.id);
  $('start').textContent = mode === 'new' ? 'Start discussion →' : mode === 'resume' ? 'Resume discussion →' : 'Start follow-up →';
  historySignature = ''; renderHistory(); window.scrollTo({top: 0});
}
function renderHistory() {
  const signature = JSON.stringify([state.runs, selected]);
  if (signature === historySignature) return;
  historySignature = signature; $('history').replaceChildren(); $('history-count').textContent = state.runs.length;
  if (!state.runs.length) $('history').append(node('p', 'Your first discussion will appear here.', 'hint'));
  for (const run of state.runs) {
    const button = node('button', undefined, run.id === selected ? 'selected' : '');
    button.append(node('span', run.question, 'history-title'), node('small', `${run.status === 'running' ? 'Unfinished' : run.status} · ${run.turns} answers`));
    button.onclick = () => act(() => openRun(run.id)); $('history').append(button);
  }
}
async function openRun(id) {
  selected = id; detail = null; detailSignature = ''; $('editor').hidden = true; $('discussion').hidden = false;
  $('discussion-title').textContent = 'Loading discussion…'; $('issues').replaceChildren(); $('turns').replaceChildren();
  $('resume').hidden = $('continue').hidden = $('download').hidden = $('back-setup').hidden = $('stop').hidden = true;
  $('summary-section').hidden = $('run-error').hidden = true; $('outcome-counts').replaceChildren();
  $('progress').value = 0; $('progress-count').textContent = ''; $('run-models').textContent = ''; $('status').textContent = '';
  renderHistory(); await refreshDetail(id); window.scrollTo({top: 0});
}
function renderDetail(data) {
  const open = new Set([...$('discussion').querySelectorAll('details[open]')].map(el => el.id));
  const record = data.record, job = state.job, active = job.active && job.run_id === data.id;
  $('discussion-title').textContent = record.question;
  $('status').textContent = active ? (job.stopping ? 'Stopping' : 'In progress') : record.status === 'running' ? 'Unfinished' : record.status;
  const total = 3 + 2 * record.rounds, count = record.turns.length;
  $('progress').max = total; $('progress').value = count; $('progress-count').textContent = `${count} / ${total} answers saved`;
  $('progress-label').textContent = active ? (job.stopping ? 'Stopping after the current answer…' : job.phase) : record.status === 'completed' ? 'Discussion complete' : 'Ready to resume';
  const model = record.model_selection || {};
  $('run-models').textContent = `GPT: ${model.codex || 'CLI default'} · Claude: ${model.claude || 'CLI default'} · Summary: ${model.summary_provider || 'codex'} / ${model.summary_model || model[model.summary_provider || 'codex'] || 'CLI default'}`;
  const failure = (job.run_id === data.id && job.error) || record.error;
  $('run-error').textContent = failure || ''; $('run-error').hidden = !failure;
  $('resume').hidden = active || !data.can_resume; $('continue').hidden = active || !data.can_continue;
  $('resume').disabled = $('continue').disabled = !!job.active;
  $('stop').hidden = !active; $('stop').disabled = !!job.stopping; $('download').hidden = false;
  const board = record.issue_outcomes || {issues: []};
  $('outcome-counts').replaceChildren();
  for (const [status, label] of Object.entries(names)) {
    const card = node('div', undefined, 'count'); card.append(node('strong', board.issues.filter(i => i.status === status).length), node('span', label)); $('outcome-counts').append(card);
  }
  $('issues').replaceChildren();
  if (!board.issues.length) $('issues').append(node('p', record.summary ? 'No assessable issue outcomes were reported. This does not imply agreement.' : 'Issue outcomes will appear after the summary. Saved answers are available below.', 'empty'));
  for (const issue of board.issues) {
    const card = node('article', undefined, `issue ${issue.status}`), title = node('div', undefined, 'title-row');
    title.append(node('h3', issue.topic || 'Unassessed issue'), node('span', names[issue.status] || issue.status, 'badge'));
    card.append(title, node('p', issue.reason), node('p', `Next step: ${issue.next_step}`));
    const quotes = node('details'); quotes.id = `issue-${issue.id}`; quotes.open = open.has(quotes.id);
    quotes.append(node('summary', `Cited positions · ${issue.citation_status.replaceAll('_', ' ')}`));
    for (const position of issue.positions) quotes.append(node('p', `${position.provider || 'Unknown'}: ${position.position || 'Unavailable'}`, 'tiny'), node('blockquote', position.quote || 'No valid quote.'));
    card.append(quotes); $('issues').append(card);
  }
  $('summary-section').hidden = !record.summary; $('summary-text').textContent = record.summary || '';
  $('turns').replaceChildren();
  record.turns.forEach((turn, i) => {
    const item = node('details', undefined, 'answer'); item.id = `turn-${i}`; item.open = open.has(item.id);
    const meta = turn.metadata || {};
    item.append(node('summary', `${String(i + 1).padStart(2, '0')} · ${turn.provider} · ${turn.phase}${turn.round ? ` / round ${turn.round}` : ''}`),
      node('p', `Requested: ${meta.requested_model || 'default / not recorded'} · Reported: ${(meta.models || []).join(', ') || 'unavailable'}`, 'hint'), node('pre', turn.text));
    $('turns').append(item);
  });
}
async function refreshDetail(id) {
  try {
    const data = await api(`/api/runs/${encodeURIComponent(id)}`);
    if (selected !== id) return;
    detail = data;
    const signature = JSON.stringify([data, state.job]);
    if (signature !== detailSignature) { detailSignature = signature; renderDetail(data); }
  } catch (e) {
    if (selected !== id) return;
    if (state.job.run_id === id) {
      $('discussion-title').textContent = state.job.active ? 'Preparing your discussion…' : 'Discussion could not start';
      $('progress-label').textContent = state.job.phase; $('run-error').textContent = state.job.error || e.message;
      $('run-error').hidden = !!state.job.active; $('stop').hidden = !state.job.active;
      $('back-setup').hidden = !!state.job.active; $('stop').disabled = !!state.job.stopping;
    } else {
      $('discussion-title').textContent = 'Discussion unavailable'; $('progress-label').textContent = 'Cannot read this record';
      $('run-error').textContent = e.message; $('run-error').hidden = false;
    }
  }
}
async function poll() {
  if (polling) return;
  polling = true;
  try {
    state = await api('/api/state'); $('connection').hidden = true;
    if (!initialized) { $('rules').value = state.default_rules; initialized = true; renderHistory(); }
    renderHistory();
    const job = state.job;
    $('active-job').hidden = !job.active || selected === job.run_id;
    $('job-label').textContent = job.stopping ? 'Stopping after the current answer…' : `Discussion in progress · ${job.phase}`;
    $('start').disabled = !!job.active;
    if (selected) await refreshDetail(selected);
  } catch (e) { $('connection').hidden = false; }
  finally { polling = false; }
}
$('new').onclick = () => edit();
$('back-setup').onclick = () => { selected = null; $('editor').hidden = false; $('discussion').hidden = true; renderHistory(); };
$('view-active').onclick = () => act(() => openRun(state.job.run_id));
$('setup').addEventListener('input', invalidate);
$('summary-provider').addEventListener('change', () => { $('summary-model').value = ''; invalidate(); });
$('setup').onsubmit = event => { event.preventDefault(); act(async () => {
  const requested = payload(), planned = await api('/api/plan', requested);
  if (JSON.stringify(requested) !== JSON.stringify(payload())) return;
  planPayload = requested; $('plan-count').textContent = `${planned.calls} calls · GPT ${planned.by_provider.codex} / Claude ${planned.by_provider.claude}`;
  $('plan-models').textContent = planned.models; $('plan').hidden = false; $('start').disabled = !!state.job.active;
  $('plan').scrollIntoView({behavior: 'smooth', block: 'nearest'});
}); };
$('start').onclick = () => act(async () => {
  if (!planPayload) return;
  $('start').disabled = true;
  const result = await api('/api/start', planPayload); invalidate();
  await poll(); await openRun(result.run_id);
});
$('resume').onclick = () => edit('resume', detail.record, detail.id);
$('continue').onclick = () => edit('continue', detail.record, detail.id);
$('stop').onclick = () => act(async () => { await api('/api/stop', {}); await poll(); });
$('download').onclick = () => act(async () => {
  const response = await fetch(`/api/download/${encodeURIComponent(selected)}/report.md`, {headers: {'X-Agora-Token': token}});
  if (!response.ok) throw new Error('The report could not be downloaded.');
  const url = URL.createObjectURL(await response.blob()), link = node('a');
  link.href = url; link.download = `${selected}-report.md`; link.click(); setTimeout(() => URL.revokeObjectURL(url), 1000);
});
poll(); setInterval(poll, 1500);
