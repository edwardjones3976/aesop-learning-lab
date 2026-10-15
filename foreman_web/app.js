const ACTIVITY_TYPES = new Set(['choice', 'trace', 'explanation', 'code_design']);
const EVIDENCE_KINDS = new Set(['recognition', 'recall', 'explanation', 'application', 'transfer']);
const HINT_LEVELS = new Set(['nudge', 'targeted', 'worked_solution']);
const PATH_ACTIONS = new Set(['lesson', 'practice', 'resume', 'delayed_check']);

function contractError(path, detail) {
  return new Error(`${path}: ${detail}`);
}

function requireRecord(value, path) {
  if (!value || typeof value !== 'object' || Array.isArray(value)) {
    throw contractError(path, 'expected an object.');
  }
  return value;
}

function requireString(value, path) {
  if (typeof value !== 'string' || !value.trim()) throw contractError(path, 'expected a non-empty string.');
  return value;
}

function requireNumber(value, path) {
  if (typeof value !== 'number' || Number.isNaN(value)) throw contractError(path, 'expected a number.');
  return value;
}

function requireArray(value, path) {
  if (!Array.isArray(value)) throw contractError(path, 'expected an array.');
  return value;
}

function requireBoolean(value, path) {
  if (typeof value !== 'boolean') throw contractError(path, 'expected true or false.');
  return value;
}

export function normalizeEvidence(evidence, path = 'evidence') {
  const raw = evidence == null ? {} : evidence;
  requireRecord(raw, path);
  const byKind = {};
  if (raw.byKind !== undefined) {
    const source = requireRecord(raw.byKind, `${path}.byKind`);
    for (const [kind, row] of Object.entries(source)) {
      const counts = requireRecord(row, `${path}.byKind.${kind}`);
      byKind[kind] = {
        unassistedCorrect: requireNumber(counts.unassistedCorrect ?? 0, `${path}.byKind.${kind}.unassistedCorrect`),
        assistedCorrect: requireNumber(counts.assistedCorrect ?? 0, `${path}.byKind.${kind}.assistedCorrect`),
        incorrect: requireNumber(counts.incorrect ?? 0, `${path}.byKind.${kind}.incorrect`),
        ungraded: requireNumber(counts.ungraded ?? 0, `${path}.byKind.${kind}.ungraded`),
      };
    }
  }
  const delayedOutcomeByDay = {};
  if (raw.delayedOutcomeByDay != null) {
    const source = requireRecord(raw.delayedOutcomeByDay, `${path}.delayedOutcomeByDay`);
    for (const [day, status] of Object.entries(source)) {
      delayedOutcomeByDay[day] = requireString(status, `${path}.delayedOutcomeByDay.${day}`);
    }
  }
  const delayedChecks = raw.delayedChecks == null ? [] : requireArray(raw.delayedChecks, `${path}.delayedChecks`);
  delayedChecks.forEach((check, index) => {
    const row = requireRecord(check, `${path}.delayedChecks[${index}]`);
    requireNumber(row.checkDelayDays, `${path}.delayedChecks[${index}].checkDelayDays`);
    requireString(row.evidenceKind, `${path}.delayedChecks[${index}].evidenceKind`);
    requireString(row.scoreStatus, `${path}.delayedChecks[${index}].scoreStatus`);
    requireString(row.occurredAt, `${path}.delayedChecks[${index}].occurredAt`);
  });
  return {
    byKind,
    delayedChecks,
    delayedOutcomeByDay,
    confidenceOutcomePairs: typeof raw.confidenceOutcomePairs === 'number' && !Number.isNaN(raw.confidenceOutcomePairs)
      ? raw.confidenceOutcomePairs : 0,
  };
}

function validateSignals(signals, path) {
  const raw = requireRecord(signals, path);
  return {
    attempts: requireNumber(raw.attempts ?? 0, `${path}.attempts`),
    unassistedCorrect: requireNumber(raw.unassistedCorrect ?? 0, `${path}.unassistedCorrect`),
    hintAssisted: requireNumber(raw.hintAssisted ?? 0, `${path}.hintAssisted`),
    needsReview: requireNumber(raw.needsReview ?? 0, `${path}.needsReview`),
    recentOutcome: raw.recentOutcome == null ? null : requireString(raw.recentOutcome, `${path}.recentOutcome`),
    evidence: normalizeEvidence(raw.evidence, `${path}.evidence`),
  };
}

