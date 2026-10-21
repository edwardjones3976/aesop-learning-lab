import assert from 'node:assert/strict';
import { spawnSync } from 'node:child_process';
import { readFileSync } from 'node:fs';
import { runInNewContext } from 'node:vm';
import { test } from 'node:test';
import { fileURLToPath } from 'node:url';

import {
  workspaceMarkup,
  consentMarkup,
  buildAttemptPayload,
  evidenceMarkup,
  evidenceSnapshot,
  evidenceSummaryMarkup,
  lessonMarkup,
  normalizeEvidence,
  reviewTimingMarkup,
  solutionMarkup,
  validateAttemptResult,
  validateLesson,
  validateOverview,
  validateSession,
} from '../foreman_web/app.js';

const repoRoot = fileURLToPath(new URL('../', import.meta.url));
const sourcePath = fileURLToPath(new URL('../src/', import.meta.url));

test('delete leaves no lesson and refreshes only after explicitly starting again', async () => {
  const source = readFileSync(new URL('../foreman_web/app.js', import.meta.url), 'utf8');
  const handler = source.slice(source.indexOf("function renderDeleted()"),
    source.indexOf('async function boot()'));
  for (const outcome of ['success', 'cancel', 'failure', 'storage unavailable']) {
    const buttons = { '#delete': {}, '#start-again': {} };
    const calls = [];
    const originalLesson = { title: 'Old lesson' };
    const context = {
      document: { querySelector: selector => {
        assert.ok(Object.hasOwn(buttons, selector), selector);
        return buttons[selector];
      } },
      AbortController, apiController: new AbortController(),
      confirm: () => outcome !== 'cancel',
      api: async path => {
        calls.push(path);
        if (path === '/api/v2/restart' && context.failRestart) throw new Error('Restart failed');
        if (outcome === 'failure') throw new Error('Delete failed');
      },
      localStorage: { removeItem: key => {
        assert.equal(key, 'preferences');
        calls.push('clear preferences');
        if (outcome === 'storage unavailable') throw new Error('Storage unavailable');
      } },
      preferenceKey: 'preferences', preferences: {},
      applyPreferences: () => calls.push('apply preferences'),
      state: { lesson: originalLesson, session: {}, result: {}, answer: 'saved', review: {}, comparison: {}, confidence: 0.75, outsideStudy: 'some', outsideStudyDetail: 'Old study', mode: 'practice', comparisonHint: 'Old hint', view: 'comparison', started: 1 },
      updateViewNavigation: () => calls.push('navigation'),
      conceptsEl: { innerHTML: 'Old navigation' },
      content: { innerHTML: 'Old lesson', querySelector: () => context.restartMessage },
      restartMessage: {},
      boot: async () => { calls.push('refresh'); },
      showError: error => calls.push(error.message),
    };
    runInNewContext(handler, context);
    await buttons['#delete'].onclick();
    if (outcome === 'cancel' || outcome === 'failure') {
      assert.deepEqual(calls, outcome === 'cancel' ? [] : ['/api/v2/delete', 'Delete failed']);
      if (outcome === 'failure') assert.equal(context.state.deleted, false);
      assert.equal(context.content.innerHTML, 'Old lesson');
      assert.equal(context.state.lesson, originalLesson);
      assert.equal(buttons['#start-again'].onclick, undefined);
      continue;
    }
    assert.deepEqual(calls, ['/api/v2/delete', 'clear preferences', 'apply preferences']);
    assert.equal(context.state.lesson, null);
    assert.equal(context.state.session, null);
    assert.equal(context.state.answer, '');
    assert.equal(context.state.deleted, true);
    assert.equal(context.state.confidence, null);
    assert.equal(context.state.outsideStudy, 'unknown');
    assert.equal(context.state.outsideStudyDetail, '');
    assert.equal(context.state.mode, 'recommended');
    assert.equal(context.state.comparisonHint, '');
    assert.equal(context.state.result, null);
    assert.equal(context.state.review, null);
    assert.equal(context.conceptsEl.innerHTML, '');
    assert.match(context.content.innerHTML, /<h2>Your data was deleted<\/h2>/);
    assert.match(context.content.innerHTML, /No lesson is loaded/);
    assert.match(context.content.innerHTML, /<button id="start-again" class="button">Start again<\/button>/);
    context.failRestart = true;
    await buttons['#start-again'].onclick();
    assert.equal(context.state.deleted, true);
    assert.equal(context.restartMessage.textContent, 'Restart failed');
    assert.ok(!calls.includes('refresh'));
    context.failRestart = false;
    context.state.started = 1;
    await buttons['#start-again'].onclick();
    assert.equal(context.state.deleted, false);
    assert.equal(context.state.view, 'path');
    assert.ok(context.state.started > 1);
    assert.ok(calls.includes('/api/v2/restart'));
    assert.equal(calls.at(-2), 'navigation');
    assert.equal(calls.at(-1), 'refresh');
    assert.equal(calls.filter(call => call === 'refresh').length, 1);
  }
});

