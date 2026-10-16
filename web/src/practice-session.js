import { toError } from "./api-error.js";
import { assertLearningApi } from "./learning-api.js";
import { reviewNextStep, reviewProblem, validComparison, validRubric } from "./self-review.js";

export const HINT_LADDER = ["nudge", "targeted", "worked_solution"];
const ACTIVITY_TYPES = new Set(["choice", "trace", "explanation", "code_design"]);
const EVIDENCE_KINDS = new Set(["recognition", "recall", "explanation", "application", "transfer"]);
const OUTSIDE = new Set(["none", "some", "unknown"]);

export function nextHintLevel(activity, viewedLevels) {
  const available = new Set((activity?.hints ?? []).map((hint) => hint.level));
  return HINT_LADDER.find((level) => available.has(level) && !viewedLevels.includes(level)) ?? null;
}

function highestHint(viewed) {
  let best = "none";
  let bestIndex = -1;
  for (const hint of viewed) {
    const index = HINT_LADDER.indexOf(hint.level);
    if (index > bestIndex) {
      bestIndex = index;
      best = hint.level;
    }
  }
  return best;
}

function validateActivity(activity) {
  if (!activity || typeof activity !== "object") return "The session response did not include an activity.";
  for (const key of ["id", "conceptId", "contentVersion", "familyId", "type", "evidenceKind", "prompt"]) {
    if (typeof activity[key] !== "string" || !activity[key]) return `The activity is missing ${key}.`;
  }
  if (!ACTIVITY_TYPES.has(activity.type)) return "The activity type is not recognized.";
  if (!EVIDENCE_KINDS.has(activity.evidenceKind)) return "The evidence kind is not recognized.";
  if (activity.body != null && typeof activity.body !== "string") return "The activity body must be text.";
  if (!Array.isArray(activity.choices)) return "Activity choices must be a list.";
  if (!Array.isArray(activity.hints)) return "Activity hints must be a list.";
  if (activity.type === "choice" && activity.choices.length === 0) return "This choice activity has no choices.";
  const seen = new Set();
  for (const hint of activity.hints) {
    if (!hint || !HINT_LADDER.includes(hint.level) || typeof hint.text !== "string" || !hint.text) {
      return "A hint is missing a level or text.";
    }
    if (seen.has(hint.level)) return "A hint level is repeated.";
    seen.add(hint.level);
  }
  for (const choice of activity.choices) {
    if (typeof choice === "string") {
      if (!choice) return "A choice is empty.";
      continue;
    }
    if (!choice || typeof choice.id !== "string" || !choice.id || typeof choice.label !== "string" || !choice.label) {
      return "A choice is missing an id or label.";
    }
  }
  return null;
}

function validateRecommendation(recommendation) {
  if (!recommendation || typeof recommendation !== "object") {
    return "The session response did not include a recommendation.";
  }
  if (typeof recommendation.reason !== "string" || !recommendation.reason.trim()) {
    return "The session response did not include a recommendation reason.";
  }
  if (typeof recommendation.policyVersion !== "string" || !recommendation.policyVersion) {
    return "The session response did not include a policy version.";
  }
  if (!Array.isArray(recommendation.evidenceAttemptIds)) return "Evidence attempt ids were not a list.";
  return null;
}

function choiceLabel(activity, id) {
  for (const choice of activity.choices) {
    if (typeof choice === "string") {
      if (choice === id) return choice;
    } else if (choice.id === id) {
      return choice.label;
    }
  }
  return "";
}

function resultIsComplete(result) {
  return Boolean(result
    && typeof result.attemptId === "string" && result.attemptId
    && typeof result.scoreStatus === "string" && result.scoreStatus
    && typeof result.gradingMethod === "string" && result.gradingMethod
    && typeof result.assisted === "boolean"
    && typeof result.nextReason === "string" && result.nextReason);
}