export function validateOverview(data) {
  const overview = requireRecord(data, 'overview');
  requireString(overview.packVersion, 'overview.packVersion');
  const concepts = requireArray(overview.concepts, 'overview.concepts');
  if (!concepts.length) throw contractError('overview.concepts', 'expected at least one concept.');
  const normalizedConcepts = concepts.map((concept, index) => {
    const path = `overview.concepts[${index}]`;
    const row = requireRecord(concept, path);
    return {
      id: requireString(row.id, `${path}.id`),
      title: requireString(row.title, `${path}.title`),
      lessonComplete: requireBoolean(row.lessonComplete ?? false, `${path}.lessonComplete`),
      signals: validateSignals(row.signals, `${path}.signals`),
    };
  });
  const pathRecommendation = requireRecord(overview.pathRecommendation, 'overview.pathRecommendation');
  const action = requireString(pathRecommendation.action, 'overview.pathRecommendation.action');
  if (!PATH_ACTIONS.has(action)) {
    throw contractError('overview.pathRecommendation.action', 'action is not recognized.');
  }
  const conceptId = requireString(pathRecommendation.conceptId, 'overview.pathRecommendation.conceptId');
  if (!normalizedConcepts.some(c => c.id === conceptId)) {
    throw contractError('overview.pathRecommendation.conceptId', 'does not match any concept.');
  }
  return {
    ...overview,
    concepts: normalizedConcepts,
    pathRecommendation: {
      conceptId,
      action,
      reason: requireString(pathRecommendation.reason, 'overview.pathRecommendation.reason'),
    },
  };
}

export function validateLesson(data) {
  const lesson = requireRecord(data, 'lesson');
  const sources = requireArray(lesson.sources ?? [], 'lesson.sources');
  sources.forEach((source, index) => {
    const row = requireRecord(source, `lesson.sources[${index}]`);
    requireString(row.title, `lesson.sources[${index}].title`);
    requireString(row.url, `lesson.sources[${index}].url`);
  });
  return {
    conceptId: requireString(lesson.conceptId, 'lesson.conceptId'),
    title: requireString(lesson.title, 'lesson.title'),
    body: requireString(lesson.body, 'lesson.body'),
    completed: requireBoolean(lesson.completed ?? false, 'lesson.completed'),
    sources,
  };
}

function validateActivity(activity, path) {
  const row = requireRecord(activity, path);
  const type = requireString(row.type, `${path}.type`);
  if (!ACTIVITY_TYPES.has(type)) throw contractError(`${path}.type`, 'activity type is not recognized.');
  const evidenceKind = requireString(row.evidenceKind, `${path}.evidenceKind`);
  if (!EVIDENCE_KINDS.has(evidenceKind)) throw contractError(`${path}.evidenceKind`, 'evidence kind is not recognized.');
  requireString(row.id, `${path}.id`);
  requireString(row.prompt, `${path}.prompt`);
  if (row.body != null && typeof row.body !== 'string') throw contractError(`${path}.body`, 'expected text or null.');
  const choices = requireArray(row.choices ?? [], `${path}.choices`);
  choices.forEach((choice, index) => {
    if (typeof choice !== 'string' || !choice) throw contractError(`${path}.choices[${index}]`, 'expected a non-empty string.');
  });
  if (type === 'choice' && !choices.length) throw contractError(`${path}.choices`, 'choice activity requires options.');
  const hints = requireArray(row.hints ?? [], `${path}.hints`);
  const seen = new Set();
  hints.forEach((hint, index) => {
    const h = requireRecord(hint, `${path}.hints[${index}]`);
    const level = requireString(h.level, `${path}.hints[${index}].level`);
    if (!HINT_LEVELS.has(level)) throw contractError(`${path}.hints[${index}].level`, 'hint level is not recognized.');
    if (seen.has(level)) throw contractError(`${path}.hints[${index}].level`, 'hint level is repeated.');
    seen.add(level);
    if (h.text != null && typeof h.text !== 'string') {
      throw contractError(`${path}.hints[${index}].text`, 'expected text when present.');
    }
  });
  return { ...row, type, evidenceKind, choices, hints, heldOut: Boolean(row.heldOut) };
}

