import assert from 'node:assert/strict';
import { spawnSync } from 'node:child_process';
import { test } from 'node:test';
import { fileURLToPath } from 'node:url';

import {
  evidenceMarkup,
  normalizeEvidence,
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
  assert.match(html, /Inspect learning evidence/);
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

test('attempt history preserves assistance and escapes the saved answer', () => {
  const attempt = { id: 'a1', activityId: 'item-1', contentVersion: 'v3',
    evidenceKind: 'recognition', occurredAt: '2026-01-01T12:00:00Z',
    firstAnswer: '<script>alert(1)</script>', scoreStatus: 'incorrect',
    gradingMethod: 'development_fixture_exact_key', hintLevel: 'nudge', assisted: true };
  const payload = baseOverview([baseConcept('c1', 'One', { recordedAttempts: [attempt] })],
    { conceptId: 'c1', action: 'practice', reason: 'Try again.' });
  const overview = validateOverview(payload);
  const html = evidenceMarkup(overview.concepts[0].signals.evidence,
    overview.concepts[0].signals.recordedAttempts);
  assert.match(html, /item-1.*assisted/);
  assert.match(html, /&lt;script&gt;/);
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
        preview.complete_lesson(cid)
        lesson = preview.lesson(cid)
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
  assert.throws(
    () => validateAttemptResult({ attemptId: 'a', scoreStatus: 'unknown', gradingMethod: 'key',
      developmentOnly: true, assisted: false, nextReason: 'Unknown.' }),
    /attempt\.scoreStatus/,
  );
  assert.throws(() => validateAttemptResult({ attemptId: 'a', scoreStatus: 'correct',
    gradingMethod: 'key', assisted: false, nextReason: 'Matched.' }),
  /attempt\.developmentOnly/);
});
