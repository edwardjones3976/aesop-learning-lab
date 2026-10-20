import assert from 'node:assert/strict';
import { spawnSync } from 'node:child_process';
import { readFileSync } from 'node:fs';
import { test } from 'node:test';
import { fileURLToPath } from 'node:url';

import {
  buildAttemptPayload,
  comparisonHintBlockReason,
  evidenceMarkup,
  evidenceSnapshot,
  evidenceSummaryMarkup,
  lessonMarkup,
  normalizeEvidence,
  personalComparisonMarkup,
  reviewTimingMarkup,
  solutionMarkup,
  validateAttemptResult,
  validateLesson,
  validateOverview,
  validateSession,
} from '../foreman_web/app.js';

const repoRoot = fileURLToPath(new URL('../', import.meta.url));
const sourcePath = fileURLToPath(new URL('../src/', import.meta.url));

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
  assert.match(html, /See what your answers show/);
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
  assert.match(html, /Unassisted draft-key matches/);
  assert.match(html, /question groups you already studied/);
  assert.match(html, /Assisted draft-key matches/);
  assert.match(html, /not extra attempts/);
  assert.match(html, /not verified mastery/);
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
  assert.match(before, /A later check is coming/);
  assert.match(before, /delayed review/);
  const due = reviewTimingMarkup(schedule, null, new Date('2026-01-03T12:00:00Z'));
  assert.match(due, /A later check is ready/);
  assert.match(due, /&lt;review&gt;/);
  assert.doesNotMatch(due, /<review>/);
  const legacy = reviewTimingMarkup(null, { nextCheckAt: null, activity: { heldOut: true },
    recommendation: { reason: 'Held-out check.' } }, new Date('2026-01-03T12:00:00Z'));
  assert.match(legacy, /A later check is ready/);
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
  assert.match(html, /Planned wait: 7 days/);
  assert.match(html, /Actual wait: 9\.25 days/);
  assert.match(html, /Due <time/);
  assert.match(html, /Independent: no hint was used/);
  assert.match(html, /Familiarity not checked/);
  evidence.delayedChecks[0].actualDelayDays = -1;
  assert.throws(() => normalizeEvidence(evidence), /actualDelayDays/);
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
  assert.match(html, /Confidence before any hint: 50%/);
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
  assert.match(html, /<details class="solution-panel"><summary>Show the draft answer and why/);
  assert.match(html, /draft candidate key/);
  assert.match(html, /not verified mastery/);
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

test('main page explains draft keys, later checks, and display limits', () => {
  const html = readFileSync(fileURLToPath(new URL('../foreman_web/index.html', import.meta.url)), 'utf8');
  assert.match(html, /not verified mastery/);
  assert.match(html, /later check/);
  assert.match(html, /unassisted/);
  assert.match(html, /assisted/);
  assert.match(html, /not an independent answer/);
  assert.match(html, /id="content"/);
  assert.match(html, /id="personal-comparison"/);
  assert.match(html, /id="focus"/);
  assert.match(html, /id="minutes"/);
});