function validateDraft(draft, path) {
  const row = requireRecord(draft, path);
  const hintLevels = row.hintLevels == null ? [] : requireArray(row.hintLevels, `${path}.hintLevels`);
  hintLevels.forEach((level, index) => {
    const value = requireString(level, `${path}.hintLevels[${index}]`);
    if (!HINT_LEVELS.has(value)) throw contractError(`${path}.hintLevels[${index}]`, 'hint level is not recognized.');
  });
  return {
    id: requireString(row.id, `${path}.id`),
    firstAnswer: typeof row.firstAnswer === 'string' ? row.firstAnswer : requireString(row.firstAnswer, `${path}.firstAnswer`),
    hintLevels,
  };
}

export function validateSession(data) {
  const session = requireRecord(data, 'session');
  if (session.lessonRequired) {
    requireBoolean(session.lessonRequired, 'session.lessonRequired');
    if (session.activity != null) throw contractError('session.activity', 'must be null when lesson is required.');
    return { lessonRequired: true, activity: null, draft: null, recommendation: null, reason: session.reason ?? null, nextCheckAt: session.nextCheckAt ?? null };
  }
  const activity = session.activity == null ? null : validateActivity(session.activity, 'session.activity');
  const draft = session.draft == null ? null : validateDraft(session.draft, 'session.draft');
  if (activity && draft && session.draft) {
    // draft is valid when activity exists
  }
  return {
    lessonRequired: false,
    activity,
    draft,
    recommendation: session.recommendation == null ? null : requireRecord(session.recommendation, 'session.recommendation'),
    reason: typeof session.reason === 'string' ? session.reason : null,
    nextCheckAt: session.nextCheckAt ?? null,
  };
}

export function validateAttemptResult(data) {
  const result = requireRecord(data, 'attempt');
  requireString(result.attemptId, 'attempt.attemptId');
  requireString(result.scoreStatus, 'attempt.scoreStatus');
  requireString(result.nextReason, 'attempt.nextReason');
  requireBoolean(result.assisted ?? false, 'attempt.assisted');
  if (result.rubric != null) {
    const rubric = requireRecord(result.rubric, 'attempt.rubric');
    requireString(rubric.id, 'attempt.rubric.id');
    requireString(rubric.version, 'attempt.rubric.version');
    const criteria = requireArray(rubric.criteria, 'attempt.rubric.criteria');
    criteria.forEach((criterion, index) => {
      const row = requireRecord(criterion, `attempt.rubric.criteria[${index}]`);
      requireString(row.id, `attempt.rubric.criteria[${index}].id`);
      requireString(row.description, `attempt.rubric.criteria[${index}].description`);
    });
  }
  return result;
}

export function evidenceMarkup(evidence) {
  const normalized = normalizeEvidence(evidence, 'signals.evidence');
  const esc = value => String(value ?? '').replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
  const rows = Object.entries(normalized.byKind).map(([kind, count]) => `<tr><th scope="row">${esc(kind)}</th><td>${count.unassistedCorrect}</td><td>${count.assistedCorrect}</td><td>${count.incorrect}</td><td>${count.ungraded}</td></tr>`).join('');
  const delayed = normalized.delayedChecks.length ? normalized.delayedChecks.map(check => `<li>Day ${esc(check.checkDelayDays)} · ${esc(check.evidenceKind)} · ${esc(check.scoreStatus)} · ${check.assisted ? 'assisted' : 'independent'} · family familiarity ${esc(String(check.familiarityStatus ?? 'not_verified').replace('_', ' '))} · ${esc(new Date(check.occurredAt).toLocaleString())}</li>`).join('') : '<li>Insufficient evidence: no delayed held-out answer yet.</li>';
  const intervalStatus = Object.entries(normalized.delayedOutcomeByDay).map(([day, status]) => `<li>Day ${esc(day)}: ${esc(status.replace('_', ' '))}</li>`).join('');
  return `<details class="evidence-panel"><summary>Inspect learning evidence</summary><p class="muted">Observed answers by kind. Candidate-key matches are development feedback, not mastery.</p><div class="table-scroll"><table><thead><tr><th scope="col">Kind</th><th scope="col">Independent matches</th><th scope="col">Assisted matches</th><th scope="col">Incorrect</th><th scope="col">Ungraded</th></tr></thead><tbody>${rows}</tbody></table></div><p><strong>Delayed check status</strong></p><ul>${intervalStatus || '<li>Insufficient evidence: no delayed held-out answer yet.</li>'}</ul><p><strong>Recorded answers</strong></p><ul>${delayed}</ul><p class="muted">Independent scored answers with confidence recorded: ${normalized.confidenceOutcomePairs}. No calibrated estimate is available.</p></details>`;
}