test('deleted state blocks refresh, navigation, retry and all API requests', async () => {
  const source = readFileSync(new URL('../foreman_web/app.js', import.meta.url), 'utf8');
  const nodes = new Map();
  const node = () => ({ dataset: {}, classList: { toggle() {} }, setAttribute() {},
    addEventListener() {}, remove() {}, append(child) { this.child = child; }, innerHTML: '' });
  const content = node();
  content.replaceChildren = child => { content.child = child; };
  const context = {
    document: { querySelector: selector => {
      if (!nodes.has(selector)) nodes.set(selector, node());
      return nodes.get(selector);
    }, createElement: node, documentElement: node(), body: node() },
    AbortController,
    confirm: () => true,
    content, conceptsEl: node(),
    localStorage: { getItem() { return null; }, setItem(key, value) { context.savedPreferences = JSON.parse(value); } },
    matchMedia: () => ({ matches: false, addEventListener() {} }),
    fetch: () => { assert.fail('deleted state must not send a request'); },
  };
  const runtime = source.slice(source.indexOf('const state ='), source.lastIndexOf('boot().catch(showError);'));
  runInNewContext(runtime + `
    showError(new Error('Before deletion'));
    globalThis.retry = content.child.child;
    state.deleted = true;
    globalThis.actions = { refresh, refreshComparison, select, chooseMorePractice, boot, api, showError };
    globalThis.viewState = state;
  `, context);
  content.innerHTML = 'Your data was deleted';
  const before = JSON.stringify(context.viewState);
  for (const action of [
    () => nodes.get('#minutes').onchange({ target: { value: '45' } }),
    () => nodes.get('#regular-path').onclick(),
    () => nodes.get('#personal-comparison').onclick(),
    () => context.retry.onclick(),
    () => context.actions.select('old-concept'),
    () => context.actions.refresh(),
    () => context.actions.refreshComparison(),
    () => context.actions.chooseMorePractice(),
    () => context.actions.boot(),
  ]) {
    await action();
    assert.equal(content.innerHTML, 'Your data was deleted');
    assert.equal(JSON.stringify(context.viewState), before);
  }
  assert.equal(context.savedPreferences.minutes, 45);
  runInNewContext(`
    showError = error => { throw error; };
    refresh = refreshComparison = boot = () => { throw new Error('Wrapper called enrollment'); };
  `, context);
  for (const action of [
    () => nodes.get('#minutes').onchange({ target: { value: '45' } }),
    () => nodes.get('#regular-path').onclick(),
    () => nodes.get('#personal-comparison').onclick(),
    () => context.retry.onclick(),
  ]) await action();
  // The shared API guard also blocks detached old lesson/comparison handlers.
  for (const path of ['/api/v2/lesson', '/api/v2/session', '/api/v2/first-answers',
    '/api/v2/lesson-completions', '/api/v2/overrides', '/api/v2/hints',
    '/api/v2/attempts', '/api/v2/self-reviews', '/api/v2/personal-comparison/enroll',
    '/api/v2/personal-comparison/start', '/api/v2/personal-comparison/open',
    '/api/v2/personal-comparison/answer']) {
    await assert.rejects(context.actions.api(path, {}), /Start again/);
  }
  // Simulate a full page reload against a persisted deletion marker.
  runInNewContext('state.deleted = false; boot = actions.boot;', context);
  const bootCalls = [];
  context.fetch = async path => { bootCalls.push(path); return { ok: true, json: async () => ({ deleted: true }) }; };
  await context.actions.boot();
  assert.deepEqual(bootCalls, ['/api/v2/overview']);
  assert.equal(context.viewState.deleted, true);
  assert.match(content.innerHTML, /Your data was deleted/);
  content.innerHTML = 'Your data was deleted';
  runInNewContext('showError = actions.showError;', context);
  context.viewState.deleted = false;
  let finishResponse, finishDelete, oldSignal;
  context.fetch = (path, options) => new Promise(resolve => {
    if (path === '/api/v2/delete') finishDelete = resolve;
    else { finishResponse = resolve; oldSignal = options.signal; }
  });
  const pending = context.actions.api('/api/v2/personal-comparison');
  const deleting = nodes.get('#delete').onclick();
  assert.equal(context.viewState.deleted, true);
  assert.equal(oldSignal.aborted, true);
  await nodes.get('#minutes').onchange({ target: { value: '45' } });
  await assert.rejects(context.actions.api('/api/v2/lesson', {}), /Start again/);
  finishDelete({ ok: false, json: async () => ({ message: 'Delete failed' }) });
  await deleting;
  assert.equal(content.child.textContent, 'Delete failed');
  assert.equal(context.viewState.deleted, false);
  // Even after failure restores usability, the previous session's results are ignored.
  finishResponse({ ok: true, json: async () => ({ oldLearner: true }) });
  await assert.rejects(pending, /Start again/);
  assert.equal(content.innerHTML, 'Your data was deleted');
});

const emptyEvidence = () => ({
  byKind: Object.fromEntries(['recognition', 'recall', 'explanation', 'application', 'transfer']
    .map(kind => [kind, { unassistedCorrect: 0, assistedCorrect: 0, incorrect: 0, ungraded: 0 }])),
  delayedChecks: [],
  delayedOutcomeByDay: { 1: 'insufficient_evidence', 7: 'insufficient_evidence' },
  confidenceOutcomePairs: 0,
});

const baseConcept = (id, title, signals = {}) => ({
  id,
  title,
  lessonComplete: false,
  signals: {
    attempts: 0,
    unassistedCorrect: 0,
    hintAssisted: 0,
    needsReview: 0,
    recentOutcome: null,
    recordedAttempts: [],
    evidence: emptyEvidence(),
    ...signals,
  },
});

const baseOverview = (concepts, pathRecommendation) => ({
  developmentOnly: true,
  packStatus: 'draft',
  packVersion: 'm1-draft.3',
  concepts,
  pathRecommendation,
});

test('earliest invalid overview value is reported at the root', () => {
  assert.throws(() => validateOverview(null), /overview: expected an object/);
});

test('missing pathRecommendation is reported before render would touch concepts', () => {
  const payload = baseOverview(
    [baseConcept('c1', 'One')],
    undefined,
  );
  delete payload.pathRecommendation;
  assert.throws(() => validateOverview(payload), /overview\.pathRecommendation: expected an object/);
});

test('missing evidence is identified before rendering instead of displayed as zero progress', () => {
  const payload = baseOverview(
    [baseConcept('c1', 'One', { evidence: undefined })],
    { conceptId: 'c1', action: 'lesson', reason: 'Begin.' },
  );
  assert.throws(() => validateOverview(payload), /overview\.concepts\[0\]\.signals\.evidence: expected an object/);
  const html = evidenceMarkup(emptyEvidence());
  assert.match(html, /Inspect learning evidence/);
});

test('returning evidence keeps unassisted, assisted, delayed, and missing counts distinct', () => {
  const evidence = emptyEvidence();
  evidence.byKind.recognition.unassistedCorrect = 1;
  evidence.byKind.recall.assistedCorrect = 1;
  evidence.byKind.application.incorrect = 1;
  evidence.delayedChecks.push({ attemptId: 'later', checkDelayDays: 1, evidenceKind: 'application',
    scoreStatus: 'incorrect', assisted: false, familiarityStatus: 'not_verified',
    occurredAt: '2026-01-02T12:00:00Z' });
  evidence.delayedOutcomeByDay['1'] = 'observed';
  assert.deepEqual(evidenceSnapshot(evidence), {
    independent: 1, assisted: 1, incorrect: 1, ungraded: 0,
    missingKinds: 2, delayedIndependent: 1, delayedMissing: 1,
  });
  const html = evidenceSummaryMarkup(evidence);
  assert.match(html, /Unassisted candidate matches/);
  assert.match(html, /Unassisted counts may include repeated families/);
  assert.match(html, /Assisted candidate matches/);
  assert.match(html, /Delayed answers are a subset/);
});

