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

function requireTimestamp(value, path) {
  requireString(value, path);
  if (Number.isNaN(Date.parse(value))) throw contractError(path, 'expected a valid timestamp.');
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
    if (row.dueAt != null) requireTimestamp(row.dueAt, `${path}.delayedChecks[${index}].dueAt`);
    if (row.actualDelayDays != null && (typeof row.actualDelayDays !== 'number' || !Number.isFinite(row.actualDelayDays) || row.actualDelayDays < 0)) {
      throw contractError(`${path}.delayedChecks[${index}].actualDelayDays`, 'expected a non-negative number.');
    }
  });
  const contentQualityCandidates = requireArray(raw.contentQualityCandidates ?? [], `${path}.contentQualityCandidates`);
  contentQualityCandidates.forEach((candidate, index) => {
    const row = requireRecord(candidate, `${path}.contentQualityCandidates[${index}]`);
    requireString(row.activityId, `${path}.contentQualityCandidates[${index}].activityId`);
    requireString(row.reason, `${path}.contentQualityCandidates[${index}].reason`);
    requireArray(row.attemptIds, `${path}.contentQualityCandidates[${index}].attemptIds`).forEach((id, n) =>
      requireString(id, `${path}.contentQualityCandidates[${index}].attemptIds[${n}]`));
  });
  return {
    byKind,
    delayedChecks,
    delayedOutcomeByDay,
    confidenceOutcomePairs: requireNumber(raw.confidenceOutcomePairs, `${path}.confidenceOutcomePairs`),
    contentQualityCandidates,
  };
}

