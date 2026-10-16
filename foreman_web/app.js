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
  if (!Number.isSafeInteger(value) || value < 0) throw contractError(path, 'expected a non-negative whole number.');
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
  const raw = requireRecord(evidence, path);
  const byKind = {};
  const source = requireRecord(raw.byKind, `${path}.byKind`);
  for (const kind of EVIDENCE_KINDS) {
      const row = source[kind];
      const counts = requireRecord(row, `${path}.byKind.${kind}`);
      byKind[kind] = {
        unassistedCorrect: requireNumber(counts.unassistedCorrect, `${path}.byKind.${kind}.unassistedCorrect`),
        assistedCorrect: requireNumber(counts.assistedCorrect, `${path}.byKind.${kind}.assistedCorrect`),
        incorrect: requireNumber(counts.incorrect, `${path}.byKind.${kind}.incorrect`),
        ungraded: requireNumber(counts.ungraded, `${path}.byKind.${kind}.ungraded`),
      };
  }
  const delayedOutcomeByDay = {};
  const intervals = requireRecord(raw.delayedOutcomeByDay, `${path}.delayedOutcomeByDay`);
  for (const [day, status] of Object.entries(intervals)) {
      delayedOutcomeByDay[day] = requireString(status, `${path}.delayedOutcomeByDay.${day}`);
  }
  const delayedChecks = requireArray(raw.delayedChecks, `${path}.delayedChecks`);
  delayedChecks.forEach((check, index) => {
    const row = requireRecord(check, `${path}.delayedChecks[${index}]`);
    requireNumber(row.checkDelayDays, `${path}.delayedChecks[${index}].checkDelayDays`);
    requireString(row.evidenceKind, `${path}.delayedChecks[${index}].evidenceKind`);
    requireString(row.scoreStatus, `${path}.delayedChecks[${index}].scoreStatus`);
    requireString(row.attemptId, `${path}.delayedChecks[${index}].attemptId`);
    requireBoolean(row.assisted, `${path}.delayedChecks[${index}].assisted`);
    requireString(row.familiarityStatus, `${path}.delayedChecks[${index}].familiarityStatus`);
    const occurredAt = requireString(row.occurredAt, `${path}.delayedChecks[${index}].occurredAt`);
    if (Number.isNaN(Date.parse(occurredAt))) throw contractError(`${path}.delayedChecks[${index}].occurredAt`, 'expected a valid timestamp.');
  });
  return {
    byKind,
    delayedChecks,
    delayedOutcomeByDay,
    confidenceOutcomePairs: requireNumber(raw.confidenceOutcomePairs, `${path}.confidenceOutcomePairs`),
  };
}