test('optional review schedule and saved draft validate without changing legacy overview', () => {
  const payload = baseOverview([baseConcept('c1', 'One')], { conceptId: 'c1', action: 'resume', reason: 'Resume.' });
  assert.equal(validateOverview(payload).concepts[0].signals.reviewSchedule, null);
  payload.concepts[0].signals.reviewSchedule = { dueAt: '2026-01-02T12:00:00Z', status: 'due', reason: 'Check recall.' };
  payload.concepts[0].signals.openDraft = { activityId: 'item-1', savedAt: '2026-01-01T12:00:00Z', hintLevel: 'nudge' };
  const valid = validateOverview(payload).concepts[0].signals;
  assert.equal(valid.reviewSchedule.status, 'due');
  assert.equal(valid.openDraft.hintLevel, 'nudge');
  payload.concepts[0].signals.reviewSchedule.dueAt = 'not a date';
  assert.throws(() => validateOverview(payload), /reviewSchedule\.dueAt/);
});

test('descriptive protocol requires independent learner counts per arm', () => {
  const payload = baseOverview([baseConcept('c1', 'One')],
    { conceptId: 'c1', action: 'lesson', reason: 'Begin.' });
  payload.experiment = { protocol: { id: 'text-vs-labeled-diagram', version: 'v2' },
    status: 'insufficient_evidence', reason: 'One learner.', analysisUnit: 'independent_learner',
    arms: Object.fromEntries(['text', 'diagram'].map(arm => [arm,
      { assigned: 1, exposed: 1, eligible: 0, correct: 0, missing: 1, independentLearners: 0 }])) };
  assert.equal(validateOverview(payload).experiment.analysisUnit, 'independent_learner');
  payload.experiment.arms.text.provisional = 1;
  payload.experiment.arms.text.candidateKeyMatches = 1;
  payload.experiment.arms.text.late = 1;
  assert.equal(validateOverview(payload).experiment.arms.text.provisional, 1);
  payload.experiment.arms.text.late = null;
  payload.experiment.arms.text.provisional = 'one';
  assert.throws(() => validateOverview(payload), /arms\.text\.provisional/);
  payload.experiment.arms.text.provisional = 1;
  delete payload.experiment.arms.text.independentLearners;
  assert.throws(() => validateOverview(payload), /arms\.text\.independentLearners/);
});

test('review timing uses a controlled clock and escapes reason text', () => {
  const schedule = { dueAt: '2026-01-02T12:00:00Z', status: 'upcoming', reason: '<review>' };
  const before = reviewTimingMarkup(schedule, null, new Date('2026-01-01T12:00:00Z'));
  assert.match(before, /Upcoming delayed review/);
  const due = reviewTimingMarkup(schedule, null, new Date('2026-01-03T12:00:00Z'));
  assert.match(due, /Delayed review due/);
  assert.match(due, /&lt;review&gt;/);
  assert.doesNotMatch(due, /<review>/);
  const legacy = reviewTimingMarkup(null, { nextCheckAt: null, activity: { heldOut: true },
    recommendation: { reason: 'Held-out check.' } }, new Date('2026-01-03T12:00:00Z'));
  assert.match(legacy, /Delayed review due/);
});

test('null evidence.byKind is rejected with a contract path', () => {
  assert.throws(
    () => normalizeEvidence({ byKind: null }, 'signals.evidence'),
    /signals\.evidence\.byKind: expected an object/,
  );
});

test('a delayed check without assistance status cannot be called independent', () => {
  const evidence = emptyEvidence();
  evidence.delayedChecks.push({ attemptId: 'attempt-1', checkDelayDays: 1,
    evidenceKind: 'application', scoreStatus: 'correct',
    familiarityStatus: 'not_verified', occurredAt: '2026-01-02T12:00:00Z' });
  assert.throws(() => normalizeEvidence(evidence), /delayedChecks\[0\]\.assisted/);
});

test('delayed evidence distinguishes target delay from actual elapsed delay', () => {
  const evidence = emptyEvidence();
  evidence.delayedChecks.push({ attemptId: 'late', checkDelayDays: 7, evidenceKind: 'transfer',
    scoreStatus: 'incorrect', assisted: false, familiarityStatus: 'not_verified',
    dueAt: '2026-01-08T12:00:00Z', actualDelayDays: 9.25,
    occurredAt: '2026-01-10T18:00:00Z' });
  const html = evidenceMarkup(evidence);
  assert.match(html, /Target delay 7 days/);
  assert.match(html, /Actual delay 9.25 days/);
  assert.match(html, /Due <time/);
  evidence.delayedChecks[0].actualDelayDays = -1;
  assert.throws(() => normalizeEvidence(evidence), /actualDelayDays/);
});

test('early delayed evidence shows timing status without rounding up to the target', () => {
  const evidence = emptyEvidence();
  evidence.delayedChecks.push({ attemptId: 'early', checkDelayDays: 1, evidenceKind: 'application',
    scoreStatus: 'correct', assisted: false, familiarityStatus: 'not_verified',
    dueAt: '2026-01-02T12:00:00Z', actualDelayDays: 0.999, timingStatus: 'early',
    occurredAt: '2026-01-02T11:59:30Z' });
  const html = evidenceMarkup(evidence);
  assert.match(html, /Actual delay 0\.999 days · early/);
  assert.doesNotMatch(html, /Actual delay 1(?:\.00)? days/);
});