if (typeof globalThis.document !== 'undefined') {
const content = document.querySelector('#content');
const conceptsEl = document.querySelector('#concepts');
const state = { overview: null, conceptId: null, lesson: null, session: null, answer: '', result: null, review: null, mode: 'recommended', started: Date.now() };
const preferenceKey = 'aesop.foreman.preferences.v1';
let preferences = { minutes: 20, textSize: 'regular', theme: 'system', focus: false };
try {
  const saved = JSON.parse(localStorage.getItem(preferenceKey) || '{}');
  if ([5,10,20,30,45].includes(saved.minutes)) preferences.minutes = saved.minutes;
  if (['regular','large'].includes(saved.textSize)) preferences.textSize = saved.textSize;
  if (['system','light','dark'].includes(saved.theme)) preferences.theme = saved.theme;
  if (typeof saved.focus === 'boolean') preferences.focus = saved.focus;
} catch (_) { /* Private browsing may disable storage. */ }
const systemTheme = matchMedia('(prefers-color-scheme: dark)');
function applyPreferences() {
  document.querySelector('#minutes').value = String(preferences.minutes);
  document.querySelector('#text-size').value = preferences.textSize;
  document.querySelector('#theme').value = preferences.theme;
  document.querySelector('#focus').checked = preferences.focus;
  document.documentElement.dataset.theme = preferences.theme === 'system'
    ? (systemTheme.matches ? 'dark' : 'light') : preferences.theme;
  document.body.classList.toggle('large-reading', preferences.textSize === 'large');
  document.body.classList.toggle('quiet', preferences.focus);
  try { localStorage.setItem(preferenceKey, JSON.stringify(preferences)); } catch (_) { /* Settings remain usable for this tab. */ }
}
document.querySelector('#minutes').onchange = async event => { preferences.minutes = Number(event.target.value); applyPreferences(); await refresh().catch(showError); };
document.querySelector('#text-size').onchange = event => { preferences.textSize = event.target.value; applyPreferences(); };
document.querySelector('#theme').onchange = event => { preferences.theme = event.target.value; applyPreferences(); };
document.querySelector('#focus').onchange = event => { preferences.focus = event.target.checked; applyPreferences(); };
systemTheme.addEventListener('change', () => { if (preferences.theme === 'system') applyPreferences(); });
applyPreferences();
const esc = value => String(value ?? '').replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));