function validateSignals(signals, path) {
  const raw = requireRecord(signals, path);
  const recordedAttempts = requireArray(raw.recordedAttempts, `${path}.recordedAttempts`);
  recordedAttempts.forEach((attempt, index) => {
    const item = requireRecord(attempt, `${path}.recordedAttempts[${index}]`);
    for (const field of ['id', 'activityId', 'contentVersion', 'evidenceKind', 'occurredAt',
      'gradingMethod', 'hintLevel', 'scoreStatus']) {
      requireString(item[field], `${path}.recordedAttempts[${index}].${field}`);
    }
    if (typeof item.firstAnswer !== 'string') throw contractError(`${path}.recordedAttempts[${index}].firstAnswer`, 'expected text.');
    requireBoolean(item.assisted, `${path}.recordedAttempts[${index}].assisted`);
    if (item.assisted !== (item.hintLevel !== 'none')) {
      throw contractError(`${path}.recordedAttempts[${index}].assisted`, 'does not match hint level.');
    }
    if (Number.isNaN(Date.parse(item.occurredAt))) throw contractError(`${path}.recordedAttempts[${index}].occurredAt`, 'expected a valid timestamp.');
    if (item.confidence != null && (typeof item.confidence !== 'number' || !Number.isFinite(item.confidence) || item.confidence < 0 || item.confidence > 1)) {
      throw contractError(`${path}.recordedAttempts[${index}].confidence`, 'expected a number from 0 to 1 or null.');
    }
    if (item.outsideStudy != null && !['none', 'some', 'unknown'].includes(item.outsideStudy)) {
      throw contractError(`${path}.recordedAttempts[${index}].outsideStudy`, 'expected none, some, unknown, or null.');
    }
  });
  return {
    attempts: requireNumber(raw.attempts, `${path}.attempts`),
    unassistedCorrect: requireNumber(raw.unassistedCorrect, `${path}.unassistedCorrect`),
    hintAssisted: requireNumber(raw.hintAssisted, `${path}.hintAssisted`),
    needsReview: requireNumber(raw.needsReview, `${path}.needsReview`),
    recentOutcome: raw.recentOutcome == null ? null : requireString(raw.recentOutcome, `${path}.recentOutcome`),
    recordedAttempts,
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
      lessonComplete: requireBoolean(row.lessonComplete, `${path}.lessonComplete`),
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
  const experiment = overview.experiment == null ? null : requireRecord(overview.experiment, 'overview.experiment');
  if (experiment) {
    const protocol = experiment.protocol == null ? null : requireRecord(experiment.protocol, 'overview.experiment.protocol');
    const protocolId = protocol?.id ?? experiment.protocolId;
    const protocolVersion = protocol?.version ?? experiment.protocolVersion;
    if (protocolId != null) requireString(protocolId, 'overview.experiment.protocolId');
    if (protocolVersion != null) requireString(protocolVersion, 'overview.experiment.protocolVersion');
    if ((protocolId == null) !== (protocolVersion == null)) {
      throw contractError('overview.experiment', 'protocol ID and version must appear together.');
    }
    if (experiment.arms != null) {
      const arms = requireRecord(experiment.arms, 'overview.experiment.arms');
      for (const arm of ['text', 'diagram']) {
        const row = requireRecord(arms[arm], `overview.experiment.arms.${arm}`);
        for (const count of ['assigned', 'exposed', 'eligible', 'correct', 'missing']) {
          requireNumber(row[count], `overview.experiment.arms.${arm}.${count}`);
        }
      }
    }
    if (requireString(experiment.status, 'overview.experiment.status') !== 'insufficient_evidence') {
      throw contractError('overview.experiment.status', 'unsupported finding status.');
    }
    requireString(experiment.reason, 'overview.experiment.reason');
  }
  return {
    ...overview,
    concepts: normalizedConcepts,
    pathRecommendation: {
      conceptId,
      action,
      reason: requireString(pathRecommendation.reason, 'overview.pathRecommendation.reason'),
    },
    experiment,
  };
}

export function validateLesson(data) {
  const lesson = requireRecord(data, 'lesson');
  const sources = requireArray(lesson.sources ?? [], 'lesson.sources');
  sources.forEach((source, index) => {
    const row = requireRecord(source, `lesson.sources[${index}]`);
    requireString(row.title, `lesson.sources[${index}].title`);
    const url = requireString(row.url, `lesson.sources[${index}].url`);
    let parsed;
    try { parsed = new URL(url); } catch (_) { throw contractError(`lesson.sources[${index}].url`, 'expected an absolute HTTPS URL.'); }
    if (parsed.protocol !== 'https:') throw contractError(`lesson.sources[${index}].url`, 'expected an absolute HTTPS URL.');
  });
  const method = lesson.method == null ? null : requireRecord(lesson.method, 'lesson.method');
  if (method) {
    if (!['text', 'diagram'].includes(method.conditionId)) {
      throw contractError('lesson.method.conditionId', 'expected text or diagram.');
    }
    requireString(method.protocolId, 'lesson.method.protocolId');
    requireString(method.protocolVersion, 'lesson.method.protocolVersion');
  }
  if (lesson.diagram != null && typeof lesson.diagram !== 'string') {
    throw contractError('lesson.diagram', 'expected text or null.');
  }
  if (lesson.diagram && method?.conditionId !== 'diagram') {
    throw contractError('lesson.diagram', 'a diagram requires the diagram condition.');
  }
  if (lesson.experimentNotice != null) requireString(lesson.experimentNotice, 'lesson.experimentNotice');
  return {
    conceptId: requireString(lesson.conceptId, 'lesson.conceptId'),
    title: requireString(lesson.title, 'lesson.title'),
    body: requireString(lesson.body, 'lesson.body'),
    completed: requireBoolean(lesson.completed ?? false, 'lesson.completed'),
    sources,
    method,
    diagram: lesson.diagram ?? null,
    experimentNotice: lesson.experimentNotice ?? null,
  };
}

function validateActivity(activity, path) {
  const row = requireRecord(activity, path);
  if (Object.hasOwn(row, 'explanation')) {
    throw contractError(`${path}.explanation`, 'must not be sent before the answer is scored.');
  }
  const type = requireString(row.type, `${path}.type`);
  if (!ACTIVITY_TYPES.has(type)) throw contractError(`${path}.type`, 'activity type is not recognized.');
  const evidenceKind = requireString(row.evidenceKind, `${path}.evidenceKind`);
  if (!EVIDENCE_KINDS.has(evidenceKind)) throw contractError(`${path}.evidenceKind`, 'evidence kind is not recognized.');
  requireString(row.id, `${path}.id`);
  requireString(row.prompt, `${path}.prompt`);
  if (row.learningObjective != null) requireString(row.learningObjective, `${path}.learningObjective`);
  if (row.difficulty != null) requireString(row.difficulty, `${path}.difficulty`);
  if (row.body != null && typeof row.body !== 'string') throw contractError(`${path}.body`, 'expected text or null.');
  const choices = requireArray(row.choices, `${path}.choices`);
  choices.forEach((choice, index) => {
    if (typeof choice !== 'string' || !choice) throw contractError(`${path}.choices[${index}]`, 'expected a non-empty string.');
  });
  if (type === 'choice' && !choices.length) throw contractError(`${path}.choices`, 'choice activity requires options.');
  const hints = requireArray(row.hints, `${path}.hints`);
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
  const hintLevels = requireArray(row.hintLevels, `${path}.hintLevels`);
  hintLevels.forEach((level, index) => {
    const value = requireString(level, `${path}.hintLevels[${index}]`);
    if (value !== ['nudge', 'targeted', 'worked_solution'][index]) {
      throw contractError(`${path}.hintLevels[${index}]`, 'hints must follow the published sequence.');
    }
  });
  return {
    id: requireString(row.id, `${path}.id`),
    firstAnswer: typeof row.firstAnswer === 'string' ? row.firstAnswer : requireString(row.firstAnswer, `${path}.firstAnswer`),
    hintLevels,
    confidence: row.confidence == null ? null : (() => {
      if (typeof row.confidence !== 'number' || !Number.isFinite(row.confidence) || row.confidence < 0 || row.confidence > 1) {
        throw contractError(`${path}.confidence`, 'expected a number from 0 to 1 or null.');
      }
      return row.confidence;
    })(),
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
  if (draft && !activity) throw contractError('session.draft', 'saved answer requires an activity.');
  if (draft) {
    for (const level of draft.hintLevels) {
      const hint = activity.hints.find(item => item.level === level);
      if (!hint || typeof hint.text !== 'string' || !hint.text.trim()) {
        throw contractError(`session.activity.hints.${level}`, 'saved hint text is missing.');
      }
    }
  }
  const recommendation = session.recommendation == null ? null : requireRecord(session.recommendation, 'session.recommendation');
  if (activity) requireString(recommendation?.reason, 'session.recommendation.reason');
  return {
    lessonRequired: false,
    activity,
    draft,
    recommendation,
    reason: typeof session.reason === 'string' ? session.reason : null,
    nextCheckAt: session.nextCheckAt ?? null,
  };
}

export function validateAttemptResult(data) {
  const result = requireRecord(data, 'attempt');
  requireString(result.attemptId, 'attempt.attemptId');
  const status = requireString(result.scoreStatus, 'attempt.scoreStatus');
  if (!['correct', 'incorrect', 'ungraded'].includes(status)) {
    throw contractError('attempt.scoreStatus', 'score status is not recognized.');
  }
  requireString(result.gradingMethod, 'attempt.gradingMethod');
  if (result.developmentOnly !== true) throw contractError('attempt.developmentOnly', 'draft status is required.');
  requireString(result.nextReason, 'attempt.nextReason');
  if (result.explanation != null) requireString(result.explanation, 'attempt.explanation');
  requireBoolean(result.assisted, 'attempt.assisted');
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

export function buildAttemptPayload(draftId, activeSeconds, confidence, outsideStudy, outsideStudyDetail = '') {
  requireString(draftId, 'attempt.draftId');
  requireNumber(activeSeconds, 'attempt.activeSeconds');
  if (confidence !== null && (typeof confidence !== 'number' || !Number.isFinite(confidence) || confidence < 0 || confidence > 1)) {
    throw contractError('attempt.confidence', 'expected a number from 0 to 1 or null.');
  }
  if (outsideStudy !== null && !['none', 'some', 'unknown'].includes(outsideStudy)) {
    throw contractError('attempt.outsideStudy', 'expected none, some, unknown, or null.');
  }
  if (typeof outsideStudyDetail !== 'string') throw contractError('attempt.outsideStudyDetail', 'expected text.');
  return { draftId, activeSeconds, confidence, outsideStudy, outsideStudyDetail: outsideStudyDetail.trim() };
}

export function lessonMarkup(body) {
  requireString(body, 'lesson.body');
  const escape = value => value.replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
  const inline = value => value.split(/(`[^`\n]+`)/g).map(part => part.startsWith('`') && part.endsWith('`')
    ? `<code>${escape(part.slice(1, -1))}</code>` : escape(part)).join('');
  const blocks = [];
  let paragraph = [];
  let code = [];
  let inCode = false;
  const flush = () => { if (paragraph.length) blocks.push(`<p>${inline(paragraph.join(' '))}</p>`); paragraph = []; };
  for (const line of body.split(/\r?\n/)) {
    if (line.trim().startsWith('```')) {
      flush();
      if (inCode) { blocks.push(`<pre class="lesson-code"><code>${escape(code.join('\n'))}</code></pre>`); code = []; }
      inCode = !inCode;
      continue;
    }
    if (inCode) { code.push(line); continue; }
    const heading = /^(#{2,3})\s+(.+)$/.exec(line);
    if (heading) { flush(); blocks.push(`<h${heading[1].length + 1}>${inline(heading[2])}</h${heading[1].length + 1}>`); continue; }
    if (!line.trim()) { flush(); continue; }
    paragraph.push(line.trim());
  }
  flush();
  if (code.length) blocks.push(`<pre class="lesson-code"><code>${escape(code.join('\n'))}</code></pre>`);
  return blocks.join('');
}

export function evidenceMarkup(evidence, recordedAttempts = []) {
  const normalized = normalizeEvidence(evidence, 'signals.evidence');
  const esc = value => String(value ?? '').replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
  const rows = Object.entries(normalized.byKind).map(([kind, count]) => `<tr><th scope="row">${esc(kind)}</th><td>${count.unassistedCorrect}</td><td>${count.assistedCorrect}</td><td>${count.incorrect}</td><td>${count.ungraded}</td></tr>`).join('');
  const delayed = normalized.delayedChecks.length ? normalized.delayedChecks.map(check => `<li>Day ${esc(check.checkDelayDays)} · ${esc(check.evidenceKind)} · ${esc(check.scoreStatus)} · ${check.assisted ? 'assisted' : 'independent'} · family familiarity ${esc(String(check.familiarityStatus ?? 'not_verified').replace('_', ' '))} · ${esc(new Date(check.occurredAt).toLocaleString())}</li>`).join('') : '<li>Insufficient evidence: no delayed held-out answer yet.</li>';
  const intervalStatus = Object.entries(normalized.delayedOutcomeByDay).map(([day, status]) => `<li>Day ${esc(day)}: ${esc(status.replace('_', ' '))}</li>`).join('');
  const history = recordedAttempts.length ? recordedAttempts.map(attempt => `<li><details><summary>${esc(attempt.activityId)} · ${esc(attempt.evidenceKind)} · ${esc(attempt.scoreStatus)} · ${attempt.assisted ? 'assisted' : 'independent'} · ${esc(new Date(attempt.occurredAt).toLocaleString())}</summary><p>Content ${esc(attempt.contentVersion)} · Hint: ${esc(attempt.hintLevel.replace('_', ' '))} · Method: ${esc(attempt.gradingMethod)}</p><p>Pre-hint confidence: ${attempt.confidence == null ? 'not provided' : `${Math.round(attempt.confidence * 100)}%`} · Outside study: ${esc(attempt.outsideStudy ?? 'not recorded')}</p><pre class="code">${esc(attempt.firstAnswer)}</pre></details></li>`).join('') : '<li>No attempts recorded yet.</li>';
  return `<details class="evidence-panel"><summary>Inspect learning evidence</summary><p class="muted">Observed answers by kind. Candidate-key matches are development feedback, not mastery.</p><div class="table-scroll"><table><thead><tr><th scope="col">Kind</th><th scope="col">Independent matches</th><th scope="col">Assisted matches</th><th scope="col">Incorrect</th><th scope="col">Ungraded</th></tr></thead><tbody>${rows}</tbody></table></div><p><strong>Delayed check status</strong></p><ul>${intervalStatus || '<li>Insufficient evidence: no delayed held-out answer yet.</li>'}</ul><p><strong>Delayed answers</strong></p><ul>${delayed}</ul><p><strong>Attempt history</strong></p><ul>${history}</ul><p class="muted">Independent scored answers with confidence recorded: ${normalized.confidenceOutcomePairs}. No calibrated estimate is available.</p></details>`;
}

if (typeof globalThis.document !== 'undefined') {
const content = document.querySelector('#content');
const conceptsEl = document.querySelector('#concepts');
const state = { overview: null, conceptId: null, lesson: null, session: null, answer: '', result: null, review: null, mode: 'recommended', started: Date.now(), confidence: null, outsideStudy: 'unknown', outsideStudyDetail: '' };
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
  const retry = document.createElement('button'); retry.type = 'button'; retry.className = 'button secondary';
  retry.textContent = 'Try loading again';
  retry.onclick = async () => { try { if (state.conceptId) await refresh(); else await boot(); } catch (next) { showError(next); } };
  el.append(retry);
  content.replaceChildren(el);
}
function concepts() {
  const path = state.overview?.pathRecommendation;
  conceptsEl.innerHTML = state.overview.concepts.map((c, i) => `<button class="concept ${c.id === state.conceptId ? 'active' : ''}" data-concept="${esc(c.id)}"><span class="num">${String(i+1).padStart(2,'0')}</span><span><span class="title">${esc(c.title)}</span><small>${c.lessonComplete ? 'Lesson read' : 'Lesson to read'} · ${c.signals.attempts} attempt${c.signals.attempts === 1 ? '' : 's'}${path && c.id === path.conceptId ? ' · Suggested' : ''}</small></span></button>`).join('');
  conceptsEl.querySelectorAll('[data-concept]').forEach(button => button.onclick = () => select(button.dataset.concept));
}
async function select(cid) {
  try {
    state.conceptId = cid; state.answer = ''; state.result = null; state.review = null; state.mode = 'recommended'; state.started = Date.now(); state.confidence = null; state.outsideStudy = 'unknown'; state.outsideStudyDetail = '';
    await refresh();
  } catch (error) { showError(error); }
}
async function chooseMorePractice() {
  await api('/api/v2/overrides', { conceptId: state.conceptId, mode: 'practice', reason: 'learner_choice' });
  state.result = null; state.review = null; state.answer = ''; state.mode = 'practice';
  state.confidence = null; state.outsideStudy = 'unknown'; state.outsideStudyDetail = '';
  await refresh();
}
async function refresh() {
  const cid = encodeURIComponent(state.conceptId);
  const [overview, lesson, session] = await Promise.all([
    api('/api/v2/overview'), api(`/api/v2/lesson?conceptId=${cid}`),
    api(`/api/v2/session?conceptId=${cid}&mode=${state.mode}&availableMinutes=${preferences.minutes}`)
  ]);
  const validOverview = validateOverview(overview);
  const validLesson = validateLesson(lesson);
  const validSession = validateSession(session);
  if (validLesson.conceptId !== state.conceptId) throw contractError('lesson.conceptId', 'does not match the selected concept.');
  state.overview = validOverview;
  state.lesson = validLesson;
  state.session = validSession;
  document.querySelector('.notice').textContent = `Draft content · ${state.overview.packVersion} · Candidate answer keys; independent review remains required. Results are for development, not mastery claims.`;
  if (state.session.draft) { state.answer = state.session.draft.firstAnswer; state.confidence = state.session.draft.confidence; }
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
  const finding = state.overview.experiment;
  const protocolId = finding?.protocol?.id ?? finding?.protocolId;
  const protocolVersion = finding?.protocol?.version ?? finding?.protocolVersion;
  const armsMarkup = finding?.arms ? `<div class="experiment-arms"><p><strong>Method A · text:</strong> ${finding.arms.text.eligible} eligible delayed answers, ${finding.arms.text.correct} correct; ${finding.arms.text.missing} missing or ineligible.</p><p><strong>Method B · text with diagram:</strong> ${finding.arms.diagram.eligible} eligible delayed answers, ${finding.arms.diagram.correct} correct; ${finding.arms.diagram.missing} missing or ineligible.</p></div>` : '';
  const experimentMarkup = finding ? `<div class="experiment-summary" aria-label="Instructional comparison findings"><strong>Instructional comparison: ${esc(finding.status.replace('_', ' '))}</strong><p>${esc(finding.reason)}</p>${armsMarkup}<small>${protocolId ? `Protocol ${esc(protocolId)} · ${esc(protocolVersion)}. ` : ''}A method preference is not evidence of better learning.</small></div>` : '';
  const intro = `<div class="section-kicker">CONCEPT ${String(index).padStart(2,'0')} / ${String(state.overview.concepts.length).padStart(2,'0')}</div><h2>${esc(current.title)}</h2><p class="lede">The goal is lasting understanding. The setting is yours to adjust; retrieval and delayed checks remain part of the learning path.</p><div class="path-note"><strong>Suggested next: ${esc(suggested.action.replace('_', ' '))} · ${esc(state.overview.concepts.find(c => c.id === suggested.conceptId)?.title)}</strong><p>${esc(suggested.reason)}</p>${suggested.conceptId !== state.conceptId ? '<button class="button secondary" id="follow-path">Go to suggested concept</button>' : '<span class="muted">You can choose any concept from Your Path.</span>'}</div>${experimentMarkup}<div class="signals"><div class="signal"><strong>${signals.attempts}</strong>attempts</div><div class="signal"><strong>${signals.unassistedCorrect}</strong>unassisted candidate matches</div><div class="signal"><strong>${signals.hintAssisted}</strong>hint-assisted attempts</div></div>${evidenceMarkup(signals.evidence, signals.recordedAttempts)}<div class="divider"></div>`;
  content.onclick = event => { if (event.target?.id === 'follow-path') select(suggested.conceptId); };
  if (!state.lesson.completed) {
    const method = state.lesson.method;
    const methodMarkup = method ? `<div class="method-note"><strong>Instructional method ${method.conditionId === 'diagram' ? 'B' : 'A'}</strong><p>${method.conditionId === 'diagram' ? 'The same written explanation includes a labeled diagram.' : 'Written explanation and retrieval practice.'}</p><small>Assignment ${esc(method.protocolId)} · ${esc(method.protocolVersion)}</small></div>` : '';
    const diagramMarkup = state.lesson.diagram ? `<figure class="lesson-diagram"><figcaption>Labeled concept diagram</figcaption><pre>${esc(state.lesson.diagram)}</pre></figure>` : '';
    content.innerHTML = intro + `<span class="pill">Short lesson</span><h2>${esc(state.lesson.title)}</h2>${methodMarkup}<article class="lesson-body">${lessonMarkup(state.lesson.body)}</article>${diagramMarkup}${state.lesson.experimentNotice ? `<p class="muted">${esc(state.lesson.experimentNotice)}</p>` : ''}<p class="sources">Sources: ${state.lesson.sources.map(s=>`<a href="${esc(s.url)}" target="_blank" rel="noopener noreferrer">${esc(s.title)}</a>`).join('')}</p><div class="button-row"><button class="button" id="complete">I've read this lesson →</button></div>`;
    document.querySelector('#complete').onclick = async () => { try { await api('/api/v2/lesson-completions',{conceptId:state.conceptId}); await refresh(); } catch(e){showError(e)} };
    return;
  }
  if (state.result) {
    const r = validateAttemptResult(state.result);
    const status = r.scoreStatus === 'ungraded' ? 'Saved for self review' : r.scoreStatus === 'correct' ? 'Candidate key match' : 'Try another approach';
    content.innerHTML = intro + `<div class="feedback"><h3>${status}</h3><p>${esc(r.nextReason)}</p>${r.explanation ? `<p><strong>Why:</strong> ${esc(r.explanation)}</p>` : ''}<p class="muted">${r.assisted ? 'Hint assisted · ' : ''}Development preview · No mastery claim</p></div>` +
      (r.rubric && !state.review ? `<div class="activity-card"><span class="label">SELF REVIEW · ORIGINAL ANSWER</span><pre class="code">${esc(state.answer)}</pre><p class="muted">For each criterion, quote the part of your first answer that supports a shown or partial rating.</p>${r.rubric.criteria.map(c=>`<div class="review-row" data-criterion="${esc(c.id)}"><p><strong>${esc(c.description)}</strong></p><select class="answer rating"><option value="unsure">Unsure</option><option value="shown">Shown</option><option value="partial">Partial</option><option value="not_shown">Not shown</option></select><input class="answer evidence" placeholder="Exact quote from your answer, if shown or partial" aria-label="Evidence for ${esc(c.description)}"></div>`).join('')}<div class="button-row"><button class="button" id="review">Save self review →</button></div></div>` : '') +
      (state.review ? `<div class="activity-card"><span class="label">COMPARE AND REVISE</span><p>${esc(state.review.nextStep.replace('_',' '))}</p><pre class="code">${esc(state.review.comparison.annotatedExample)}</pre><p class="muted">Common mistakes: ${esc((state.review.comparison.commonMistakes ?? []).join(' · '))}</p><label class="muted" for="revision">A revised answer, if you want to try again</label><textarea id="revision" class="answer long"></textarea><div class="button-row"><button class="button secondary" id="save-revision">Save revision</button></div></div>` : '') +
      `<div class="button-row"><button class="button" id="next">Continue →</button><button class="button secondary" id="more">Choose more practice (override)</button></div>`;
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
    document.querySelector('#next').onclick = async () => { state.result = null; state.review = null; state.answer = ''; state.confidence = null; state.outsideStudy = 'unknown'; state.outsideStudyDetail = ''; await refresh().catch(showError); };
    document.querySelector('#more').onclick = () => chooseMorePractice().catch(showError);
    return;
  }
  const s = state.session, a = s.activity;
  if (!a) {
    content.innerHTML = intro + `<div class="empty"><h3>You're caught up for now.</h3><p>${esc(s.reason || 'The next check will be offered later.')}</p>${s.nextCheckAt ? `<p>Next check: ${esc(new Date(s.nextCheckAt).toLocaleString())}</p>` : ''}</div><div class="button-row"><button class="button secondary" id="more">Choose more practice (override)</button></div>`;
    document.querySelector('#more').onclick = () => chooseMorePractice().catch(showError);
    return;
  }
  const saved = Boolean(s.draft);
  const previous = signals.recentOutcome === 'incorrect' ? 'Your previous scored answer missed its candidate key. The policy offers continued practice.' : signals.recentOutcome === 'ungraded' ? 'Your previous open answer remains ungraded; self review supplies the comparison.' : signals.recentOutcome === 'correct' ? 'Your previous answer matched a candidate key. A delayed check still requires time and unassisted evidence.' : 'Start with retrieval after reading the lesson.';
  const reason = saved ? 'Resume the first answer you already saved.' : s.recommendation?.reason || 'Continue with an available activity.';
  content.innerHTML = intro + `<span class="pill">${a.heldOut ? 'Delayed check' : 'Practice activity'}</span><div class="why"><strong>Why this activity?</strong>${esc(reason)} ${esc(previous)}${s.nextCheckAt && !a.heldOut ? `<p>Independent check time, if eligibility remains: ${esc(new Date(s.nextCheckAt).toLocaleString())}</p>` : ''}</div><div class="activity-card"><span class="label">${esc(a.type.replace('_',' '))} · ${esc(a.evidenceKind)}${a.difficulty ? ` · ${esc(a.difficulty)}` : ''}</span>${a.learningObjective ? `<p class="activity-objective"><strong>Learning objective:</strong> ${esc(a.learningObjective)}</p>` : ''}<h3>${esc(a.prompt)}</h3>${a.body ? `<pre class="code">${esc(a.body)}</pre>` : ''}<div id="answer-area"></div>${!saved ? '<div class="answer-context"><label for="confidence">How confident are you in this first answer?</label><select id="confidence" class="answer"><option value="">Prefer not to say</option><option value="0">0% · guessing</option><option value="0.25">25%</option><option value="0.5">50%</option><option value="0.75">75%</option><option value="1">100% · certain</option></select><p class="muted">Record this before opening any hints. You may leave it blank.</p></div>' : ''}<div class="button-row"><button id="save" class="button" ${saved?'disabled':''}>${saved?'First answer saved':'Save first answer →'}</button></div><div id="after-save"></div></div>`;
  drawAnswer(a, saved);
  if (!saved) {
    document.querySelector('#confidence').value = state.confidence == null ? '' : String(state.confidence);
    document.querySelector('#confidence').onchange = event => { state.confidence = event.target.value === '' ? null : Number(event.target.value); };
  }
  document.querySelector('#save').onclick = async () => {
    try {
      if (!state.answer.trim()) throw new Error('Enter an answer first.');
      await api('/api/v2/first-answers', { conceptId:state.conceptId, activityId:a.id, draftId:crypto.randomUUID(), answer:state.answer, confidence:state.confidence, mode:state.mode, availableMinutes:preferences.minutes });
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
  area.innerHTML = `<div class="hint-panel"><h4>A little help, if you need it</h4><p>Hints open in order. The answer you saved stays the same.</p>${a.hints.filter(h=>viewed.has(h.level)).map(h=>`<div class="hint"><strong>${esc(h.level.replace('_',' '))}</strong><br>${esc(h.text)}</div>`).join('')}<div class="answer-context"><h4>Answer context</h4><p>Confidence was saved with the first answer before hints: ${draft.confidence == null ? 'not provided' : `${Math.round(draft.confidence * 100)}%`}.</p><p>Outside study helps interpret later outcomes; it does not change scoring.</p><label for="outside-study">Since studying this concept here, have you studied it elsewhere?</label><select id="outside-study" class="answer"><option value="unknown">I am not sure / prefer not to say</option><option value="none">No outside study</option><option value="some">Yes, some outside study</option></select><label for="outside-study-detail">Outside study details (optional)</label><input id="outside-study-detail" class="answer" maxlength="500" value="${esc(state.outsideStudyDetail)}" placeholder="For example, a textbook or another course"></div><div class="button-row">${viewed.size<a.hints.length?'<button id="hint" class="button secondary">Open next hint</button>':''}<button id="submit" class="button">Check saved answer →</button></div></div>`;
  document.querySelector('#outside-study').value = state.outsideStudy;
  document.querySelector('#outside-study').onchange = event => { state.outsideStudy = event.target.value; };
  document.querySelector('#outside-study-detail').oninput = event => { state.outsideStudyDetail = event.target.value; };
  const hint = document.querySelector('#hint');
  if (hint) hint.onclick = async () => { try { await api('/api/v2/hints',{draftId:draft.id}); await refresh(); } catch(error){showError(error)} };
  document.querySelector('#submit').onclick = async () => { try { const payload = buildAttemptPayload(draft.id, Math.max(0,Math.floor((Date.now()-state.started)/1000)), state.confidence, state.outsideStudy, state.outsideStudyDetail); const result = validateAttemptResult(await api('/api/v2/attempts',payload)); const overview=validateOverview(await api('/api/v2/overview')); state.result=result; state.overview=overview; concepts(); render(); } catch(error){showError(error)} };
}
document.querySelector('#export').onclick = async () => {
  try { const data=await api('/api/v2/export'); data.displayPreferences = {...preferences}; const blob=new Blob([JSON.stringify(data,null,2)],{type:'application/json'}); const url=URL.createObjectURL(blob); const link=document.createElement('a'); link.href=url; link.download='aesop-foreman-data.json'; link.click(); setTimeout(()=>URL.revokeObjectURL(url),1000); } catch(error){showError(error)}
};
document.querySelector('#delete').onclick = async () => {
  if (!confirm('Delete all local learner data for this preview? This cannot be undone.')) return;
  try { await api('/api/v2/delete',{}); try { localStorage.removeItem(preferenceKey); } catch (_) {} preferences = {minutes:20,textSize:'regular',theme:'system',focus:false}; applyPreferences(); state.result=null;state.answer='';await refresh(); } catch(error){showError(error)}
};
async function boot() {
  const overview = validateOverview(await api('/api/v2/overview'));
  state.overview = overview;
  state.conceptId = overview.pathRecommendation.conceptId;
  await refresh();
}
boot().catch(showError);
}