test('content quality candidates remain review candidates and escape their reason', () => {
  const evidence = emptyEvidence();
  evidence.contentQualityCandidates = [{ activityId: 'item-1', attemptIds: ['a1', 'a2'],
    reason: '<script>repeated misses</script>' }];
  const html = evidenceMarkup(evidence);
  assert.match(html, /Content review candidates/);
  assert.match(html, /Requires content review/);
  assert.match(html, /&lt;script&gt;/);
  assert.doesNotMatch(html, /<script>/);
  delete evidence.contentQualityCandidates[0].attemptIds;
  assert.throws(() => normalizeEvidence(evidence), /contentQualityCandidates\[0\]\.attemptIds/);
});

test('attempt history preserves assistance and escapes the saved answer', () => {
  const attempt = { id: 'a1', activityId: 'item-1', contentVersion: 'v3',
    evidenceKind: 'recognition', occurredAt: '2026-01-01T12:00:00Z',
    firstAnswer: '<script>alert(1)</script>', scoreStatus: 'incorrect',
    gradingMethod: 'development_fixture_exact_key', hintLevel: 'nudge', assisted: true,
    confidence: 0.5, outsideStudy: 'unknown' };
  const payload = baseOverview([baseConcept('c1', 'One', { recordedAttempts: [attempt] })],
    { conceptId: 'c1', action: 'practice', reason: 'Try again.' });
  const overview = validateOverview(payload);
  const html = evidenceMarkup(overview.concepts[0].signals.evidence,
    overview.concepts[0].signals.recordedAttempts);
  assert.match(html, /item-1.*assisted/);
  assert.match(html, /&lt;script&gt;/);
  assert.match(html, /Pre-hint confidence: 50%/);
  assert.doesNotMatch(html, /<script>/);
  attempt.assisted = false;
  assert.throws(() => validateOverview(payload), /recordedAttempts\[0\]\.assisted/);
});

test('session draft missing hintLevels is rejected rather than losing assistance history', () => {
  const activity = {
    id: 'a1',
    type: 'choice',
    evidenceKind: 'recognition',
    prompt: 'Pick one',
    choices: ['yes'],
    hints: [{ level: 'nudge' }],
  };
  assert.throws(() => validateSession({
    activity,
    draft: { id: 'd1', firstAnswer: 'yes' },
    recommendation: { reason: 'Practice' },
  }), /session\.draft\.hintLevels: expected an array/);
});

test('saved hint must have revealed text in the offered activity', () => {
  const session = { activity: { id: 'a1', type: 'choice', evidenceKind: 'recognition',
    prompt: 'Pick one', choices: ['yes'], hints: [{ level: 'nudge' }] },
    draft: { id: 'd1', firstAnswer: 'yes', hintLevels: ['nudge'] },
    recommendation: { reason: 'Resume.' } };
  assert.throws(() => validateSession(session), /session\.activity\.hints\.nudge/);
  session.activity.hints[0].text = 'Look at the return statement.';
  assert.equal(validateSession(session).draft.hintLevels[0], 'nudge');
  session.draft.confidence = 0.75;
  assert.equal(validateSession(session).draft.confidence, 0.75);
  session.draft.confidence = 2;
  assert.throws(() => validateSession(session), /session\.draft\.confidence/);
});

test('activity objective is available before answer while explanation is withheld', () => {
  const activity = { id: 'a1', type: 'choice', evidenceKind: 'recognition', prompt: 'Pick one',
    learningObjective: 'Distinguish return from print', difficulty: 'introductory',
    heldOut: true, choices: ['return 1'], hints: [] };
  const session = { activity, draft: null, recommendation: { reason: 'Begin practice.' } };
  const valid = validateSession(session);
  assert.equal(valid.activity.learningObjective, 'Distinguish return from print');
  assert.equal(valid.activity.difficulty, 'introductory');
  assert.equal(Object.hasOwn(valid.activity, 'explanation'), false);
  activity.explanation = 'return sends the value back';
  assert.throws(() => validateSession(session), /session\.activity\.explanation: must not be sent/);
  delete activity.explanation;
  activity.solution = { answer: 'return 1' };
  assert.throws(() => validateSession(session), /session\.activity\.solution: must not be sent/);
  delete activity.solution;
  activity.hints = [{ level: 'worked_solution', text: 'return 1' }];
  assert.throws(() => validateSession(session), /unrequested hint text must not be sent/);
});

test('live preview API payloads validate for all five concepts', () => {
  const script = `
import json, tempfile
from pathlib import Path
from uuid import uuid4
from aesop_lab.foreman import Preview

path = Path(tempfile.mkdtemp()) / "learner.db"
preview = Preview(path)
preview.consent()
try:
    order = preview.pack.learning_order()
    assert len(order) == 5
    overview = preview.overview()
    saved_sessions = {}
    for cid in order:
        lesson = preview.lesson(cid)
        preview.complete_lesson(cid)
        session = preview.session(cid)
        activity = session.get("activity")
        if activity and activity["type"] == "choice":
            draft_id = str(uuid4())
            answer = activity["choices"][0]
            preview.first_answer({
                "conceptId": cid,
                "activityId": activity["id"],
                "draftId": draft_id,
                "answer": answer,
            })
            preview.hint({"draftId": draft_id})
            saved_sessions[cid] = preview.session(cid)
            preview.submit({"draftId": draft_id, "activeSeconds": 1})
    print(json.dumps({
        "overview": overview,
        "savedSessions": saved_sessions,
        "concepts": {cid: {
            "lesson": preview.lesson(cid),
            "session": preview.session(cid),
        } for cid in order},
    }))
finally:
    preview.store.close()
`;
  const result = spawnSync(process.env.PYTHON ?? 'python', ['-c', script], {
    cwd: repoRoot,
    env: { ...process.env, PYTHONPATH: sourcePath },
    encoding: 'utf8',
  });
  assert.equal(result.status, 0, result.stderr || result.stdout);
  const payload = JSON.parse(result.stdout);
  validateOverview(payload.overview);
  // Exercise the actual renderer with string output and handler stubs; no DOM is needed.
  const source = readFileSync(new URL('../foreman_web/app.js', import.meta.url), 'utf8');
  const renderSource = source.slice(source.indexOf('function renderWorkspace() {'),
    source.indexOf('function drawAnswer('));
  const escapeSource = source.match(/^const esc = .*;$/m)[0];
  for (const [index, concept] of payload.overview.concepts.entries()) {
    const lesson = { ...payload.concepts[concept.id].lesson, completed: false };
    assert.equal(lesson.title, concept.title);
    const content = {};
    const completeButton = {};
    const context = {
      state: { overview: payload.overview, conceptId: concept.id, lesson, session: {} },
      content,
      document: { querySelector: selector => {
        assert.equal(selector, '#complete');
        return completeButton;
      } },
      workspaceMarkup,
  consentMarkup, evidenceSummaryMarkup, evidenceMarkup, lessonMarkup, reviewTimingMarkup,
    };
    runInNewContext(`${escapeSource}\n${renderSource}\nrenderWorkspace();`, context);
    const title = `<h2>${concept.title}</h2>`;
    assert.equal(content.innerHTML.split(title).length - 1, 1);
    assert.equal((content.innerHTML.match(/<h2>/g) ?? []).length, 1);
    assert.match(content.innerHTML, new RegExp(`CONCEPT 0${index + 1} / 05`));
    assert.match(content.innerHTML, /<span class="pill">Worked answer first · draft lesson<\/span>/);
    assert.equal(typeof completeButton.onclick, 'function');
    lesson.title = '<Distinct lesson title>';
    runInNewContext('renderWorkspace();', context);
    assert.ok(content.innerHTML.includes(title));
    assert.equal((content.innerHTML.match(/<h2>/g) ?? []).length, 1);
    assert.match(content.innerHTML, /<h3>&lt;Distinct lesson title&gt;<\/h3>/);
    assert.doesNotMatch(content.innerHTML, /<Distinct lesson title>/);
  }
  for (const saved of Object.values(payload.savedSessions)) validateSession(saved);
  for (const cid of Object.keys(payload.concepts)) {
    validateLesson(payload.concepts[cid].lesson);
    validateSession(payload.concepts[cid].session);
  }
});