function validateSignals(signals, path) {
  const raw = requireRecord(signals, path);
  const reviewSchedule = raw.reviewSchedule == null ? null : requireRecord(raw.reviewSchedule, `${path}.reviewSchedule`);
  if (reviewSchedule) {
    if (!['upcoming', 'due', 'overdue', 'none'].includes(reviewSchedule.status)) {
      throw contractError(`${path}.reviewSchedule.status`, 'expected upcoming, due, overdue, or none.');
    }
    if (reviewSchedule.dueAt != null) requireTimestamp(reviewSchedule.dueAt, `${path}.reviewSchedule.dueAt`);
    requireString(reviewSchedule.reason, `${path}.reviewSchedule.reason`);
  }
  const openDraft = raw.openDraft == null ? null : requireRecord(raw.openDraft, `${path}.openDraft`);
  if (openDraft) {
    requireString(openDraft.activityId, `${path}.openDraft.activityId`);
    requireTimestamp(openDraft.savedAt, `${path}.openDraft.savedAt`);
    if (!['none', 'nudge', 'targeted', 'worked_solution'].includes(openDraft.hintLevel)) {
      throw contractError(`${path}.openDraft.hintLevel`, 'hint level is not recognized.');
    }
  }
  const recordedAttempts = requireArray(raw.recordedAttempts, `${path}.recordedAttempts`);
  const encounteredFamilyIds = requireArray(raw.encounteredFamilyIds ?? [], `${path}.encounteredFamilyIds`);
  encounteredFamilyIds.forEach((family, index) => requireString(family, `${path}.encounteredFamilyIds[${index}]`));
  recordedAttempts.forEach((attempt, index) => {
    const item = requireRecord(attempt, `${path}.recordedAttempts[${index}]`);
    for (const field of ['id', 'activityId', 'contentVersion', 'evidenceKind', 'occurredAt',
      'gradingMethod', 'hintLevel', 'scoreStatus']) {
      requireString(item[field], `${path}.recordedAttempts[${index}].${field}`);
    }
    if (item.familyId != null) requireString(item.familyId, `${path}.recordedAttempts[${index}].familyId`);
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
    freshUnassistedCorrect: raw.freshUnassistedCorrect == null ? null : requireNumber(raw.freshUnassistedCorrect, `${path}.freshUnassistedCorrect`),
    hintAssisted: requireNumber(raw.hintAssisted, `${path}.hintAssisted`),
    needsReview: requireNumber(raw.needsReview, `${path}.needsReview`),
    recentOutcome: raw.recentOutcome == null ? null : requireString(raw.recentOutcome, `${path}.recentOutcome`),
    recordedAttempts,
    encounteredFamilyIds,
    evidence: normalizeEvidence(raw.evidence, `${path}.evidence`),
    reviewSchedule,
    openDraft,
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
        for (const count of ['provisional', 'candidateKeyMatches', 'late', 'early', 'contaminated', 'ungraded', 'invalid', 'exposureIncomparable']) {
          if (row[count] != null) requireNumber(row[count], `overview.experiment.arms.${arm}.${count}`);
        }
        if (experiment.analysisUnit === 'independent_learner') {
          requireNumber(row.independentLearners, `overview.experiment.arms.${arm}.independentLearners`);
        }
      }
    }
    if (experiment.analysisUnit != null && experiment.analysisUnit !== 'independent_learner') {
      throw contractError('overview.experiment.analysisUnit', 'unsupported analysis unit.');
    }
    if (!['insufficient_evidence', 'descriptive_only'].includes(requireString(experiment.status, 'overview.experiment.status'))) {
      throw contractError('overview.experiment.status', 'unsupported finding status.');
    }
    requireString(experiment.reason, 'overview.experiment.reason');
    if (experiment.contentReviewStatus != null && !['draft', 'reviewed'].includes(experiment.contentReviewStatus)) {
      throw contractError('overview.experiment.contentReviewStatus', 'expected draft or reviewed.');
    }
    if (protocol?.exposureDurationControlled != null) requireBoolean(protocol.exposureDurationControlled, 'overview.experiment.protocol.exposureDurationControlled');
    if (protocol?.minimumPerArm != null) requireNumber(protocol.minimumPerArm, 'overview.experiment.protocol.minimumPerArm');
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
    if (method.studyTargetMinutes != null && (!Number.isSafeInteger(method.studyTargetMinutes) || method.studyTargetMinutes < 1)) {
      throw contractError('lesson.method.studyTargetMinutes', 'expected a positive whole number.');
    }
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
  for (const hidden of ['explanation', 'solution', 'answerKey', 'correctAnswer', 'modelAnswer']) {
    if (Object.hasOwn(row, hidden)) {
      throw contractError(`${path}.${hidden}`, 'must not be sent before the answer is scored.');
    }
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
  if (session.nextCheckAt != null) requireTimestamp(session.nextCheckAt, 'session.nextCheckAt');
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
  if (activity) {
    const revealed = new Set(draft?.hintLevels ?? []);
    for (const hint of activity.hints) {
      if (!revealed.has(hint.level) && hint.text != null) {
        throw contractError(`session.activity.hints.${hint.level}.text`, 'unrequested hint text must not be sent.');
      }
    }
  }
  const recommendation = session.recommendation == null ? null : requireRecord(session.recommendation, 'session.recommendation');
  if (activity) requireString(recommendation?.reason, 'session.recommendation.reason');
  if (recommendation?.aim != null) requireString(recommendation.aim, 'session.recommendation.aim');
  if (recommendation?.evidenceGap != null) requireString(recommendation.evidenceGap, 'session.recommendation.evidenceGap');
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
  if (result.solution != null) {
    const solution = requireRecord(result.solution, 'attempt.solution');
    if (status === 'ungraded') throw contractError('attempt.solution', 'ungraded answers cannot have a scored solution.');
    if (solution.kind !== 'candidate_key') throw contractError('attempt.solution.kind', 'expected a candidate key.');
    requireString(solution.answer, 'attempt.solution.answer');
    requireString(solution.reasoning, 'attempt.solution.reasoning');
    if (solution.misconception != null) requireString(solution.misconception, 'attempt.solution.misconception');
  }
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

export function solutionMarkup(result) {
  const validated = validateAttemptResult(result);
  if (!validated.solution) return '';
  const esc = value => String(value ?? '').replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
  return `<details class="solution-panel"><summary>Reveal candidate answer and reasoning</summary><p class="muted">This is a draft candidate key shown after your first answer was saved and scored. It is not a mastery judgment.</p><p><strong>Candidate answer</strong></p><pre class="code">${esc(validated.solution.answer)}</pre><p><strong>Reasoning:</strong> ${esc(validated.solution.reasoning)}</p>${validated.solution.misconception ? `<p><strong>Common misconception:</strong> ${esc(validated.solution.misconception)}</p>` : ''}</details>`;
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
  const delayed = normalized.delayedChecks.length ? normalized.delayedChecks.map(check => `<li>Target delay ${esc(check.checkDelayDays)} day${check.checkDelayDays === 1 ? '' : 's'}${check.actualDelayDays != null ? ` · Actual delay ${esc(Number(check.actualDelayDays.toFixed(2)))} days` : ''}${check.dueAt ? ` · Due <time datetime="${esc(check.dueAt)}">${esc(new Date(check.dueAt).toLocaleString())}</time>` : ''} · ${esc(check.evidenceKind)} · ${esc(check.scoreStatus)} · ${check.assisted ? 'assisted' : 'independent'} · family familiarity ${esc(String(check.familiarityStatus ?? 'not_verified').replace('_', ' '))} · answered ${esc(new Date(check.occurredAt).toLocaleString())}</li>`).join('') : '<li>Insufficient evidence: no delayed held-out answer yet.</li>';
  const intervalStatus = Object.entries(normalized.delayedOutcomeByDay).map(([day, status]) => `<li>Day ${esc(day)}: ${esc(status.replace('_', ' '))}</li>`).join('');
  const history = recordedAttempts.length ? recordedAttempts.map(attempt => `<li><details><summary>${esc(attempt.activityId)} · ${esc(attempt.evidenceKind)} · ${esc(attempt.scoreStatus)} · ${attempt.assisted ? 'assisted' : 'independent'} · ${esc(new Date(attempt.occurredAt).toLocaleString())}</summary><p>Content ${esc(attempt.contentVersion)} · Hint: ${esc(attempt.hintLevel.replace('_', ' '))} · Method: ${esc(attempt.gradingMethod)}</p><p>Pre-hint confidence: ${attempt.confidence == null ? 'not provided' : `${Math.round(attempt.confidence * 100)}%`} · Outside study: ${esc(attempt.outsideStudy ?? 'not recorded')}</p><pre class="code">${esc(attempt.firstAnswer)}</pre></details></li>`).join('') : '<li>No attempts recorded yet.</li>';
  const candidates = normalized.contentQualityCandidates.length ? normalized.contentQualityCandidates.map(row => `<li>${esc(row.activityId)}: ${esc(row.reason)} (${row.attemptIds.length} recorded attempts). Requires content review; repeated errors alone do not prove an item defect.</li>`).join('') : '<li>No content review candidates recorded.</li>';
  return `<details class="evidence-panel"><summary>Inspect learning evidence</summary><p class="muted">Observed answers by kind. Unassisted counts may include repeated or studied families; candidate-key matches are development feedback, not mastery.</p><div class="table-scroll"><table><thead><tr><th scope="col">Kind</th><th scope="col">Unassisted matches</th><th scope="col">Assisted matches</th><th scope="col">Incorrect</th><th scope="col">Ungraded</th></tr></thead><tbody>${rows}</tbody></table></div><p><strong>Delayed check status</strong></p><ul>${intervalStatus || '<li>Insufficient evidence: no delayed held-out answer yet.</li>'}</ul><p><strong>Delayed answers</strong></p><ul>${delayed}</ul><p><strong>Content review candidates</strong></p><ul>${candidates}</ul><p><strong>Attempt history</strong></p><ul>${history}</ul><p class="muted">Unassisted scored answers with confidence recorded: ${normalized.confidenceOutcomePairs}. No calibrated estimate is available.</p></details>`;
}

export function evidenceSnapshot(evidence) {
  const normalized = normalizeEvidence(evidence, 'signals.evidence');
  const counts = Object.values(normalized.byKind);
  return {
    independent: counts.reduce((sum, row) => sum + row.unassistedCorrect, 0),
    assisted: counts.reduce((sum, row) => sum + row.assistedCorrect, 0),
    incorrect: counts.reduce((sum, row) => sum + row.incorrect, 0),
    ungraded: counts.reduce((sum, row) => sum + row.ungraded, 0),
    missingKinds: counts.filter(row => row.unassistedCorrect + row.assistedCorrect + row.incorrect + row.ungraded === 0).length,
    delayedIndependent: normalized.delayedChecks.filter(row => !row.assisted).length,
    delayedMissing: Object.values(normalized.delayedOutcomeByDay).filter(status => status === 'insufficient_evidence').length,
  };
}

export function evidenceSummaryMarkup(evidence) {
  const counts = evidenceSnapshot(evidence);
  return `<section class="evidence-summary" aria-label="Observed learning evidence"><h3>What has been observed</h3><div class="evidence-summary-grid"><p><strong>${counts.independent}</strong>Unassisted candidate matches</p><p><strong>${counts.assisted}</strong>Assisted candidate matches</p><p><strong>${counts.delayedIndependent}</strong>Unassisted delayed answers</p><p><strong>${counts.missingKinds}</strong>Evidence categories without an answer</p></div><p class="muted">${counts.incorrect} incorrect · ${counts.ungraded} ungraded · ${counts.delayedMissing} delayed intervals without an observed answer. Unassisted counts may include repeated families. Delayed answers are a subset of the categories above, not extra attempts. Candidate-key matches do not establish mastery.</p></section>`;
}

export function reviewTimingMarkup(schedule, session = null, now = new Date()) {
  const esc = value => String(value ?? '').replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
  const dueAt = schedule?.dueAt ?? session?.nextCheckAt ?? null;
  let status = schedule?.status ?? (session?.activity?.heldOut ? 'due' : dueAt ? 'upcoming' : 'none');
  if (dueAt && status === 'upcoming' && Date.parse(dueAt) <= now.getTime()) status = 'due';
  const label = {upcoming:'Upcoming delayed review', due:'Delayed review due', overdue:'Delayed review overdue', none:'No delayed review scheduled'}[status];
  const reason = schedule?.reason ?? session?.recommendation?.reason ?? session?.reason ?? 'A review time appears after sufficient practice evidence.';
  return `<section class="review-timing" role="status" aria-label="Review timing"><strong>${label}</strong>${dueAt ? `<p>Review time: <time datetime="${esc(dueAt)}">${esc(new Date(dueAt).toLocaleString())}</time></p>` : ''}<p>${esc(reason)}</p></section>`;
}

function comparisonSolutionStatus(unit, version = 'v2') {
  if (version === 'v1') return 'Not tracked in v1';
  const phases = [];
  if (unit.practiceSolutionRevealedAt) phases.push('Practice');
  if (unit.delayedSolutionRevealedAt) phases.push('Delayed');
  return phases.join(' · ') || 'Not recorded';
}

export function personalComparisonMarkup(report, openedHint = '', now = new Date(), justOpenedDelayed = false) {
  const h = value => String(value ?? '').replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
  if (!report || typeof report !== 'object' || !report.protocol || !Array.isArray(report.units)) {
    throw new Error('The personal comparison report is incomplete.');
  }
  const protocol = report.protocol;
  const intro = `<div class="section-kicker">PERSONAL COMPARISON · DRAFT</div><h2>Compare two ways to study</h2>
    <p class="lede">Study worked Python examples in text or with a labeled diagram, solve different questions, then return for unfamiliar checks after seven days.</p>
    <section class="experiment-summary" aria-label="Comparison limits"><strong>${h(report.status.replaceAll('_', ' '))}</strong>
      <p>${h(report.reason)}</p><p>${h(report.uncertainty)}</p>
      <small>${h(protocol.id)} · ${h(protocol.version)} · ${h(protocol.contentVersion)} · ${h(protocol.analysisUnit)} · ${h(protocol.contentReviewStatus)} keys. This is one learner's descriptive pilot, not a test of which method works better for people.</small></section>`;
  const units = report.units.length ? `<section class="comparison-report"><h3>Your four units</h3><div class="table-scroll"><table><thead><tr><th scope="col">Unit</th><th scope="col">Method</th><th scope="col">Practice</th><th scope="col">Solution viewed</th><th scope="col">Delayed check</th><th scope="col">Delay</th></tr></thead><tbody>${report.units.map(u => `<tr><th scope="row">${h(u.name)}</th><td>${h(u.condition === 'diagram' ? 'Text with diagram' : 'Text')}</td><td>${u.practiceAnswered ? (u.practiceAssisted ? 'Assisted' : 'Unassisted first response') + (u.practiceCandidateMatch ? ' · candidate match' : ' · no candidate match') : 'Missing'}</td><td data-solution-unit="${h(u.id)}">${comparisonSolutionStatus(u, protocol.version)}</td><td>${h(u.classification)}${u.delayedAnswered ? (u.delayedCandidateMatch ? ' · candidate match' : ' · no candidate match') : ''}</td><td>${u.actualDelayDays == null ? '—' : `${h(u.actualDelayDays)} days`}</td></tr>`).join('')}</tbody></table></div>
    <p class="muted">Candidate-key matches are feedback, not verified mastery. Missing, late, contaminated, and provisional delayed answers remain distinct.</p></section>` : '';
  const arms = report.enrolled ? `<details class="evidence-panel"><summary>Descriptive counts by method</summary><div class="table-scroll"><table><thead><tr><th scope="col">Method</th><th scope="col">Assigned</th><th scope="col">All delayed answered</th><th scope="col">All candidate matches</th><th scope="col">Eligible delayed answers</th><th scope="col">Eligible candidate matches</th><th scope="col">Provisional</th><th scope="col">Missing</th><th scope="col">Late</th><th scope="col">Contaminated</th><th scope="col">Outside study unknown</th></tr></thead><tbody>${['text','diagram'].map(arm => { const c = report.arms?.[arm] ?? {}; const d = report.descriptive?.[arm] ?? {}; return `<tr><th scope="row">${arm === 'diagram' ? 'Text with diagram' : 'Text'}</th><td>${h(c.assigned)}</td><td>${h(d.observed)}</td><td>${h(d.candidateMatches)}</td><td>${h(c.eligible)}</td><td>${h(d.eligibleCandidateMatches)}</td><td>${h(c.provisional)}</td><td>${h(c.missing)}</td><td>${h(c.late)}</td><td>${h(c.contaminated)}</td><td>${h(c.outsideStudyUnknown)}</td></tr>`; }).join('')}</tbody></table></div><p class="muted">All recorded counts include ineligible answers; only eligible columns follow the delayed outcome rule. These are dependent observations from one learner and do not supply a meaningful confidence interval.</p></details>` : '';
  const dimensions = report.dimensions ? `<details class="evidence-panel"><summary>Learning dimensions and missing evidence</summary><ul>${Object.entries(report.dimensions).map(([name, data]) => `<li><strong>${h(name.replace(/([A-Z])/g, ' $1'))}:</strong> ${h(data.status.replaceAll('_', ' '))}${data.observations == null ? '' : ` · ${h(data.observations)} ${h(data.observationLabel ?? 'recorded responses')}`}${data.otherRecordedResponses == null ? '' : ` · ${h(data.otherRecordedResponses)} other delayed response${data.otherRecordedResponses === 1 ? '' : 's'} retained descriptively`}${data.pairs == null ? '' : ` · ${h(data.pairs)} confidence and draft-key pair${data.pairs === 1 ? '' : 's'}`}${data.interpretation ? ` · ${h(data.interpretation)}` : ''}</li>`).join('')}</ul><p class="muted">A candidate match is an observation, not demonstrated mastery or a causal method effect.</p></details>` : '';
  const hidePriorFeedback = Boolean(report.feedback) && report.next?.stage === 'delayed';
  const shownFeedback = hidePriorFeedback ? null : report.feedback;
  const solution = shownFeedback && (protocol.version === 'v1' || shownFeedback.solutionRevealedAt)
    ? `<details class="solution-panel" id="comparison-solution" ${protocol.version === 'v2' ? 'open' : ''}><summary>Candidate answer and reasoning</summary><p>Candidate answer: <strong>${h(shownFeedback.answer)}</strong></p><ol>${(shownFeedback.steps ?? []).map(step => `<li>${h(step)}</li>`).join('')}</ol><p class="muted">The first answer remains recorded separately.</p></details>`
    : shownFeedback ? '<button class="button secondary" id="comparison-reveal" type="button">Reveal candidate answer and reasoning</button>' : '';
  const feedback = shownFeedback ? `<section class="feedback" aria-label="Last answer feedback"><h3>Last ${h(shownFeedback.phase)} answer</h3><p>${shownFeedback.candidateMatch ? 'Matches' : 'Does not match'} the draft candidate key${shownFeedback.assisted ? ' · assisted practice' : ' · unassisted response; delayed eligibility is reported separately'}.</p>${solution}<p class="muted" id="comparison-reveal-status">${protocol.version === 'v1' ? 'Solution opening was not tracked in this historical version.' : shownFeedback.solutionRevealedAt ? 'Solution opening recorded.' : 'Solution opening not recorded.'}</p></section>` : hidePriorFeedback ? '<p class="muted">Earlier answer feedback is hidden while the delayed check is due.</p>' : '';
  if (!report.enrolled) return intro + (report.priorConceptExposure
    ? '<div class="empty"><h3>This comparison cannot start for this learner</h3><p>This concept already has learner history. A prospective assignment must begin before its lesson or practice. Existing history stays intact.</p></div>'
    : '<div class="activity-card"><h3>Start the four-unit comparison</h3><p>Assignment is fixed at enrollment. Each pair includes one text and one diagram unit; order is balanced. Your choices and study time remain under your control.</p><button class="button" id="comparison-enroll" type="button">Enroll in draft comparison</button></div>');
  const recommendation = report.recommendation;
  const recommendationMarkup = recommendation ? `<section class="experiment-summary" aria-label="Suggested next comparison activity"><h3>Suggested next: ${h(recommendation.stage.replaceAll('_', ' '))}${recommendation.unitId ? ` · ${h(recommendation.unitId)}` : ''}</h3><p>${h(recommendation.reason)}</p><p><strong>Aim:</strong> ${h(recommendation.aim)}</p><p><strong>Supporting units:</strong> ${h((recommendation.evidenceUnitIds ?? []).join(', ') || 'No prior unit yet')}</p><p><strong>Uncertainty:</strong> ${h(recommendation.uncertainty)}</p><small>Decision rule ${h(recommendation.policyVersion)}. This rule does not select a teaching method from a single favorable result.</small>${report.override ? `<p><strong>Your choice:</strong> Continue ${h(report.override.selectedStage)} in ${h(report.override.selectedUnitId)} before the due check. The original recommendation remains recorded.</p>` : recommendation.alternative ? `<div class="button-row"><button class="button secondary" id="comparison-override" type="button">Choose ${h(recommendation.alternative.stage)} in ${h(recommendation.alternative.unitId)} first</button></div><label for="comparison-override-note">Reason for your choice (optional)</label><input id="comparison-override-note" class="answer" maxlength="500">` : ''}</section>` : '';
  const next = report.next;
  let activity = '';
  if (next?.stage === 'study') {
    const unit = report.units.find(u => u.id === next.unitId);
    const instruction = report.instruction;
    if (unit?.exposureStartedAt && !instruction) throw new Error('The opened worked example is incomplete.');
    activity = `<section class="activity-card"><span class="pill">${h(unit?.condition === 'diagram' ? 'Text with labeled diagram' : 'Text')} · worked example</span><h3>${h(unit?.name)}</h3>
      ${unit?.exposureStartedAt ? `<p class="muted">Opened ${h(new Date(unit.exposureStartedAt).toLocaleString())}. Time spent is not verified.</p>` : '<button class="button" id="comparison-start" type="button">Open worked example</button>'}
      ${unit?.exposureStartedAt ? `<div class="comparison-study"><p>Trace the code, the returned value, and the unchanged global name.</p><pre class="code">${h(instruction.workedCode)}</pre><p><strong>Worked answer:</strong> ${h(instruction.workedAnswer)}</p><h4>Step by step</h4><ol>${instruction.steps.map(step => `<li>${h(step)}</li>`).join('')}</ol>${instruction.diagram ? `<figure class="lesson-diagram"><figcaption>Labeled diagram</figcaption><pre>${h(instruction.diagram)}</pre></figure>` : ''}<h4>Common misconceptions</h4><ul>${instruction.misconceptions.map(item => `<li>${h(item)}</li>`).join('')}</ul><p class="muted">Suggested study target: about ${h(instruction.studyTargetMinutes)} minutes. Attentive study is not verified.</p><p class="sources"><a href="${h(instruction.source)}" target="_blank" rel="noopener noreferrer">Python documentation source</a></p>${comparisonOutsideStudy('exposure')}<button class="button" id="comparison-complete" type="button">I studied this worked example →</button></div>` : ''}</section>`;
  } else if ((next?.stage === 'practice' || next?.stage === 'delayed') && !report.question) {
    activity = `<div class="activity-card"><span class="pill">${next.stage === 'delayed' ? 'Unfamiliar delayed assessment' : 'Practice'}</span><h3>${next.stage === 'delayed' ? 'A delayed check is ready' : 'A different practice question is ready'}</h3><p>Opening the question records its item family as encountered. Answer it without support for independent evidence.</p><button class="button" id="comparison-open" type="button">Open ${next.stage === 'delayed' ? 'delayed check' : 'practice question'}</button></div>`;
  } else if ((next?.stage === 'practice' || next?.stage === 'delayed') && report.question) {
    const q = report.question;
    const assistedPractice = q.phase === 'practice' && (q.hintOpened || Boolean(openedHint));
    const unit = report.units.find(u => u.id === next.unitId);
    const viewedAt = q.phase === 'delayed' ? unit?.delayedFirstViewedAt : null;
    const elapsedMs = viewedAt ? new Date(now).getTime() - Date.parse(viewedAt) : 0;
    const viewWarning = viewedAt && elapsedMs > 30 * 60 * 1000
      ? '<p class="error" role="alert">More than 30 minutes have passed since this delayed question was first opened. A submitted answer will be classified contaminated.</p>' : '';
    const confidence = protocol.version === 'v2' ? '<label for="comparison-confidence">Confidence before feedback (optional)</label><select id="comparison-confidence" class="answer"><option value="">Not recorded</option><option value="0">0%</option><option value="0.25">25%</option><option value="0.5">50%</option><option value="0.75">75%</option><option value="1">100%</option></select>' : '';
    activity = `<section class="activity-card"><span class="pill">${q.phase === 'delayed' ? (justOpenedDelayed ? 'Unfamiliar delayed assessment' : 'Previously opened delayed check') : 'New practice question'}</span>${viewWarning}<h3>${h(q.prompt)}</h3><pre class="code">${h(q.code)}</pre><p class="muted">Item family ${h(q.familyId)}. ${assistedPractice ? 'A hint was opened, so this answer will be assisted practice.' : 'Answer before using support for an independent first answer.'} Enter the returned value and unchanged global value as number, number.</p><label for="comparison-answer">Your first answer</label><input id="comparison-answer" class="answer" type="text" maxlength="100" autocomplete="off" placeholder="number, number" aria-describedby="comparison-answer-note"><p id="comparison-answer-note" class="muted">Your first submitted answer is locked. The candidate answer appears only after submission.</p>${comparisonOutsideStudy(q.phase)}${confidence}${assistedPractice ? `<p class="hint" role="status">Hint ${h(q.hintLevel || 1)}: ${h(openedHint || q.hintText || 'Track the local keyword parameter inside the call, then the unchanged global name.')} This practice answer will be classified assisted.</p>` : ''}${q.hintAvailable ? '<p class="muted">Open a hint only while the answer field is blank. After a hint, your later answer is assisted practice.</p>' : ''}<div class="button-row">${q.hintAvailable ? `<button class="button secondary" id="comparison-hint" type="button">${q.hintLevel ? 'Open next practice hint' : 'Open practice hint'}</button>` : ''}<button class="button" id="comparison-answer-submit" type="button">Submit first answer →</button></div></section>`;
  } else if (next?.stage === 'waiting') {
    const due = report.units.filter(u => u.exposureCompletedAt && !u.delayedAnswered).map(u => new Date(Date.parse(u.exposureCompletedAt) + 7 * 86400000));
    const soonest = due.length ? new Date(Math.min(...due)) : null;
    activity = `<div class="empty"><h3>Waiting for an unfamiliar check</h3><p>The next delayed question opens at least seven days after the worked example. Return then for an independent answer.</p>${soonest ? `<p>Next possible check: <time datetime="${h(soonest.toISOString())}">${h(soonest.toLocaleString())}</time></p>` : ''}<button class="button secondary" id="comparison-refresh" type="button">Check again</button></div>`;
  }
  return intro + recommendationMarkup + feedback + activity + dimensions + units + arms;
}

function comparisonOutsideStudy(phase) {
  const note = phase === 'practice'
    ? 'This report is recorded with your practice response. Delayed eligibility uses your study and return declarations.'
    : 'Unknown or reported outside study remains recorded but makes the delayed outcome ineligible for the primary comparison.';
  return `<label class="comparison-outside" for="comparison-outside-study">Outside study since this example (optional)</label><select id="comparison-outside-study" class="answer" aria-describedby="comparison-outside-note"><option value="unknown">Unknown or prefer not to say</option><option value="none">No outside study</option><option value="some">Yes, some outside study</option></select><p id="comparison-outside-note" class="muted">${note}</p>`;
}

export function comparisonHintBlockReason(answer) {
  return String(answer ?? '').trim()
    ? 'You have typed an answer. Submit it as your independent first answer, or clear the field before opening a hint. After a hint, a later answer is assisted practice.'
    : null;
}

if (typeof globalThis.document !== 'undefined') {
const content = document.querySelector('#content');
const conceptsEl = document.querySelector('#concepts');
const state = { overview: null, conceptId: null, lesson: null, session: null, answer: '', result: null, review: null, mode: 'recommended', view: 'path', comparison: null, comparisonHint: '', started: Date.now(), confidence: null, outsideStudy: 'unknown', outsideStudyDetail: '' };
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
  retry.onclick = async () => { try { if (state.view === 'comparison') await refreshComparison(); else if (state.conceptId) await refresh(); else await boot(); } catch (next) { showError(next); } };
  el.append(retry);
  content.replaceChildren(el);
}
function concepts() {
  const path = state.overview?.pathRecommendation;
  conceptsEl.innerHTML = state.overview.concepts.map((c, i) => {
    const schedule = c.signals.reviewSchedule;
    const timing = schedule && schedule.status !== 'none' ? ` · Review ${esc(schedule.status)}` : '';
    const draft = c.signals.openDraft ? ' · Saved first answer' : '';
    return `<button class="concept ${c.id === state.conceptId ? 'active' : ''}" data-concept="${esc(c.id)}" aria-current="${c.id === state.conceptId ? 'true' : 'false'}"><span class="num">${String(i+1).padStart(2,'0')}</span><span><span class="title">${esc(c.title)}</span><small>${c.lessonComplete ? 'Lesson read' : 'Lesson to read'} · ${c.signals.attempts} attempt${c.signals.attempts === 1 ? '' : 's'}${timing}${draft}${path && c.id === path.conceptId ? ' · Suggested' : ''}</small></span></button>`;
  }).join('');
  conceptsEl.querySelectorAll('[data-concept]').forEach(button => button.onclick = () => select(button.dataset.concept));
}
async function select(cid) {
  try {
    state.view = 'path'; updateViewNavigation();
    state.conceptId = cid; state.answer = ''; state.result = null; state.review = null; state.mode = 'recommended'; state.started = Date.now(); state.confidence = null; state.outsideStudy = 'unknown'; state.outsideStudyDetail = '';
    await refresh();
  } catch (error) { showError(error); }
}
async function chooseMorePractice() {
  const learnerReason = document.querySelector('#override-note')?.value.trim() || null;
  await api('/api/v2/overrides', { conceptId: state.conceptId, mode: 'practice', reason: 'learner_choice', learnerReason });
  state.result = null; state.review = null; state.answer = ''; state.mode = 'practice';
  state.confidence = null; state.outsideStudy = 'unknown'; state.outsideStudyDetail = '';
  await refresh();
}
async function refresh() {
  const cid = encodeURIComponent(state.conceptId);
  const [overview, lesson, session] = await Promise.all([
    api('/api/v2/overview'), api('/api/v2/lesson', {conceptId:state.conceptId}),
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
function updateViewNavigation() {
  document.querySelector('#regular-path').setAttribute('aria-current', state.view === 'path' ? 'page' : 'false');
  document.querySelector('#personal-comparison').setAttribute('aria-current', state.view === 'comparison' ? 'page' : 'false');
}
async function refreshComparison(report, options = {}) {
  state.comparison = report ?? await api('/api/v2/personal-comparison');
  content.innerHTML = personalComparisonMarkup(state.comparison, state.comparisonHint,
    new Date(), options.justOpenedDelayed === true);
  const next = state.comparison.next;
  const comparisonError = error => {
    content.querySelector('.comparison-action-error')?.remove();
    const message = document.createElement('p');
    message.className = 'error comparison-action-error';
    message.role = 'alert';
    message.tabIndex = -1;
    message.textContent = error.message || String(error);
    content.prepend(message);
    message.focus();
  };
  const act = async (action, body = {}) => {
    try {
      const updated = await api(`/api/v2/personal-comparison/${action}`, body);
      state.comparisonHint = '';
      await refreshComparison(updated, {justOpenedDelayed: action === 'open' && body.phase === 'delayed',
        focus: action});
    } catch (error) { comparisonError(error); }
  };
  const bind = (id, action, body) => {
    const node = document.querySelector(id);
    if (node) node.onclick = () => act(action, typeof body === 'function' ? body() : body);
  };
  bind('#comparison-enroll', 'enroll', {});
  bind('#comparison-reveal', 'reveal', () => ({unitId: state.comparison.feedback.unitId,
    phase: state.comparison.feedback.phase}));
  bind('#comparison-start', 'start', () => ({unitId: next.unitId}));
  bind('#comparison-complete', 'complete', () => ({unitId: next.unitId, outsideStudy: document.querySelector('#comparison-outside-study').value}));
  bind('#comparison-open', 'open', () => ({unitId: next.unitId, phase: next.stage}));
  bind('#comparison-override', 'override', () => ({recommendedUnitId: state.comparison.recommendation.unitId,
    recommendedStage: state.comparison.recommendation.stage,
    selectedUnitId: state.comparison.recommendation.alternative.unitId,
    selectedStage: state.comparison.recommendation.alternative.stage,
    learnerReason: document.querySelector('#comparison-override-note')?.value.trim() || null}));
  document.querySelector('#comparison-refresh')?.addEventListener('click', () => refreshComparison().catch(showError));
  document.querySelector('#comparison-hint')?.addEventListener('click', async () => {
    try {
      const answerInput = document.querySelector('#comparison-answer');
      const blocked = comparisonHintBlockReason(answerInput?.value);
      if (blocked) { comparisonError(new Error(blocked)); answerInput.focus(); return; }
      const result = await api('/api/v2/personal-comparison/hint', {unitId: next.unitId});
      state.comparisonHint = result.hint;
      await refreshComparison();
      document.querySelector('#comparison-answer')?.focus();
    } catch (error) { comparisonError(error); }
  });
  document.querySelector('#comparison-answer-submit')?.addEventListener('click', async () => {
    const input = document.querySelector('#comparison-answer');
    const answer = input.value.trim();
    if (!/^\d+\s*,\s*\d+$/.test(answer)) {
      input.setCustomValidity('Enter two non-negative whole numbers as number, number.');
      input.reportValidity(); input.focus();
      return;
    }
    input.setCustomValidity('');
    const confidenceValue = document.querySelector('#comparison-confidence')?.value;
    await act('answer', {unitId: next.unitId, phase: state.comparison.question.phase,
      answer, outsideStudy: document.querySelector('#comparison-outside-study').value,
      confidence: confidenceValue == null || confidenceValue === '' ? null : Number(confidenceValue)});
  });
  if (options.focus) {
    const target = options.focus === 'answer'
      ? content.querySelector('#comparison-reveal, .feedback h3')
      : options.focus === 'reveal'
        ? content.querySelector('#comparison-solution summary')
        : content.querySelector('.activity-card h3, .empty h3, .feedback h3');
    if (target) {
      if (!target.matches('button, summary, a, input, select')) target.tabIndex = -1;
      target.focus();
    }
  }
}
document.querySelector('#regular-path').onclick = async () => {
  try { state.view = 'path'; updateViewNavigation(); await refresh(); } catch (error) { showError(error); }
};
document.querySelector('#personal-comparison').onclick = async () => {
  try { state.view = 'comparison'; updateViewNavigation(); await refreshComparison(); } catch (error) { showError(error); }
};
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
  const unitLabel = finding?.analysisUnit === 'independent_learner' ? 'correlated concept observations' : 'eligible delayed answers';
  const armDetail = arm => {
    if (finding?.analysisUnit !== 'independent_learner') return '';
    const row = finding.arms[arm];
    return `; ${row.independentLearners} independent learner${row.independentLearners === 1 ? '' : 's'}` +
      (row.provisional ? `; ${row.provisional} provisional draft-key check${row.provisional === 1 ? '' : 's'} (${row.candidateKeyMatches} candidate match${row.candidateKeyMatches === 1 ? '' : 'es'})` : '') +
      (row.late ? `; ${row.late} late check${row.late === 1 ? '' : 's'} reported outside the primary window` : '') +
      (row.contaminated ? `; ${row.contaminated} familiar or assisted check${row.contaminated === 1 ? '' : 's'}` : '') +
      (row.early ? `; ${row.early} early check${row.early === 1 ? '' : 's'}` : '') +
      (row.ungraded ? `; ${row.ungraded} ungraded response${row.ungraded === 1 ? '' : 's'}` : '') +
      (row.invalid ? `; ${row.invalid} invalid response${row.invalid === 1 ? '' : 's'}` : '') +
      (row.exposureIncomparable ? `; ${row.exposureIncomparable} exposure${row.exposureIncomparable === 1 ? '' : 's'} without verified comparability` : '');
  };
  const armsMarkup = finding?.arms ? `<div class="experiment-arms"><p><strong>Method A · text:</strong> ${finding.arms.text.eligible} ${unitLabel}, ${finding.arms.text.correct} correct; ${finding.arms.text.missing} missing${armDetail('text')}.</p><p><strong>Method B · text with diagram:</strong> ${finding.arms.diagram.eligible} ${unitLabel}, ${finding.arms.diagram.correct} correct; ${finding.arms.diagram.missing} missing${armDetail('diagram')}.</p></div>` : '';
  const limitations = [
    finding?.contentReviewStatus === 'draft' ? 'Instructional content and answer keys are draft; independent review is not complete.' : null,
    finding?.protocol?.exposureDurationControlled === false ? 'Lesson exposure is self-paced, so the two methods cannot support a causal superiority claim.' : null,
    finding?.protocol?.minimumPerArm != null ? `The protocol requires ${finding.protocol.minimumPerArm} eligible delayed outcomes per method.` : null,
    finding?.protocol?.minimumIndependentLearnersPerArm != null ? `A stronger comparison needs at least ${finding.protocol.minimumIndependentLearnersPerArm} independent learners per arm, verified exposure, and reviewed content. One person's concept results remain correlated.` : null,
    finding?.syntheticResultsAreLearningEvidence === false ? 'Synthetic test results are not learner evidence.' : null,
  ].filter(Boolean);
  const assignedMethod = state.lesson.method?.conditionId === 'diagram' ? 'B · text with diagram' : state.lesson.method?.conditionId === 'text' ? 'A · text' : null;
  const experimentMarkup = finding ? `<section class="experiment-summary" aria-label="Instructional comparison findings"><strong>Instructional comparison: ${esc(finding.status.replace('_', ' '))}</strong><p>${esc(finding.reason)}</p>${assignedMethod ? `<p>Your assigned presentation here: ${esc(assignedMethod)}.</p>` : ''}${armsMarkup}${limitations.length ? `<p><strong>Limits on interpretation</strong></p><ul>${limitations.map(text => `<li>${esc(text)}</li>`).join('')}</ul>` : ''}<small>${protocolId ? `Protocol ${esc(protocolId)} · ${esc(protocolVersion)}. ` : ''}A method preference is not evidence of better learning.</small></section>` : '';
  const draftMarkup = state.result ? '' : signals.openDraft ? `<section class="draft-status" role="status" aria-label="Saved answer status"><strong>Saved first answer to resume</strong><p>Activity ${esc(signals.openDraft.activityId)} · ${esc(signals.openDraft.hintLevel.replace('_', ' '))} assistance · saved <time datetime="${esc(signals.openDraft.savedAt)}">${esc(new Date(signals.openDraft.savedAt).toLocaleString())}</time>. The first answer remains locked while you request hints.</p></section>` : state.session.draft ? '<section class="draft-status" role="status" aria-label="Saved answer status"><strong>Saved first answer to resume</strong><p>Your original answer remains locked while you request hints.</p></section>' : '';
  const reviewMarkup = state.lesson.completed ? reviewTimingMarkup(signals.reviewSchedule, state.session) : '';
  const intro = `<div class="section-kicker">CONCEPT ${String(index).padStart(2,'0')} / ${String(state.overview.concepts.length).padStart(2,'0')}</div><h2>${esc(current.title)}</h2><p class="lede">The goal is lasting understanding. The setting is yours to adjust; retrieval and delayed checks remain part of the learning path.</p><div class="path-note"><strong>Suggested next: ${esc(suggested.action.replace('_', ' '))} · ${esc(state.overview.concepts.find(c => c.id === suggested.conceptId)?.title)}</strong><p>${esc(suggested.reason)}</p>${suggested.conceptId !== state.conceptId ? '<button class="button secondary" id="follow-path">Go to suggested concept</button>' : '<span class="muted">You can choose any concept from Your Path.</span>'}</div>${draftMarkup}${reviewMarkup}${evidenceSummaryMarkup(signals.evidence)}<p class="muted">${signals.needsReview} ungraded open response${signals.needsReview === 1 ? '' : 's'}. Self review supports reflection but does not award correctness.</p>${evidenceMarkup(signals.evidence, signals.recordedAttempts)}${experimentMarkup}<div class="divider"></div>`;
  const overrideNote = '<label class="muted" for="override-note">Why choose more practice? (optional)</label><input id="override-note" class="answer" maxlength="500" placeholder="Your reason, if you want to record it">';
  content.onclick = event => { if (event.target?.id === 'follow-path') select(suggested.conceptId); };
  if (!state.lesson.completed) {
    const method = state.lesson.method;
    const methodMarkup = method ? `<div class="method-note"><strong>Instructional method ${method.conditionId === 'diagram' ? 'B' : 'A'}</strong><p>${method.conditionId === 'diagram' ? 'The same written explanation includes a labeled diagram.' : 'Written explanation and retrieval practice.'}</p>${method.studyTargetMinutes ? `<p>Comparison study target: about ${esc(method.studyTargetMinutes)} minutes with this lesson before practice in either method. You may continue sooner or later; study time is not verified.</p>` : ''}<small>Assignment ${esc(method.protocolId)} · ${esc(method.protocolVersion)}</small></div>` : '';
    const diagramMarkup = state.lesson.diagram ? `<figure class="lesson-diagram"><figcaption>Labeled concept diagram</figcaption><pre>${esc(state.lesson.diagram)}</pre></figure>` : '';
    content.innerHTML = intro + `<span class="pill">Worked answer first · draft lesson</span><h2>${esc(state.lesson.title)}</h2>${methodMarkup}<p class="method-note">Study the complete worked answer, follow each step, and check the common mistakes. Your next question uses a different item family; studying this answer does not count as an independent correct answer.</p><article class="lesson-body">${lessonMarkup(state.lesson.body)}</article>${diagramMarkup}${state.lesson.experimentNotice ? `<p class="muted">${esc(state.lesson.experimentNotice)}</p>` : ''}<p class="sources">Sources: ${state.lesson.sources.map(s=>`<a href="${esc(s.url)}" target="_blank" rel="noopener noreferrer">${esc(s.title)}</a>`).join('')}</p><div class="button-row"><button class="button" id="complete">I've studied the worked answer →</button></div>`;
    document.querySelector('#complete').onclick = async () => { try { await api('/api/v2/lesson-completions',{conceptId:state.conceptId}); await refresh(); } catch(e){showError(e)} };
    return;
  }
  if (state.result) {
    const r = validateAttemptResult(state.result);
    const status = r.scoreStatus === 'ungraded' ? 'Saved for self review' : r.scoreStatus === 'correct' ? 'Candidate key match' : 'Try another approach';
    content.innerHTML = intro + `<div class="feedback" role="status" aria-live="polite"><h3>${status}</h3><p>${esc(r.nextReason)}</p>${r.explanation && !r.solution ? `<p><strong>Why:</strong> ${esc(r.explanation)}</p>` : ''}<p class="muted">${r.assisted ? 'Hint assisted · ' : ''}Development preview · No mastery claim</p></div>${solutionMarkup(r)}` +
      (r.rubric && !state.review ? `<div class="activity-card"><span class="label">SELF REVIEW · ORIGINAL ANSWER</span><pre class="code">${esc(state.answer)}</pre><p class="muted">For each criterion, quote the part of your first answer that supports a shown or partial rating.</p>${r.rubric.criteria.map(c=>`<div class="review-row" data-criterion="${esc(c.id)}"><p><strong>${esc(c.description)}</strong></p><select class="answer rating"><option value="unsure">Unsure</option><option value="shown">Shown</option><option value="partial">Partial</option><option value="not_shown">Not shown</option></select><input class="answer evidence" placeholder="Exact quote from your answer, if shown or partial" aria-label="Evidence for ${esc(c.description)}"></div>`).join('')}<div class="button-row"><button class="button" id="review">Save self review →</button></div></div>` : '') +
      (state.review ? `<div class="activity-card"><span class="label">COMPARE AND REVISE</span><p>${esc(state.review.nextStep.replace('_',' '))}</p><pre class="code">${esc(state.review.comparison.annotatedExample)}</pre><p class="muted">Common mistakes: ${esc((state.review.comparison.commonMistakes ?? []).join(' · '))}</p><label class="muted" for="revision">A revised answer, if you want to try again</label><textarea id="revision" class="answer long"></textarea><div class="button-row"><button class="button secondary" id="save-revision">Save revision</button></div></div>` : '') +
      `${overrideNote}<div class="button-row"><button class="button" id="next">Continue →</button><button class="button secondary" id="more">Choose more practice (override)</button></div>`;
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
    content.innerHTML = intro + `<div class="empty"><h3>You're caught up for now.</h3><p>${esc(s.reason || 'The next check will be offered later.')}</p>${s.nextCheckAt ? `<p>Next check: ${esc(new Date(s.nextCheckAt).toLocaleString())}</p>` : ''}</div>${overrideNote}<div class="button-row"><button class="button secondary" id="more">Choose more practice (override)</button></div>`;
    document.querySelector('#more').onclick = () => chooseMorePractice().catch(showError);
    return;
  }
  const saved = Boolean(s.draft);
  const previous = signals.recentOutcome === 'incorrect' ? 'Your previous scored answer missed its candidate key. The policy offers continued practice.' : signals.recentOutcome === 'ungraded' ? 'Your previous open answer remains ungraded; self review supplies the comparison.' : signals.recentOutcome === 'correct' ? 'Your previous answer matched a candidate key. A delayed check still requires time and unassisted evidence.' : 'Start with retrieval after reading the lesson.';
  const reason = saved ? 'Resume the first answer you already saved.' : s.recommendation?.reason || 'Continue with an available activity.';
  const priorFamily = signals.recordedAttempts.filter(attempt => attempt.familyId === a.familyId);
  const activityLabel = a.heldOut ? 'Unfamiliar delayed assessment' :
    priorFamily.some(attempt => attempt.assisted) ? 'Assisted review' :
    priorFamily.length || signals.encounteredFamilyIds.includes(a.familyId) ? 'Repeated practice' : 'New question';
  content.innerHTML = intro + `<span class="pill">${activityLabel}</span><div class="why"><strong>Why this activity?</strong>${esc(reason)} ${esc(previous)}${priorFamily.length ? '<p>This item family has been attempted before. A new answer here remains repeat practice.</p>' : ''}${s.recommendation?.aim ? `<p><strong>Aim:</strong> ${esc(s.recommendation.aim)}</p>` : ''}${s.recommendation?.evidenceGap ? `<p><strong>Evidence still needed:</strong> ${esc(s.recommendation.evidenceGap)}</p>` : ''}${s.nextCheckAt && !a.heldOut ? `<p>Independent check time, if eligibility remains: ${esc(new Date(s.nextCheckAt).toLocaleString())}</p>` : ''}</div><div class="activity-card"><span class="label">${esc(a.type.replace('_',' '))} · ${esc(a.evidenceKind)}${a.difficulty ? ` · ${esc(a.difficulty)}` : ''}</span>${a.learningObjective ? `<p class="activity-objective"><strong>Learning objective:</strong> ${esc(a.learningObjective)}</p>` : ''}<h3>${esc(a.prompt)}</h3>${a.body ? `<pre class="code">${esc(a.body)}</pre>` : ''}<div id="answer-area"></div>${!saved ? '<div class="answer-context"><label for="confidence">How confident are you in this first answer?</label><select id="confidence" class="answer"><option value="">Prefer not to say</option><option value="0">0% · guessing</option><option value="0.25">25%</option><option value="0.5">50%</option><option value="0.75">75%</option><option value="1">100% · certain</option></select><p class="muted">Record this before opening any hints. You may leave it blank.</p></div>' : ''}<div class="button-row"><button id="save" class="button" ${saved?'disabled':''}>${saved?'First answer saved':'Save first answer →'}</button></div><div id="after-save"></div></div>${!saved && state.mode === 'recommended' ? `${overrideNote}<div class="button-row"><button class="button secondary" id="more">Choose more practice (override)</button></div>` : ''}`;
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
  const overrideButton = document.querySelector('#more');
  if (overrideButton) overrideButton.onclick = () => chooseMorePractice().catch(showError);
  if (saved) drawAfterSave(a, s.draft);
}
function drawAnswer(a, saved) {
  const area = document.querySelector('#answer-area');
  if (a.type === 'choice') {
    area.innerHTML = `<div role="group" aria-label="Answer choices">${a.choices.map((choice,i)=>`<button type="button" class="choice ${state.answer===choice?'selected':''}" aria-pressed="${state.answer===choice}" data-choice="${i}" ${saved?'disabled':''}><span aria-hidden="true">${state.answer===choice?'✓':''}</span>${esc(choice)}</button>`).join('')}</div>`;
    area.querySelectorAll('[data-choice]').forEach(button=>button.onclick=()=>{ const index = Number(button.dataset.choice); state.answer=a.choices[index]; drawAnswer(a,false); area.querySelector(`[data-choice="${index}"]`).focus(); });
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
  document.querySelector('#submit').onclick = async () => {
    try {
      const payload = buildAttemptPayload(draft.id, Math.max(0, Math.floor((Date.now()-state.started)/1000)), state.confidence, state.outsideStudy, state.outsideStudyDetail);
      const result = validateAttemptResult(await api('/api/v2/attempts', payload));
      const cid = encodeURIComponent(state.conceptId);
      const [overview, session] = await Promise.all([
        api('/api/v2/overview'),
        api(`/api/v2/session?conceptId=${cid}&mode=${state.mode}&availableMinutes=${preferences.minutes}`),
      ]);
      state.result = result;
      state.overview = validateOverview(overview);
      state.session = validateSession(session);
      concepts(); render();
    } catch (error) { showError(error); }
  };
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