export function createPracticeSession(api, { now = () => Date.now(), availableMinutes = 20 } = {}) {
  assertLearningApi(api);
  const listeners = new Set();
  let loadToken = 0;
  let accumulatedMs = 0;
  let runningSince = null;
  const state = {
    phase: "loading",
    mode: "recommended",
    nextCheckAt: null,
    developmentOnly: false,
    availableMinutes,
    activity: null,
    recommendation: null,
    draft: "",
    selectedChoice: "",
    firstAnswer: null,
    confidence: null,
    outsideStudy: null,
    outsideStudyDetail: null,
    viewedHints: [],
    result: null,
    rubric: null,
    judgments: {},
    reviewConfidence: null,
    review: null,
    comparison: null,
    revisionDraft: "",
    revisionId: null,
    error: null,
    status: "Loading the next activity.",
    sent: false,
  };

  function elapsedMs() {
    let ms = accumulatedMs;
    if (runningSince != null) {
      const delta = now() - runningSince;
      if (delta > 0) ms += delta;
    }
    return ms;
  }

  function activeSeconds() {
    return Math.floor(elapsedMs() / 1000);
  }

  function freeze() {
    if (runningSince != null) {
      const delta = now() - runningSince;
      if (delta > 0) accumulatedMs += delta;
      runningSince = null;
    }
  }

  function getState() {
    return {
      phase: state.phase,
      mode: state.mode,
      nextCheckAt: state.nextCheckAt,
      developmentOnly: state.developmentOnly,
      availableMinutes: state.availableMinutes,
      activity: state.activity ? structuredClone(state.activity) : null,
      recommendation: state.recommendation ? structuredClone(state.recommendation) : null,
      draft: state.draft,
      selectedChoice: state.selectedChoice,
      firstAnswer: state.firstAnswer,
      confidence: state.confidence,
      outsideStudy: state.outsideStudy,
      outsideStudyDetail: state.outsideStudyDetail,
      viewedHints: state.viewedHints.map((hint) => ({ ...hint })),
      result: state.result ? { ...state.result } : null,
      rubric: state.rubric ? structuredClone(state.rubric) : null,
      judgments: structuredClone(state.judgments),
      reviewConfidence: state.reviewConfidence,
      review: state.review ? { ...state.review } : null,
      comparison: state.comparison ? structuredClone(state.comparison) : null,
      revisionDraft: state.revisionDraft,
      revisionId: state.revisionId,
      error: state.error ? { ...state.error } : null,
      status: state.status,
      sent: state.sent,
    };
  }

  function notify(reason) {
    const snapshot = getState();
    for (const listener of [...listeners]) listener(snapshot, { reason });
  }

  function fail(code, message) {
    state.error = { code, message };
    state.status = "";
    notify("error");
  }

  function resetPracticeFields() {
    state.activity = null;
    state.recommendation = null;
    state.draft = "";
    state.selectedChoice = "";
    state.firstAnswer = null;
    state.confidence = null;
    state.outsideStudy = null;
    state.outsideStudyDetail = null;
    state.viewedHints = [];
    state.result = null;
    state.rubric = null;
    state.judgments = {};
    state.reviewConfidence = null;
    state.review = null;
    state.comparison = null;
    state.revisionDraft = "";
    state.revisionId = null;
    state.error = null;
    state.sent = false;
    accumulatedMs = 0;
    runningSince = null;
  }

  function applySession(response) {
    if (!response || typeof response !== "object") {
      state.phase = "load_error";
      state.error = { code: "invalid_response", message: "The session response was not a record." };
      state.status = "";
      notify("error");
      return;
    }
    const recommendation = response.recommendation ?? (response.activity == null ? {
      policyVersion: "pilot-v1", reason: response.reason,
      evidenceAttemptIds: [],
    } : null);
    const recommendationProblem = validateRecommendation(recommendation);
    if (recommendationProblem) {
      state.phase = "load_error";
      state.activity = null;
      state.recommendation = null;
      state.error = { code: "invalid_response", message: recommendationProblem };
      state.status = "";
      notify("error");
      return;
    }
    state.recommendation = {
      policyVersion: recommendation.policyVersion,
      reason: recommendation.reason,
      evidenceAttemptIds: recommendation.evidenceAttemptIds.map(String),
    };
    state.mode = response.mode ?? state.mode;
    state.nextCheckAt = response.nextCheckAt ?? null;
    state.developmentOnly = response.developmentOnly === true;
    if (response.activity == null) {
      state.phase = "empty";
      state.activity = null;
      state.error = null;
      state.status = "No activity was returned.";
      notify("load");
      return;
    }
    const activityProblem = validateActivity(response.activity);
    if (activityProblem) {
      state.phase = "load_error";
      state.activity = null;
      state.error = { code: "invalid_response", message: activityProblem };
      state.status = "";
      notify("error");
      return;
    }
    state.activity = structuredClone(response.activity);
    state.phase = "practicing";
    state.error = null;
    state.status = "Activity ready.";
    accumulatedMs = 0;
    runningSince = now();
    notify("load");
  }

  async function load(mode = "recommended") {
    const token = ++loadToken;
    if (!Number.isInteger(state.availableMinutes) || state.availableMinutes < 1) {
      resetPracticeFields();
      state.phase = "load_error";
      state.recommendation = null;
      state.error = {
        code: "validation_error",
        message: "Enter available minutes as a whole number of at least 1.",
      };
      state.status = "";
      notify("error");
      return;
    }
    resetPracticeFields();
    state.phase = "loading";
    state.error = null;
    state.status = "Loading the next activity.";
    notify("load-start");
    try {
      const response = await api.nextSession({ availableMinutes: state.availableMinutes, mode });
      if (token !== loadToken) return;
      applySession(response);
    } catch (error) {
      if (token !== loadToken) return;
      resetPracticeFields();
      state.phase = "load_error";
      state.error = toError(error);
      state.status = "";
      notify("error");
    }
  }

  function setAvailableMinutes(value) {
    const text = String(value ?? "").trim();
    if (/^\d+$/.test(text)) {
      const minutes = Number(text);
      state.availableMinutes = minutes >= 1 ? minutes : null;
    } else {
      state.availableMinutes = null;
    }
    notify("minutes");
  }

  function setDraft(text) {
    if (state.phase !== "practicing" || state.firstAnswer) return;
    state.draft = String(text);
    notify("draft");
  }

  function setChoice(id) {
    if (state.phase !== "practicing" || state.firstAnswer) return;
    state.selectedChoice = String(id);
    notify("choice");
  }

  function recordFirstAnswer() {
    if (state.phase === "paused") {
      fail("paused", "Resume before changing this activity.");
      return;
    }
    if (state.phase !== "practicing" || state.firstAnswer) return;
    const answer = state.activity.type === "choice"
      ? choiceLabel(state.activity, state.selectedChoice).trim()
      : state.draft.trim();
    if (!answer) {
      fail("first_answer_required", "Record a first answer before hints or submission.");
      return;
    }
    state.firstAnswer = answer;
    state.error = null;
    state.status = "First answer recorded.";
    notify("record");
  }

  function setConfidence(raw) {
    if (state.phase !== "practicing") return;
    if (raw === "" || raw == null) {
      state.confidence = null;
      state.error = null;
      notify("confidence");
      return;
    }
    const value = Number(raw);
    if (!Number.isFinite(value) || value < 0 || value > 1) {
      fail("validation_error", "Confidence must be between 0 and 1, or left unanswered.");
      return;
    }
    state.confidence = Math.round(value * 10) / 10;
    state.error = null;
    notify("confidence");
  }

  function setOutsideStudy(raw) {
    if (state.phase !== "practicing") return;
    if (raw === "" || raw == null) {
      state.outsideStudy = null;
    } else if (OUTSIDE.has(raw)) {
      state.outsideStudy = raw;
    } else {
      fail("validation_error", "Outside study must be none, some, unknown, or left unanswered.");
      return;
    }
    state.error = null;
    notify("outside");
  }

  function setOutsideStudyDetail(text) {
    if (state.phase !== "practicing") return;
    const trimmed = String(text ?? "").trim();
    state.outsideStudyDetail = trimmed ? trimmed : null;
    notify("detail");
  }

  function revealNextHint() {
    if (state.phase === "paused") {
      fail("paused", "Resume before changing this activity.");
      return;
    }
    if (state.phase !== "practicing") return;
    if (!state.firstAnswer) {
      fail("first_answer_required", "Record a first answer before opening a hint.");
      return;
    }
    const level = nextHintLevel(state.activity, state.viewedHints.map((hint) => hint.level));
    if (!level) {
      state.status = "No further hints are available for this activity.";
      notify("hint");
      return;
    }
    const hint = state.activity.hints.find((item) => item.level === level);
    state.viewedHints = [...state.viewedHints, { level, text: hint.text }];
    state.error = null;
    state.status = `Hint opened: ${level}.`;
    notify("hint");
  }

  function pause() {
    if (state.phase !== "practicing") return;
    freeze();
    state.phase = "paused";
    state.status = "Paused. Active time is stopped.";
    notify("pause");
  }

  function resume() {
    if (state.phase !== "paused") return;
    runningSince = now();
    state.phase = "practicing";
    state.status = "Resumed.";
    notify("resume");
  }

  function togglePause() {
    if (state.phase === "practicing") pause();
    else if (state.phase === "paused") resume();
  }

  function buildPayload() {
    return {
      activityId: state.activity.id,
      contentVersion: state.activity.contentVersion,
      firstAnswer: state.firstAnswer,
      hintLevel: highestHint(state.viewedHints),
      confidence: state.confidence,
      outsideStudy: state.outsideStudy,
      outsideStudyDetail: state.outsideStudyDetail,
      activeSeconds: activeSeconds(),
    };
  }

  async function submit() {
    if (state.phase === "paused") {
      fail("paused", "Resume before submitting the attempt.");
      return;
    }
    if (state.phase !== "practicing" || state.sent) return;
    if (!state.firstAnswer) {
      fail("first_answer_required", "Record a first answer before submitting the attempt.");
      return;
    }
    freeze();
    const payload = buildPayload();
    state.phase = "submitting";
    state.error = null;
    state.status = "Submitting attempt.";
    notify("submit-start");
    let response;
    try {
      response = await api.submitAttempt(payload);
    } catch (error) {
      runningSince = now();
      state.phase = "practicing";
      state.result = null;
      state.error = toError(error);
      state.status = "";
      notify("error");
      return;
    }
    state.sent = true;
    const sentAssisted = payload.hintLevel !== "none";
    if (!resultIsComplete(response)) {
      state.phase = "rejected";
      state.result = null;
      state.error = { code: "invalid_response", message: "The attempt response was missing grading details." };
      state.status = "";
      notify("error");
      return;
    }
    if (payload.hintLevel === "worked_solution" && response.scoreStatus === "correct") {
      state.phase = "rejected";
      state.result = null;
      state.error = {
        code: "invalid_response",
        message: "The response marked a revealed solution as correct. It was not shown as a successful attempt.",
      };
      state.status = "";
      notify("error");
      return;
    }
    if (response.assisted !== sentAssisted) {
      state.phase = "rejected";
      state.result = null;
      state.error = {
        code: "invalid_response",
        message: "The response disagreed with the hint level that was sent. It was not shown as recorded.",
      };
      state.status = "";
      notify("error");
      return;
    }
    const openEnded = state.activity.type === "explanation" || state.activity.type === "code_design";
    if (openEnded
        && (response.scoreStatus !== "ungraded" || !validRubric(response.rubric))) {
      state.phase = "rejected";
      state.result = null;
      state.error = { code: "invalid_response", message: "The open-ended response needs an ungraded result and a complete rubric." };
      state.status = "";
      notify("error");
      return;
    }
    state.result = {
      attemptId: response.attemptId,
      scoreStatus: response.scoreStatus,
      gradingMethod: response.gradingMethod,
      assisted: response.assisted,
      nextReason: response.nextReason,
    };
    state.rubric = response.rubric ? structuredClone(response.rubric) : null;
    state.phase = openEnded ? "review" : "result";
    state.error = null;
    state.status = openEnded
      ? "First answer recorded. Compare it with each rubric criterion."
      : `Attempt recorded. Score status: ${response.scoreStatus}.`;
    notify("submit");
  }

  function setReviewRating(criterionId, rating) {
    if (state.phase !== "review" || !state.rubric.criteria.some((item) => item.id === criterionId)) return;
    state.judgments[criterionId] = { rating, evidence: "" };
    state.error = null;
    notify("review-rating");
  }

  function setReviewEvidence(criterionId, evidence) {
    if (state.phase !== "review" || !state.rubric.criteria.some((item) => item.id === criterionId)) return;
    state.judgments[criterionId] ??= { rating: "", evidence: "" };
    state.judgments[criterionId].evidence = String(evidence);
    notify("review-evidence");
  }

  function setReviewConfidence(raw) {
    if (state.phase !== "review") return;
    if (raw === "") state.reviewConfidence = null;
    else {
      const value = Number(raw);
      if (!Number.isFinite(value) || value < 0 || value > 1) {
        fail("validation_error", "Review confidence must be between 0 and 1, or unanswered.");
        return;
      }
      state.reviewConfidence = value;
    }
    notify("review-confidence");
  }

  async function submitReview() {
    if (state.phase !== "review") return;
    const judgments = state.rubric.criteria.map((criterion) => ({
      criterionId: criterion.id,
      rating: state.judgments[criterion.id]?.rating ?? "",
      evidence: (state.judgments[criterion.id]?.evidence ?? "").trim(),
    }));
    const problem = reviewProblem(state.rubric, state.firstAnswer, judgments);
    if (problem) { fail("validation_error", problem); return; }
    if (typeof api.submitSelfReview !== "function") {
      fail("unavailable", "This adapter cannot save self reviews.");
      return;
    }
    state.phase = "review_submitting";
    state.error = null;
    state.status = "Saving self review.";
    notify("review-submit-start");
    try {
      const response = await api.submitSelfReview({
        attemptId: state.result.attemptId,
        rubricId: state.rubric.id,
        rubricVersion: state.rubric.version,
        judgments,
        confidence: state.reviewConfidence,
      });
      if (!response || typeof response.reviewId !== "string" || !response.reviewId
          || response.nextStep !== reviewNextStep(judgments)
          || !validComparison(response.comparison)) {
        throw new Error("The saved review response was incomplete.");
      }
      state.review = { reviewId: response.reviewId, nextStep: response.nextStep };
      state.comparison = structuredClone(response.comparison);
      state.phase = "comparison";
      state.status = "Review saved. Compare your answer with the example, then revise or finish.";
      notify("review-saved");
    } catch (error) {
      state.phase = "review";
      state.error = toError(error);
      state.status = "";
      notify("error");
    }
  }

  function setRevisionDraft(text) {
    if (state.phase !== "comparison") return;
    state.revisionDraft = String(text);
    notify("revision-draft");
  }

  async function submitRevision() {
    if (state.phase !== "comparison") return;
    if (!state.revisionDraft.trim()) { fail("validation_error", "Write a revision before saving it."); return; }
    if (typeof api.submitRevision !== "function") { fail("unavailable", "This adapter cannot save revisions."); return; }
    state.phase = "revision_submitting";
    state.error = null;
    state.status = "Saving revision.";
    notify("revision-submit-start");
    try {
      const response = await api.submitRevision({ reviewId: state.review.reviewId, answer: state.revisionDraft });
      if (!response || typeof response.revisionId !== "string" || !response.revisionId) {
        throw new Error("The saved revision response was incomplete.");
      }
      state.revisionId = response.revisionId;
      state.phase = "review_done";
      state.status = "Revision saved separately from the first answer.";
      notify("revision-saved");
    } catch (error) {
      state.phase = "comparison";
      state.error = toError(error);
      state.status = "";
      notify("error");
    }
  }

  function finishWithoutRevision() {
    if (state.phase !== "comparison" || state.revisionDraft.trim()) return;
    state.phase = "review_done";
    state.status = "Self review saved. A later independent check is still needed.";
    notify("review-finished");
  }

  return {
    getState,
    activeSeconds,
    subscribe(listener) {
      listeners.add(listener);
      return () => listeners.delete(listener);
    },
    load,
    setAvailableMinutes,
    setDraft,
    setChoice,
    recordFirstAnswer,
    setConfidence,
    setOutsideStudy,
    setOutsideStudyDetail,
    revealNextHint,
    pause,
    resume,
    togglePause,
    submit,
    setReviewRating,
    setReviewEvidence,
    setReviewConfidence,
    submitReview,
    setRevisionDraft,
    submitRevision,
    finishWithoutRevision,
  };
}
