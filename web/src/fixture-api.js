import { ApiError } from "./api-error.js";
import {
  choiceActivity,
  emptySession,
  exampleAttemptResponse,
  exampleNextSession,
  explanationActivity,
} from "./fixtures.js";

const HINT_LEVELS = new Set(["none", "nudge", "targeted", "worked_solution"]);
const OUTSIDE = new Set(["none", "some", "unknown"]);

const answerKeys = new Map([
  ["functions-base-case-01", "2"],
  ["functions-base-case-02", "if n == 0: return 1"],
]);

const queue = [exampleNextSession.activity, choiceActivity, explanationActivity];
const reasons = [
  exampleNextSession.recommendation.reason,
  "This item is a recognition check.",
  "This item asks for an explanation.",
];

function clone(value) {
  return structuredClone(value);
}

function sessionResponse(activity, reason, evidenceAttemptIds) {
  return {
    activity: activity ? clone(activity) : null,
    recommendation: {
      policyVersion: "pilot-v1",
      reason,
      evidenceAttemptIds: [...evidenceAttemptIds],
    },
  };
}

function requireAttemptShape(body) {
  if (!body || typeof body !== "object") {
    throw new ApiError("validation_error", "The attempt body was empty.", 400);
  }
  for (const key of [
    "activityId",
    "contentVersion",
    "firstAnswer",
    "hintLevel",
    "confidence",
    "outsideStudy",
    "outsideStudyDetail",
    "activeSeconds",
  ]) {
    if (!(key in body)) {
      throw new ApiError("validation_error", `The attempt is missing ${key}.`, 400);
    }
  }
  if (typeof body.firstAnswer !== "string" || !body.firstAnswer.trim()) {
    throw new ApiError("validation_error", "A first answer is required.", 400);
  }
  if (!HINT_LEVELS.has(body.hintLevel)) {
    throw new ApiError("validation_error", "The hint level is not recognized.", 400);
  }
  if (body.confidence !== null && (typeof body.confidence !== "number" || body.confidence < 0 || body.confidence > 1)) {
    throw new ApiError("validation_error", "Confidence must be between 0 and 1, or null.", 400);
  }
  if (body.outsideStudy !== null && !OUTSIDE.has(body.outsideStudy)) {
    throw new ApiError("validation_error", "Outside study must be none, some, unknown, or null.", 400);
  }
  if (body.outsideStudyDetail !== null && typeof body.outsideStudyDetail !== "string") {
    throw new ApiError("validation_error", "Outside study detail must be text or null.", 400);
  }
  if (!Number.isInteger(body.activeSeconds) || body.activeSeconds < 0) {
    throw new ApiError("validation_error", "Active seconds must be a whole number that is not negative.", 400);
  }
}

function scoreAttempt(activity, body) {
  const assisted = body.hintLevel !== "none";
  if (activity.type === "explanation" || activity.type === "code_design") {
    return {
      scoreStatus: "ungraded",
      gradingMethod: "self_review_pending",
      assisted,
      nextReason: "This response stays ungraded until self or human review.",
    };
  }
  if (body.hintLevel === "worked_solution") {
    return {
      scoreStatus: "incorrect",
      gradingMethod: "reviewed_exact_key",
      assisted: true,
      nextReason: "A revealed solution cannot count as a correct attempt.",
    };
  }
  const correct = body.firstAnswer === answerKeys.get(activity.id);
  let nextReason = "The recorded answer did not match the reviewed key.";
  if (correct && assisted) nextReason = "The answer matched the reviewed key after a hint.";
  if (correct && !assisted) nextReason = "Try a different application tomorrow.";
  return {
    scoreStatus: correct ? "correct" : "incorrect",
    gradingMethod: "reviewed_exact_key",
    assisted,
    nextReason,
  };
}

export function createFixtureApi({ scenario = "default" } = {}) {
  if (!["default", "empty", "storage", "unavailable"].includes(scenario)) {
    throw new Error(`Unknown fixture scenario: ${scenario}`);
  }
  const activities = new Map(queue.map((activity) => [activity.id, activity]));
  const attempts = [];
  let cursor = 0;

  return {
    async nextSession({ availableMinutes } = {}) {
      if (!Number.isInteger(availableMinutes) || availableMinutes < 1) {
        throw new ApiError("validation_error", "Available minutes must be a positive whole number.", 400);
      }
      if (scenario === "unavailable") {
        throw new ApiError("storage_unavailable", "Local records are unavailable right now.", 503);
      }
      if (scenario === "empty" || cursor >= queue.length) {
        const response = clone(emptySession);
        response.recommendation.evidenceAttemptIds = attempts.map((attempt) => attempt.attemptId);
        return response;
      }
      const activity = queue[cursor];
      const reason = reasons[cursor];
      cursor += 1;
      return sessionResponse(activity, reason, attempts.map((attempt) => attempt.attemptId));
    },

    async submitAttempt(body) {
      requireAttemptShape(body);
      const activity = activities.get(body.activityId);
      if (!activity || activity.contentVersion !== body.contentVersion) {
        throw new ApiError("not_found", "That activity is not in the local records.", 404);
      }
      if (scenario === "storage") {
        throw new ApiError("storage_unavailable", "Local records are unavailable right now.", 503);
      }
      const scored = scoreAttempt(activity, body);
      const isExample = attempts.length === 0
        && activity.id === "functions-base-case-01"
        && body.firstAnswer === "2"
        && body.hintLevel === "none"
        && scored.scoreStatus === "correct";
      const attemptId = isExample ? exampleAttemptResponse.attemptId : `attempt-${attempts.length + 1}`;
      const result = { attemptId, ...scored };
      attempts.push(result);
      return clone(result);
    },
  };
}