async function api(path, body) {
  const options = body === undefined ? {} : { method:'POST', headers:{'Content-Type':'application/json'}, body:JSON.stringify(body) };
  const response = await fetch(path, options);
  let data;
  try {
    data = await response.json();
  } catch (_) {
    throw new Error(`Request failed: response was not JSON (${response.status}).`);
  }
  if (!response.ok) throw new Error(data.message || data.error || `Request failed (${response.status})`);
  return data;
}
function showError(error) {
  document.querySelector('.error')?.remove();
  const el = document.createElement('div'); el.className = 'error'; el.role = 'alert'; el.textContent = error.message || String(error);
  content.prepend(el);
}
function concepts() {
  const path = state.overview?.pathRecommendation;
  conceptsEl.innerHTML = state.overview.concepts.map((c, i) => `<button class="concept ${c.id === state.conceptId ? 'active' : ''}" data-concept="${esc(c.id)}"><span class="num">${String(i+1).padStart(2,'0')}</span><span><span class="title">${esc(c.title)}</span><small>${c.lessonComplete ? 'Lesson read' : 'Lesson to read'} · ${c.signals.attempts} attempt${c.signals.attempts === 1 ? '' : 's'}${path && c.id === path.conceptId ? ' · Suggested' : ''}</small></span></button>`).join('');
  conceptsEl.querySelectorAll('[data-concept]').forEach(button => button.onclick = () => select(button.dataset.concept));
}
async function select(cid) {
  try {
    state.conceptId = cid; state.answer = ''; state.result = null; state.review = null; state.mode = 'recommended'; state.started = Date.now();
    await refresh();
  } catch (error) { showError(error); }
}
async function refresh() {
  const cid = encodeURIComponent(state.conceptId);
  const [overview, lesson, session] = await Promise.all([
    api('/api/v2/overview'), api(`/api/v2/lesson?conceptId=${cid}`),
    api(`/api/v2/session?conceptId=${cid}&mode=${state.mode}&availableMinutes=${preferences.minutes}`)
  ]);
  state.overview = validateOverview(overview);
  state.lesson = validateLesson(lesson);
  state.session = validateSession(session);
  document.querySelector('.notice').textContent = `Draft content · ${state.overview.packVersion} · Candidate answer keys; independent review remains required. Results are for development, not mastery claims.`;
  if (state.session.draft) state.answer = state.session.draft.firstAnswer;
  concepts(); render();
}
function render() {
  try {
    renderWorkspace();
  } catch (error) {
    showError(error);
  }
}
function renderWorkspace() {
  const index = state.overview.concepts.findIndex(c => c.id === state.conceptId) + 1;
  if (index < 1) throw contractError('overview.concepts', 'selected concept was not found.');
  const current = state.overview.concepts[index-1], signals = current.signals;
  const suggested = state.overview.pathRecommendation;
  const intro = `<div class="section-kicker">CONCEPT ${String(index).padStart(2,'0')} / ${String(state.overview.concepts.length).padStart(2,'0')}</div><h2>${esc(current.title)}</h2><p class="lede">The goal is lasting understanding. The setting is yours to adjust; retrieval and delayed checks remain part of the learning path.</p><div class="path-note"><strong>Suggested next: ${esc(suggested.action.replace('_', ' '))} · ${esc(state.overview.concepts.find(c => c.id === suggested.conceptId)?.title)}</strong><p>${esc(suggested.reason)}</p>${suggested.conceptId !== state.conceptId ? '<button class="button secondary" id="follow-path">Go to suggested concept</button>' : '<span class="muted">You can choose any concept from Your Path.</span>'}</div><div class="signals"><div class="signal"><strong>${signals.attempts}</strong>attempts</div><div class="signal"><strong>${signals.unassistedCorrect}</strong>unassisted candidate matches</div><div class="signal"><strong>${signals.hintAssisted}</strong>hint-assisted attempts</div></div>${evidenceMarkup(signals.evidence)}<div class="divider"></div>`;
  content.onclick = event => { if (event.target?.id === 'follow-path') select(suggested.conceptId); };
  if (!state.lesson.completed) {
    content.innerHTML = intro + `<span class="pill">Short lesson</span><h2>${esc(state.lesson.title)}</h2><div class="lesson-body">${esc(state.lesson.body)}</div><p class="sources">Sources: ${state.lesson.sources.map(s=>`<a href="${esc(s.url)}" target="_blank" rel="noopener noreferrer">${esc(s.title)}</a>`).join('')}</p><div class="button-row"><button class="button" id="complete">I've read this lesson →</button></div>`;
    document.querySelector('#complete').onclick = async () => { try { await api('/api/v2/lesson-completions',{conceptId:state.conceptId}); await refresh(); } catch(e){showError(e)} };
    return;
  }
  if (state.result) {
    const r = validateAttemptResult(state.result);
    const status = r.scoreStatus === 'ungraded' ? 'Saved for self review' : r.scoreStatus === 'correct' ? 'Candidate key match' : 'Try another approach';
    content.innerHTML = intro + `<div class="feedback"><h3>${status}</h3><p>${esc(r.nextReason)}</p><p class="muted">${r.assisted ? 'Hint assisted · ' : ''}Development preview · No mastery claim</p></div>` +
      (r.rubric && !state.review ? `<div class="activity-card"><span class="label">SELF REVIEW · ORIGINAL ANSWER</span><pre class="code">${esc(state.answer)}</pre><p class="muted">For each criterion, quote the part of your first answer that supports a shown or partial rating.</p>${r.rubric.criteria.map(c=>`<div class="review-row" data-criterion="${esc(c.id)}"><p><strong>${esc(c.description)}</strong></p><select class="answer rating"><option value="unsure">Unsure</option><option value="shown">Shown</option><option value="partial">Partial</option><option value="not_shown">Not shown</option></select><input class="answer evidence" placeholder="Exact quote from your answer, if shown or partial" aria-label="Evidence for ${esc(c.description)}"></div>`).join('')}<div class="button-row"><button class="button" id="review">Save self review →</button></div></div>` : '') +
      (state.review ? `<div class="activity-card"><span class="label">COMPARE AND REVISE</span><p>${esc(state.review.nextStep.replace('_',' '))}</p><pre class="code">${esc(state.review.comparison.annotatedExample)}</pre><p class="muted">Common mistakes: ${esc((state.review.comparison.commonMistakes ?? []).join(' · '))}</p><label class="muted" for="revision">A revised answer, if you want to try again</label><textarea id="revision" class="answer long"></textarea><div class="button-row"><button class="button secondary" id="save-revision">Save revision</button></div></div>` : '') +
      `<div class="button-row"><button class="button" id="next">Continue →</button><button class="button secondary" id="more">More practice</button></div>`;
    if (r.rubric && !state.review) document.querySelector('#review').onclick = async () => {
      try {
        const judgments = [...document.querySelectorAll('.review-row')].map(row => ({criterionId:row.dataset.criterion,rating:row.querySelector('.rating').value,evidence:row.querySelector('.evidence').value}));
        state.review = await api('/api/v2/self-reviews',{conceptId:state.conceptId,attemptId:r.attemptId,rubricId:r.rubric.id,rubricVersion:r.rubric.version,judgments,confidence:null});
        render();
      } catch(error){showError(error)}
    };
    if (state.review) document.querySelector('#save-revision').onclick = async () => {
      try { await api('/api/v2/revisions',{conceptId:state.conceptId,reviewId:state.review.reviewId,answer:document.querySelector('#revision').value}); document.querySelector('#save-revision').textContent='Revision saved'; document.querySelector('#save-revision').disabled=true; } catch(error){showError(error)}
    };
    document.querySelector('#next').onclick = async () => { state.result = null; state.review = null; state.answer = ''; await refresh().catch(showError); };
    document.querySelector('#more').onclick = async () => { state.result = null; state.review = null; state.answer = ''; state.mode = 'practice'; await refresh().catch(showError); };
    return;
  }
  const s = state.session, a = s.activity;
  if (!a) {
    content.innerHTML = intro + `<div class="empty"><h3>You're caught up for now.</h3><p>${esc(s.reason || 'The next check will be offered later.')}</p>${s.nextCheckAt ? `<p>Next check: ${esc(new Date(s.nextCheckAt).toLocaleString())}</p>` : ''}</div><div class="button-row"><button class="button secondary" id="more">More practice</button></div>`;
    document.querySelector('#more').onclick = async () => { state.mode = 'practice'; await refresh().catch(showError); };
    return;
  }
  const saved = Boolean(s.draft);
  const previous = signals.recentOutcome === 'incorrect' ? 'Your previous scored answer missed its candidate key. The policy offers continued practice.' : signals.recentOutcome === 'ungraded' ? 'Your previous open answer remains ungraded; self review supplies the comparison.' : signals.recentOutcome === 'correct' ? 'Your previous answer matched a candidate key. A delayed check still requires time and unassisted evidence.' : 'Start with retrieval after reading the lesson.';
  const reason = saved ? 'Resume the first answer you already saved.' : s.recommendation?.reason || 'Continue with an available activity.';
  content.innerHTML = intro + `<span class="pill">${a.heldOut ? 'Delayed check' : 'Practice activity'}</span><div class="why"><strong>Why this activity?</strong>${esc(reason)} ${esc(previous)}${s.nextCheckAt && !a.heldOut ? `<p>Independent check time, if eligibility remains: ${esc(new Date(s.nextCheckAt).toLocaleString())}</p>` : ''}</div><div class="activity-card"><span class="label">${esc(a.type.replace('_',' '))} · ${esc(a.evidenceKind)}</span><h3>${esc(a.prompt)}</h3>${a.body ? `<pre class="code">${esc(a.body)}</pre>` : ''}<div id="answer-area"></div><div class="button-row"><button id="save" class="button" ${saved?'disabled':''}>${saved?'First answer saved':'Save first answer →'}</button></div><div id="after-save"></div></div>`;
  drawAnswer(a, saved);
  document.querySelector('#save').onclick = async () => {
    try {
      if (!state.answer.trim()) throw new Error('Enter an answer first.');
      await api('/api/v2/first-answers', { conceptId:state.conceptId, activityId:a.id, draftId:crypto.randomUUID(), answer:state.answer, mode:state.mode, availableMinutes:preferences.minutes });
      await refresh();
    } catch(error){showError(error)}
  };
  if (saved) drawAfterSave(a, s.draft);
}
function drawAnswer(a, saved) {
  const area = document.querySelector('#answer-area');
  if (a.type === 'choice') {
    area.innerHTML = a.choices.map((choice,i)=>`<button class="choice ${state.answer===choice?'selected':''}" data-choice="${i}" ${saved?'disabled':''}><span></span>${esc(choice)}</button>`).join('');
    area.querySelectorAll('[data-choice]').forEach(button=>button.onclick=()=>{ state.answer=a.choices[Number(button.dataset.choice)]; drawAnswer(a,false); });
  } else if (a.type === 'trace') {
    area.innerHTML = `<label class="muted" for="answer-input">YOUR ANSWER</label><input id="answer-input" class="answer" value="${esc(state.answer)}" ${saved?'readonly':''} autocomplete="off">`;
    area.querySelector('input').oninput = event => { state.answer=event.target.value; };
  } else {
    area.innerHTML = `<label class="muted" for="answer-input">YOUR EXPLANATION OR CODE</label><textarea id="answer-input" class="answer long" ${saved?'readonly':''}>${esc(state.answer)}</textarea>`;
    area.querySelector('textarea').oninput = event => { state.answer=event.target.value; };
  }
}
function drawAfterSave(a, draft) {
  const area = document.querySelector('#after-save');
  const viewed = new Set(draft.hintLevels);
  area.innerHTML = `<div class="hint-panel"><h4>A little help, if you need it</h4><p>Hints open in order. The answer you saved stays the same.</p>${a.hints.filter(h=>viewed.has(h.level)).map(h=>`<div class="hint"><strong>${esc(h.level.replace('_',' '))}</strong><br>${esc(h.text)}</div>`).join('')}<div class="button-row">${viewed.size<a.hints.length?'<button id="hint" class="button secondary">Open next hint</button>':''}<button id="submit" class="button">Check saved answer →</button></div></div>`;
  const hint = document.querySelector('#hint');
  if (hint) hint.onclick = async () => { try { await api('/api/v2/hints',{draftId:draft.id}); await refresh(); } catch(error){showError(error)} };
  document.querySelector('#submit').onclick = async () => { try { state.result = validateAttemptResult(await api('/api/v2/attempts',{draftId:draft.id,activeSeconds:Math.max(0,Math.floor((Date.now()-state.started)/1000))})); state.overview=validateOverview(await api('/api/v2/overview')); concepts(); render(); } catch(error){showError(error)} };
}
document.querySelector('#export').onclick = async () => {
  try { const data=await api('/api/v2/export'); data.displayPreferences = {...preferences}; const blob=new Blob([JSON.stringify(data,null,2)],{type:'application/json'}); const url=URL.createObjectURL(blob); const link=document.createElement('a'); link.href=url; link.download='aesop-foreman-data.json'; link.click(); setTimeout(()=>URL.revokeObjectURL(url),1000); } catch(error){showError(error)}
};
document.querySelector('#delete').onclick = async () => {
  if (!confirm('Delete all local learner data for this preview? This cannot be undone.')) return;
  try { await api('/api/v2/delete',{}); try { localStorage.removeItem(preferenceKey); } catch (_) {} preferences = {minutes:20,textSize:'regular',theme:'system',focus:false}; applyPreferences(); state.result=null;state.answer='';await refresh(); } catch(error){showError(error)}
};
(async()=>{try{const overview=validateOverview(await api('/api/v2/overview'));state.overview=overview;state.conceptId=overview.pathRecommendation.conceptId;await refresh()}catch(error){showError(error)}})();
}
