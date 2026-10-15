import assert from 'node:assert/strict';
import { spawnSync } from 'node:child_process';
import { test } from 'node:test';

import {
  evidenceMarkup,
  normalizeEvidence,
  validateAttemptResult,
  validateLesson,
  validateOverview,
  validateSession,
} from '../foreman_web/app.js';

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

test('old profile signals without evidence normalize instead of throwing on markup', () => {
  const payload = baseOverview(
    [baseConcept('c1', 'One', { evidence: undefined })],
    { conceptId: 'c1', action: 'lesson', reason: 'Begin.' },
  );
  const overview = validateOverview(payload);
  assert.equal(overview.concepts[0].signals.evidence.byKind.recognition, undefined);
  const html = evidenceMarkup(overview.concepts[0].signals.evidence);
  assert.match(html, /Inspect learning evidence/);
  assert.doesNotThrow(() => Object.entries(overview.concepts[0].signals.evidence.byKind));
});

test('null evidence.byKind is rejected with a contract path', () => {
  assert.throws(
    () => normalizeEvidence({ byKind: null }, 'signals.evidence'),
    /signals\.evidence\.byKind: expected an object/,
  );
});

test('session draft missing hintLevels defaults to empty array for older payloads', () => {
  const activity = {
    id: 'a1',
    type: 'choice',
    evidenceKind: 'recognition',
    prompt: 'Pick one',
    choices: ['yes'],
    hints: [{ level: 'nudge' }],
  };
  const session = validateSession({
    activity,
    draft: { id: 'd1', firstAnswer: 'yes' },
    recommendation: { reason: 'Practice' },
  });
  assert.deepEqual(session.draft.hintLevels, []);
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
            preview.submit({"draftId": draft_id, "activeSeconds": 1})
    print(json.dumps({
        "overview": overview,
        "concepts": {cid: {
            "lesson": preview.lesson(cid),
            "session": preview.session(cid),
        } for cid in order},
    }))
finally:
    preview.store.close()
`;
  const result = spawnSync('python', ['-c', script], {
    env: { ...process.env, PYTHONPATH: 'src' },
    encoding: 'utf8',
  });
  assert.equal(result.status, 0, result.stderr || result.stdout);
  const payload = JSON.parse(result.stdout);
  validateOverview(payload.overview);
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
    () => validateAttemptResult({ attemptId: 'a', scoreStatus: 'correct' }),
    /attempt\.nextReason/,
  );
});