test('attempt result validation guards feedback rendering', () => {
  const result = validateAttemptResult({
    attemptId: 'a',
    scoreStatus: 'correct',
    gradingMethod: 'key',
    assisted: false,
    nextReason: 'Matched.',
    developmentOnly: true,
  });
  assert.equal(result.scoreStatus, 'correct');
  assert.equal(validateAttemptResult({ ...result, explanation: 'return sends a value back' }).explanation,
    'return sends a value back');
  assert.throws(
    () => validateAttemptResult({ attemptId: 'a', scoreStatus: 'unknown', gradingMethod: 'key',
      developmentOnly: true, assisted: false, nextReason: 'Unknown.' }),
    /attempt\.scoreStatus/,
  );
  assert.throws(() => validateAttemptResult({ attemptId: 'a', scoreStatus: 'correct',
    gradingMethod: 'key', assisted: false, nextReason: 'Matched.' }),
  /attempt\.developmentOnly/);
});

test('candidate solution is intentionally revealed only for a scored result', () => {
  const result = { attemptId: 'a', scoreStatus: 'incorrect', gradingMethod: 'development_fixture_exact_key',
    assisted: false, nextReason: 'Candidate key did not match.', developmentOnly: true,
    solution: { kind: 'candidate_key', answer: '<return 1>', reasoning: 'Return sends a value.',
      misconception: '<print> only displays it.' } };
  const html = solutionMarkup(result);
  assert.match(html, /<details class="solution-panel"><summary>Reveal candidate answer and reasoning/);
  assert.match(html, /&lt;return 1&gt;/);
  assert.match(html, /&lt;print&gt;/);
  assert.doesNotMatch(html, /<return 1>/);
  assert.equal(solutionMarkup({ ...result, solution: undefined }), '');
  assert.throws(() => validateAttemptResult({ ...result, scoreStatus: 'ungraded' }),
    /ungraded answers cannot have a scored solution/);
});

test('experiment lesson condition controls optional labeled diagram', () => {
  const base = { conceptId: 'c1', title: 'Functions', body: 'Shared explanation', completed: false,
    sources: [], method: { conditionId: 'text', protocolId: 'pilot-1', protocolVersion: '1' },
    diagram: null, experimentNotice: 'Assignment is stable.' };
  assert.equal(validateLesson(base).method.conditionId, 'text');
  assert.equal(validateLesson({ ...base, method: { ...base.method, studyTargetMinutes: 10 } }).method.studyTargetMinutes, 10);
  assert.throws(() => validateLesson({ ...base, method: { ...base.method, studyTargetMinutes: 0 } }), /studyTargetMinutes/);
  assert.equal(validateLesson({ ...base, method: { ...base.method, conditionId: 'diagram' }, diagram: 'input → output' }).diagram, 'input → output');
  assert.throws(() => validateLesson({ ...base, diagram: 'leaked diagram' }), /lesson\.diagram: a diagram requires/);
  assert.throws(() => validateLesson({ ...base, method: { ...base.method, conditionId: 'unknown' } }), /lesson\.method\.conditionId/);
});

test('lesson headings and Python examples render as escaped structured text', () => {
  const html = lessonMarkup('## Objective\nUse `return`.\n\n```python\nprint("<unsafe>")\n```\n<script>alert(1)</script>');
  assert.match(html, /<h3>Objective<\/h3>/);
  assert.match(html, /<code>return<\/code>/);
  assert.match(html, /<pre class="lesson-code">/);
  assert.match(html, /&lt;unsafe&gt;/);
  assert.doesNotMatch(html, /<script>/);
});

test('lesson sources reject executable URL schemes', () => {
  assert.throws(() => validateLesson({ conceptId: 'c1', title: 'One', body: 'Text', completed: false,
    sources: [{ title: 'Unsafe', url: 'javascript:alert(1)' }] }), /lesson\.sources\[0\]\.url/);
});

test('experiment finding remains explicitly insufficient without delayed human evidence', () => {
  const payload = baseOverview([baseConcept('c1', 'One')], { conceptId: 'c1', action: 'lesson', reason: 'Begin.' });
  payload.experiment = { protocolId: 'pilot-1', protocolVersion: '1', status: 'insufficient_evidence', reason: 'No eligible delayed outcomes.' };
  assert.equal(validateOverview(payload).experiment.status, 'insufficient_evidence');
  payload.experiment.status = 'diagram_wins';
  assert.throws(() => validateOverview(payload), /overview\.experiment\.status/);
  payload.experiment.status = 'insufficient_evidence';
  payload.experiment.protocol = { id: 'pilot-1', version: '1' };
  payload.experiment.arms = { text: { assigned: 1, exposed: 0, eligible: 0, correct: 0, missing: 1 },
    diagram: { assigned: 1, exposed: 0, eligible: 0, correct: 0, missing: 1 } };
  assert.equal(validateOverview(payload).experiment.arms.diagram.eligible, 0);
  delete payload.experiment.arms.diagram.correct;
  assert.throws(() => validateOverview(payload), /overview\.experiment\.arms\.diagram\.correct/);
});