test('comparison copy keeps limits distinct and escapes unit names', () => {
  const protocol = { id: 'pilot', version: 'v2', contentVersion: 'v9', analysisUnit: 'unit', contentReviewStatus: 'draft' };
  const units = [
    { id: 'u1', name: '<Late>', condition: 'diagram', practiceAnswered: true, practiceAssisted: false,
      practiceCandidateMatch: true, classification: 'late', delayedAnswered: true, delayedCandidateMatch: false, actualDelayDays: 20 },
    { id: 'u2', name: 'Scope', condition: 'text', practiceAnswered: false, classification: 'missing',
      delayedAnswered: false, actualDelayDays: null },
    { id: 'u3', name: 'Bind', condition: 'text', practiceAnswered: true, practiceAssisted: true,
      practiceCandidateMatch: false, classification: 'contaminated', delayedAnswered: true, delayedCandidateMatch: false, actualDelayDays: 8 },
    { id: 'u4', name: 'Return', condition: 'diagram', practiceAnswered: true, practiceAssisted: false,
      practiceCandidateMatch: true, classification: 'provisional', delayedAnswered: true, delayedCandidateMatch: true, actualDelayDays: 9 },
  ];
  const html = personalComparisonMarkup({
    status: 'insufficient_evidence', reason: 'One learner is not enough.', uncertainty: 'No cause is shown.',
    enrolled: true, protocol, units,
    arms: { text: { assigned: 2, eligible: 0, provisional: 1, missing: 1, late: 0, contaminated: 1, outsideStudyUnknown: 0 },
      diagram: { assigned: 2, eligible: 0, provisional: 0, missing: 0, late: 1, contaminated: 0, outsideStudyUnknown: 0 } },
    descriptive: { text: { observed: 1, candidateMatches: 0, eligibleCandidateMatches: 0 },
      diagram: { observed: 1, candidateMatches: 1, eligibleCandidateMatches: 0 } },
    next: { stage: 'waiting' },
  });
  assert.match(html, /not verified mastery/);
  assert.match(html, /does not show that one method caused better learning/);
  assert.match(html, /Missing means no answer/);
  assert.match(html, /Late means after the window/);
  assert.match(html, /Contaminated means/);
  assert.match(html, /Provisional means a draft key was used/);
  assert.match(html, /Outside study unknown is a separate label/);
  assert.match(html, /reviewed key/);
  assert.match(html, /Unassisted\. No hint was used/);
  assert.match(html, /Assisted\. A hint was used/);
  assert.match(html, /&lt;Late&gt;/);
  assert.doesNotMatch(html, /<Late>/);
  assert.match(html, /id="comparison-refresh"/);
  assert.match(html, /unfamiliar question group/);
  assert.equal(comparisonHintBlockReason('  1, 2'), 
    'You have typed an answer. Submit it as your unassisted first answer, or clear the field before you open a hint. After a hint, a later answer is assisted practice.');
  assert.equal(comparisonHintBlockReason('   '), null);
});

test('a long-open later question is labeled contaminated without changing its controls', () => {
  const html = personalComparisonMarkup({
    status: 'insufficient_evidence', reason: 'Waiting.', uncertainty: 'No cause is shown.',
    enrolled: true,
    protocol: { id: 'pilot', version: 'v2', contentVersion: 'v9', analysisUnit: 'unit', contentReviewStatus: 'draft' },
    units: [{ id: 'u1', name: 'Scope', condition: 'text', practiceAnswered: true, practiceAssisted: false,
      practiceCandidateMatch: true, classification: 'missing', delayedAnswered: false, actualDelayDays: null,
      delayedFirstViewedAt: '2026-01-01T00:00:00Z' }],
    next: { stage: 'delayed', unitId: 'u1' },
    question: { phase: 'delayed', prompt: 'What returns?', code: 'return 1', familyId: 'fam-1', hintAvailable: false },
  }, '', new Date('2026-01-01T01:00:00Z'), false);
  assert.match(html, /classified contaminated/);
  assert.match(html, /cannot count in the main comparison/);
  assert.match(html, /id="comparison-answer"/);
  assert.match(html, /id="comparison-answer-submit"/);
  assert.match(html, /Unfamiliar later check|Later check already opened/);
});

test('comparison suggestions explain an override and keep its controls', () => {
  const html = personalComparisonMarkup({
    status: 'descriptive_only', reason: 'Description only.', uncertainty: 'One person.',
    enrolled: true,
    protocol: { id: 'pilot', version: 'v2', contentVersion: 'v9', analysisUnit: 'independent_learner', contentReviewStatus: 'draft' },
    units: [],
    recommendation: { stage: 'delayed', unitId: 'u2', reason: 'Return for the check.', aim: 'See what remains.',
      evidenceUnitIds: ['u1'], uncertainty: 'This does not pick a method.', policyVersion: '1',
      alternative: { stage: 'practice', unitId: 'u1' } },
  });
  assert.match(html, /id="comparison-override"/);
  assert.match(html, /id="comparison-override-note"/);
  assert.match(html, /An override is optional/);
  assert.match(html, /does not show a cause/);
  assert.match(html, /Later check/);
  assert.doesNotMatch(html, /id="comparison-enroll"/);
});