test('attempt context is explicit and cannot turn assistance into independent evidence', () => {
  assert.deepEqual(buildAttemptPayload('draft-1', 14, 0.75, 'some', 'Read a book'), {
    draftId: 'draft-1', activeSeconds: 14, confidence: 0.75,
    outsideStudy: 'some', outsideStudyDetail: 'Read a book',
  });
  assert.equal(buildAttemptPayload('draft-1', 0, null, 'unknown').confidence, null);
  assert.throws(() => buildAttemptPayload('draft-1', 0, 1.2, 'none'), /attempt\.confidence/);
  assert.throws(() => buildAttemptPayload('draft-1', 0, 0.5, 'never'), /attempt\.outsideStudy/);
});

const workspaceView = () => ({
  overview: baseOverview([baseConcept('c1', 'Unique concept title', {
    encounteredFamilyIds: [], reviewSchedule: { status: 'none' },
  }), baseConcept('c2', 'Next concept')], { conceptId: 'c2', action: 'practice', reason: 'Continue.' }),
  conceptId: 'c1', mode: 'recommended', answer: 'yes', result: null, review: null,
  lesson: { title: 'Unique concept title', completed: true, body: 'Worked example.', sources: [] },
  session: { activity: { id: 'a1', familyId: 'f1', type: 'choice',
    evidenceKind: 'recognition', prompt: 'Pick one', choices: ['yes'], hints: [] },
    draft: null, recommendation: { reason: 'Practice.' } },
});

for (const screen of ['lesson', 'practice question', 'saved draft', 'result', 'caught-up', 'due', 'overdue']) {
  test(`workspace markup placement: ${screen}`, () => {
    const view = workspaceView();
    let activity = '<div class="activity-card">';
    if (screen === 'lesson') {
      view.lesson.completed = false;
      activity = '<article class="lesson-body">';
    } else if (screen === 'saved draft') {
      view.session.draft = { id: 'd1', firstAnswer: 'yes', hintLevels: [] };
    } else if (screen === 'result') {
      view.result = { attemptId: 'a1', scoreStatus: 'correct', gradingMethod: 'key',
        assisted: false, nextReason: 'Matched.', developmentOnly: true };
      activity = '<div class="feedback"';
    } else if (screen === 'caught-up') {
      view.session.activity = null;
      activity = '<div class="empty">';
    } else if (screen === 'due' || screen === 'overdue') {
      view.session.activity.heldOut = true;
      view.overview.concepts[0].signals.reviewSchedule = {
        status: screen, dueAt: '2026-01-02T12:00:00Z', reason: 'Check recall.',
      };
    }
    const before = structuredClone(view);
    const html = workspaceMarkup(view);
    assert.deepEqual(view, before, 'markup must not mutate its input');
    const main = html.indexOf(activity);
    const path = html.indexOf('<div class="path-note">');
    const evidence = html.indexOf('<details class="workspace-evidence">');
    assert.ok(main >= 0 && main < path && main < evidence, 'activity must precede path and evidence');
    const panels = html.match(/<details\b[^>]*\bclass="workspace-evidence"[^>]*>/g) ?? [];
    assert.equal(panels.length, 1, 'exactly one evidence panel');
    assert.doesNotMatch(panels[0], /\sopen(?:\s|=|>)/, 'evidence panel must be closed');
    if (screen === 'due' || screen === 'overdue') {
      const timing = html.indexOf('<section class="review-timing"');
      assert.ok(timing >= 0 && timing < evidence, 'review timing must precede evidence');
      assert.match(html, new RegExp(`Delayed review ${screen}`));
      assert.match(html, /Unfamiliar delayed assessment/);
    } else {
      assert.doesNotMatch(html, /class="review-timing"/);
    }
    if (screen === 'lesson') {
      assert.equal(html.split(view.lesson.title).length - 1, 1);
      assert.ok(!html.includes(`<h3>${view.lesson.title}</h3>`));
    }
  });
}
test('workspace wording separates reviewed-key outcomes from candidate-key matches', () => {
  const view = workspaceView();
  view.lesson.completed = false;
  // v2+: `correct` counts reviewed-key outcomes only; draft-key matches are provisional.
  view.overview.experiment = { protocol: { id: 'text-vs-labeled-diagram', version: 'v2' },
    status: 'insufficient_evidence', reason: 'One learner.', analysisUnit: 'independent_learner',
    contentReviewStatus: 'draft',
    arms: {
      text: { assigned: 1, exposed: 1, eligible: 0, correct: 0, missing: 0, independentLearners: 1,
        provisional: 2, candidateKeyMatches: 1 },
      diagram: { assigned: 1, exposed: 1, eligible: 1, correct: 1, missing: 0, independentLearners: 1 },
    } };
  let html = workspaceMarkup(view);
  assert.match(html, /does not count as an independent candidate-key match\./);
  assert.match(html, /Method A · text:<\/strong> 0 correlated concept observations, 0 correct on reviewed keys; 0 missing; 1 independent learner; 2 provisional draft-key checks \(1 candidate match\)/);
  assert.match(html, /Method B · text with diagram:<\/strong> 1 correlated concept observations, 1 correct on reviewed keys;/);
  assert.doesNotMatch(html, /independent correct answer/);
  // v1: `correct` counts every key match, so with draft keys it is a candidate-key match.
  view.overview.experiment = { protocol: { id: 'text-vs-labeled-diagram', version: 'v1' },
    status: 'insufficient_evidence', reason: 'One learner.', contentReviewStatus: 'draft',
    arms: Object.fromEntries(['text', 'diagram'].map((arm, i) => [arm,
      { assigned: 1, exposed: 1, eligible: 2, correct: i + 1, missing: 0 }])) };
  html = workspaceMarkup(view);
  assert.match(html, /Method A · text:<\/strong> 2 eligible delayed answers, 1 candidate-key match;/);
  assert.match(html, /Method B · text with diagram:<\/strong> 2 eligible delayed answers, 2 candidate-key matches;/);
  assert.doesNotMatch(html, /\d correct;/);
});

test('comparison area explains single learner limits when status is insufficient_evidence', () => {
  const view = workspaceView();
  view.lesson.completed = false;
  view.overview.experiment = {
    protocol: { id: 'text-vs-labeled-diagram', version: 'v8', minimumIndependentLearnersPerArm: 20 },
    status: 'insufficient_evidence',
    reason: 'One local learner supplies at most one independent learner unit per arm; the fixed minimum of 20 independent learners per arm is unreachable in this local analysis.',
    analysisUnit: 'independent_learner',
    contentReviewStatus: 'draft',
    arms: {
      text: { assigned: 1, exposed: 1, eligible: 0, correct: 0, missing: 0, independentLearners: 1 },
      diagram: { assigned: 1, exposed: 1, eligible: 0, correct: 0, missing: 0, independentLearners: 1 },
    },
  };
  const html = workspaceMarkup(view);
  const comparisonArea = html.slice(html.indexOf('<section class="experiment-summary" aria-label="Instructional comparison findings">'));
  assert.match(comparisonArea, /This comparison needs at least 20 learners in each method before it can show a result\. One person(?:'|&#39;)s answers can(?:'|&#39;)t show which method works better\./);
  assert.doesNotMatch(comparisonArea, /mastery/i);
  // v1 counts delayed outcomes, not learners: no learner explanation there.
  view.overview.experiment = { protocol: { id: 'text-vs-labeled-diagram', version: 'v1', minimumPerArm: 30 },
    status: 'insufficient_evidence', reason: 'Too few outcomes.', contentReviewStatus: 'draft',
    arms: Object.fromEntries(['text', 'diagram'].map(arm => [arm,
      { assigned: 1, exposed: 1, eligible: 0, correct: 0, missing: 0 }])) };
  const legacy = workspaceMarkup(view);
  assert.doesNotMatch(legacy, /learners in each method/);
  assert.match(legacy, /requires 30 eligible delayed outcomes per method/);
});

test('review timing markup renders overdue status and returns empty string for none', () => {
  const fixedNow = new Date('2026-01-03T12:00:00Z');
  const overdueSchedule = {
    dueAt: '2026-01-01T12:00:00Z',
    status: 'overdue',
    reason: 'Review window passed.',
  };
  const overdueMarkup = reviewTimingMarkup(overdueSchedule, null, fixedNow);
  assert.match(overdueMarkup, /<section class="review-timing"/);
  assert.doesNotMatch(overdueMarkup, /<[a-z][^>]*\shidden\b/i, 'No element in the review timing markup may have a hidden attribute');
  assert.match(overdueMarkup, /Review window passed\./);
  const overdueLabel = overdueMarkup.match(/<strong[^>]*>(.*?)<\/strong>/)?.[1];
  assert.equal(overdueLabel, 'Delayed review overdue');
  const overdueParagraphs = [...overdueMarkup.matchAll(/<p[^>]*>([\s\S]*?)<\/p>/g)].map(m => m[1]);
  const overdueReasonParagraph = overdueParagraphs.find(p => !p.includes('<time'));
  assert.equal(overdueReasonParagraph, 'Review window passed.');
  assert.doesNotMatch(overdueReasonParagraph ?? '', /Delayed review overdue|Delayed review due/);

  const dueSchedule = {
    dueAt: '2026-01-01T12:00:00Z',
    status: 'due',
    reason: 'Review window open.',
  };
  const dueMarkup = reviewTimingMarkup(dueSchedule, null, fixedNow);
  assert.match(dueMarkup, /<section class="review-timing"/);
  assert.doesNotMatch(dueMarkup, /<[a-z][^>]*\shidden\b/i, 'No element in the review timing markup may have a hidden attribute');
  assert.match(dueMarkup, /Review window open\./);
  const dueLabel = dueMarkup.match(/<strong[^>]*>(.*?)<\/strong>/)?.[1];
  assert.equal(dueLabel, 'Delayed review due');
  const dueParagraphs = [...dueMarkup.matchAll(/<p[^>]*>([\s\S]*?)<\/p>/g)].map(m => m[1]);
  const dueReasonParagraph = dueParagraphs.find(p => !p.includes('<time'));
  assert.equal(dueReasonParagraph, 'Review window open.');
  assert.doesNotMatch(dueReasonParagraph ?? '', /Delayed review overdue|Delayed review due/);

  const noneSchedule = {
    dueAt: null,
    status: 'none',
    reason: 'No review scheduled.',
  };
  assert.equal(reviewTimingMarkup(noneSchedule, null, fixedNow), '');
  assert.equal(reviewTimingMarkup({ status: 'none', dueAt: '2026-01-01T12:00:00Z' }, null, fixedNow), '');
  assert.equal(reviewTimingMarkup(null, null, fixedNow), '');
});

test('quiet view in style.css hides workspace evidence without hiding review timing notice or why', () => {
  const cssPath = fileURLToPath(new URL('../foreman_web/style.css', import.meta.url));
  const css = readFileSync(cssPath, 'utf8');
  const cleanCss = css.replace(/\/\*[\s\S]*?\*\//g, '');

  function parseRules(str) {
    const rules = [];
    let i = 0;
    while (i < str.length) {
      const openBrace = str.indexOf('{', i);
      if (openBrace === -1) break;
      const selector = str.slice(i, openBrace).trim();
      let depth = 1;
      let j = openBrace + 1;
      while (j < str.length && depth > 0) {
        if (str[j] === '{') depth++;
        else if (str[j] === '}') depth--;
        j++;
      }
      const body = str.slice(openBrace + 1, j - 1);
      if (selector.startsWith('@media') || selector.startsWith('@supports')) {
        rules.push(...parseRules(body));
      } else {
        rules.push({ selector, body });
      }
      i = j;
    }
    return rules;
  }

  const allRules = parseRules(cleanCss);
  const quietRules = allRules.filter(rule => /(?<![\w-])\.quiet(?![\w-])/.test(rule.selector));
  assert.ok(quietRules.length > 0, 'style.css should contain .quiet rules');

  function parseDeclarations(body) {
    const decls = [];
    const parts = body.split(';');
    for (const part of parts) {
      const colon = part.indexOf(':');
      if (colon === -1) continue;
      const prop = part.slice(0, colon).trim().toLowerCase();
      let val = part.slice(colon + 1).trim().toLowerCase();
      val = val.replace(/\s*!important\s*$/i, '').trim();
      decls.push({ prop, val });
    }
    return decls;
  }

  const isHiding = (body, selector) => {
    if (/\[\s*hidden\s*\]/i.test(body) || /\[\s*hidden\s*\]/i.test(selector)) return true;
    const decls = parseDeclarations(body);
    for (const { prop, val } of decls) {
      if (prop === 'display' && val === 'none') return true;
      if (prop === 'visibility' && val === 'hidden') return true;
      if (prop === 'content-visibility' && val === 'hidden') return true;
      if (prop === 'opacity') {
        const num = parseFloat(val);
        if (!isNaN(num) && num === 0) return true;
      }
    }
    return false;
  };

  function splitSelectorList(selectorStr) {
    const list = [];
    let current = '';
    let parenDepth = 0;
    let bracketDepth = 0;
    for (let i = 0; i < selectorStr.length; i++) {
      const c = selectorStr[i];
      if (c === '(') parenDepth++;
      else if (c === ')') parenDepth--;
      else if (c === '[') bracketDepth++;
      else if (c === ']') bracketDepth--;
      else if (c === ',' && parenDepth === 0 && bracketDepth === 0) {
        list.push(current.trim());
        current = '';
        continue;
      }
      current += c;
    }
    if (current.trim()) list.push(current.trim());
    return list;
  }

  function expandFunctionalPseudo(selector) {
    let changed = true;
    let currentSelectors = [selector];
    while (changed) {
      changed = false;
      const nextSelectors = [];
      for (const sel of currentSelectors) {
        const match = sel.match(/:(?:is|where)\(([^()]+)\)/);
        if (match) {
          changed = true;
          const prefix = sel.slice(0, match.index);
          const suffix = sel.slice(match.index + match[0].length);
          const options = splitSelectorList(match[1]);
          for (const opt of options) {
            nextSelectors.push(prefix + opt.trim() + suffix);
          }
        } else {
          nextSelectors.push(sel);
        }
      }
      currentSelectors = nextSelectors;
    }
    return [...new Set(currentSelectors)];
  }

  const allHidingSelectors = [];
  for (const rule of allRules) {
    if (isHiding(rule.body, rule.selector)) {
      const rawSelectors = splitSelectorList(rule.selector);
      for (const rawSel of rawSelectors) {
        const expanded = expandFunctionalPseudo(rawSel);
        for (const sel of expanded) {
          allHidingSelectors.push(sel.trim());
        }
      }
    }
  }

  function selectorTargets(selector, item) {
    const segments = selector.trim().split(/[\s>+~]+/);
    const subject = segments[segments.length - 1];
    if (/::[a-zA-Z-]+$/.test(subject) || /:(?:before|after|first-line|first-letter|placeholder|backdrop|selection)(?![a-zA-Z-])/i.test(subject)) {
      return false;
    }

    const matches = (target) => {
      if (item.startsWith('.')) {
        const cls = item.slice(1);
        return new RegExp('\\.' + cls + '(?![\\w-])').test(target);
      }
      if (item.startsWith('#')) {
        const id = item.slice(1);
        return new RegExp('#' + id + '(?![\\w-])').test(target);
      }
      return new RegExp('(?<![\\w.-])' + item + '(?![\\w-])').test(target);
    };

    if (matches(subject)) return true;
    if (item === 'body' && /(?<![\\w-])\.quiet(?![\\w-])/.test(subject)) return true;
    if (subject === '*' && segments.some(seg => matches(seg) || (item === 'body' && /(?<![\\w-])\.quiet(?![\\w-])/.test(seg)))) return true;

    return false;
  }

  assert.ok(
    allHidingSelectors.some(selector => /(?<![\\w-])\.quiet(?![\\w-])/.test(selector) && selectorTargets(selector, '.workspace-evidence')),
    'Quiet view must hide .workspace-evidence',
  );

  for (const forbidden of ['.review-timing', '.notice', '.why', '.workspace', '#content', '.layout', '.shell', 'main', 'body']) {
    const offending = allHidingSelectors.filter(selector => !selector.includes('.consent-pending') && selectorTargets(selector, forbidden));
    assert.deepEqual(
      offending,
      [],
      `Quiet view must not have a rule hiding ${forbidden}`,
    );
  }
});


test('consent replaces workspace and includes every required statement without preselected inputs', () => {
  const html = consentMarkup();
  for (const statement of ['answers, hint use, confidence, outside-study notes and timing',
    'on this computer only', 'not sent to any outside service, including AI models',
    'draft answer keys', 'provisional', 'not a grade or a judgment of what you know',
    "One person's answers are not enough evidence", 'teaching method works better',
    'stop at any time', 'ask for your data to be deleted']) assert.ok(html.includes(statement), statement);
  assert.doesNotMatch(html, /mastery|<input|checked/i);
  assert.equal((html.match(/<button/g) || []).length, 1);
  assert.equal(workspaceMarkup({consentRequired: true}), html);
});

test('boot stops at consent before loading a lesson or workspace', async () => {
  const source = readFileSync(new URL('../foreman_web/app.js', import.meta.url), 'utf8');
  const boot = source.slice(source.indexOf('async function boot()'), source.indexOf('boot().catch(showError)'));
  const calls = [];
  const context = { state: {}, api: async () => ({consentRequired: true}),
    renderConsent: () => calls.push('consent'), renderDeleted: () => calls.push('deleted'),
    validateOverview: () => { throw new Error('workspace validated before consent'); },
    refresh: async () => calls.push('workspace'),
    document: {body: {classList: {remove: () => calls.push('unhidden')}}} };
  runInNewContext(boot + ';this.boot = boot;', context);
  await context.boot();
  assert.deepEqual(calls, ['consent']);
});
