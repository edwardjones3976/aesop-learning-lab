import assert from "node:assert/strict";
import { test } from "node:test";

import { ApiError } from "../src/api-error.js";
import { createFixtureApi } from "../src/fixture-api.js";
import {
  emptySession,
  exampleAttemptRequest,
  exampleAttemptResponse,
  exampleNextSession,
} from "../src/fixtures.js";
import { practiceMarkup } from "../src/markup.js";
import { createPracticeSession, nextHintLevel } from "../src/practice-session.js";
import { formatActive } from "../src/render.js";

function manualClock(start = 0) {
  let time = start;
  return {
    now: () => time,
    advance(ms) { time += ms; },
  };
}

async function readySession(api, now = () => 0) {
  const session = createPracticeSession(api, { now, availableMinutes: 20 });
  await session.load();
  return session;
}

function watchAttempts(api) {
  const bodies = [];
  const original = api.submitAttempt.bind(api);
  api.submitAttempt = async (body) => {
    bodies.push(body);
    return original(body);
  };
  return bodies;
}

test("nextHintLevel walks the ladder and skips missing levels", () => {
  const activity = exampleNextSession.activity;
  assert.equal(nextHintLevel(activity, []), "nudge");
  assert.equal(nextHintLevel(activity, ["nudge"]), "targeted");
  assert.equal(nextHintLevel(activity, ["nudge", "targeted"]), "worked_solution");
  assert.equal(nextHintLevel(activity, ["nudge", "targeted", "worked_solution"]), null);
  assert.equal(nextHintLevel({ hints: [{ level: "targeted", text: "Only targeted." }] }, []), "targeted");
});

test("fixture serves the documented next activity without an answer key", async () => {
  const response = await createFixtureApi().nextSession({ availableMinutes: 20 });
  assert.deepEqual(response, exampleNextSession);
  assert.equal(Object.hasOwn(response.activity, "answer"), false);
});

test("an unassisted trace matches the documented attempt", async () => {
  const clock = manualClock();
  const api = createFixtureApi();
  const bodies = watchAttempts(api);
  const session = await readySession(api, clock.now);
  clock.advance(54000);
  session.setDraft("2");
  session.recordFirstAnswer();
  session.setConfidence("0.7");
  session.setOutsideStudy("none");
  await session.submit();
  assert.deepEqual(bodies[0], exampleAttemptRequest);
  assert.deepEqual(session.getState().result, exampleAttemptResponse);
  assert.equal(session.getState().phase, "result");
});

test("unanswered confidence and outside study stay null", async () => {
  const api = createFixtureApi();
  const bodies = watchAttempts(api);
  const session = await readySession(api);
  session.setDraft("2");
  session.recordFirstAnswer();
  session.setConfidence("0");
  assert.equal(session.getState().confidence, 0);
  session.setConfidence("");
  await session.submit();
  assert.equal(bodies[0].confidence, null);
  assert.equal(bodies[0].outsideStudy, null);
  assert.equal(bodies[0].outsideStudyDetail, null);
  assert.notEqual(bodies[0].confidence, 0);
});

test("hints stay closed until the first answer and send the highest level", async () => {
  const api = createFixtureApi();
  const bodies = watchAttempts(api);
  const session = await readySession(api);
  session.revealNextHint();
  assert.equal(session.getState().error.code, "first_answer_required");
  assert.equal(session.getState().viewedHints.length, 0);
  assert.equal(practiceMarkup(session.getState()).includes("Find the stopping condition."), false);
  assert.equal(practiceMarkup(session.getState()).includes("f(0)=1, f(1)=1, f(2)=2."), false);

  session.setDraft("2");
  session.recordFirstAnswer();
  assert.equal(session.getState().firstAnswer, "2");
  session.setDraft("9");
  assert.equal(session.getState().firstAnswer, "2");
  session.revealNextHint();
  session.revealNextHint();
  const html = practiceMarkup(session.getState());
  assert.equal(html.includes("Find the stopping condition."), true);
  assert.equal(html.includes("Evaluate f(0), then f(1)."), true);
  assert.equal(html.includes("f(0)=1, f(1)=1, f(2)=2."), false);
  assert.equal(html.includes('data-control="shown-hint"'), true);
  await session.submit();
  assert.equal(bodies[0].hintLevel, "targeted");
  assert.equal(bodies[0].firstAnswer, "2");
  assert.equal(session.getState().result.assisted, true);
  assert.equal(session.getState().result.scoreStatus, "correct");
});

test("pause keeps the inactive interval out of active seconds", async () => {
  const clock = manualClock();
  const bodies = [];
  const api = {
    async nextSession() { return structuredClone(exampleNextSession); },
    async submitAttempt(body) {
      bodies.push(body);
      return {
        attemptId: "attempt-pause",
        scoreStatus: "correct",
        gradingMethod: "reviewed_exact_key",
        assisted: false,
        nextReason: "Try a different application tomorrow.",
      };
    },
  };
  const session = await readySession(api, clock.now);
  clock.advance(10000);
  session.pause();
  assert.equal(session.getState().phase, "paused");
  assert.match(practiceMarkup(session.getState()), /<form inert>/);
  assert.equal(session.getState().status, "Paused. Active time is stopped.");
  clock.advance(50000);
  session.resume();
  clock.advance(4000);
  session.setDraft("2");
  session.recordFirstAnswer();
  await session.submit();
  assert.equal(bodies[0].activeSeconds, 14);
  assert.equal(formatActive(14), "0:14");
  assert.equal(formatActive(125), "2:05");
});

test("a storage failure stays unsuccessful and can be sent again", async () => {
  const session = await readySession(createFixtureApi({ scenario: "storage" }));
  session.setDraft("2");
  session.recordFirstAnswer();
  await session.submit();
  await session.submit();
  const state = session.getState();
  assert.equal(state.result, null);
  assert.equal(state.phase, "practicing");
  assert.equal(state.error.code, "storage_unavailable");
  assert.equal(state.error.message, "Local records are unavailable right now.");
  const html = practiceMarkup(state);
  assert.equal(html.includes("Score status"), false);
  assert.equal(html.includes("Submit attempt"), true);
});

test("a revealed solution is not shown as correct", async () => {
  const session = await readySession(createFixtureApi());
  session.setDraft("2");
  session.recordFirstAnswer();
  session.revealNextHint();
  session.revealNextHint();
  session.revealNextHint();
  await session.submit();
  const result = session.getState().result;
  assert.equal(result.scoreStatus, "incorrect");
  assert.equal(result.assisted, true);
  assert.equal(result.nextReason, "A revealed solution cannot count as a correct attempt.");
});

test("a contradictory score is not presented as recorded", async () => {
  let calls = 0;
  const api = {
    async nextSession() { return structuredClone(exampleNextSession); },
    async submitAttempt() {
      calls += 1;
      return {
        attemptId: "bad-attempt",
        scoreStatus: "correct",
        gradingMethod: "reviewed_exact_key",
        assisted: false,
        nextReason: "This should not be shown.",
      };
    },
  };
  const session = await readySession(api);
  session.setDraft("2");
  session.recordFirstAnswer();
  session.revealNextHint();
  session.revealNextHint();
  session.revealNextHint();
  await session.submit();
  assert.equal(calls, 1);
  assert.equal(session.getState().phase, "rejected");
  assert.equal(session.getState().result, null);
  assert.equal(session.getState().error.code, "invalid_response");
  const html = practiceMarkup(session.getState());
  assert.equal(html.includes("Score status"), false);
  assert.equal(html.includes("This should not be shown."), false);
  await session.submit();
  assert.equal(calls, 1);
});

test("choice, explanation, and empty sessions keep their contract results", async () => {
  const session = await readySession(createFixtureApi());
  session.setDraft("2");
  session.recordFirstAnswer();
  await session.submit();
  await session.load();
  assert.equal(session.getState().activity.type, "choice");
  assert.deepEqual(session.getState().recommendation.evidenceAttemptIds, ["example-attempt-1"]);
  session.recordFirstAnswer();
  assert.equal(session.getState().error.code, "first_answer_required");
  session.setChoice("guard");
  session.recordFirstAnswer();
  assert.equal(session.getState().firstAnswer, "if n == 0: return 1");
  await session.submit();
  assert.equal(session.getState().result.scoreStatus, "correct");

  await session.load();
  assert.equal(session.getState().activity.type, "explanation");
  session.setDraft("It has to stop.");
  session.recordFirstAnswer();
  await session.submit();
  assert.equal(session.getState().result.scoreStatus, "ungraded");
  assert.equal(session.getState().result.gradingMethod, "self_review_pending");

  await session.load();
  assert.equal(session.getState().phase, "empty");
  assert.equal(session.getState().recommendation.reason, emptySession.recommendation.reason);
  assert.equal(practiceMarkup(session.getState()).includes("Nothing is due in the available time."), true);
});

test("markup escapes activity text and a missing reason is not invented", async () => {
  const session = await readySession({
    async nextSession() {
      return {
        activity: {
          ...exampleNextSession.activity,
          prompt: "<script>alert(1)</script>",
        },
        recommendation: exampleNextSession.recommendation,
      };
    },
    async submitAttempt() { throw new Error("unused"); },
  });
  const html = practiceMarkup(session.getState());
  assert.equal(html.includes("<script>"), false);
  assert.equal(html.includes("&lt;script&gt;alert(1)&lt;/script&gt;"), true);

  const missing = createPracticeSession({
    async nextSession() {
      return {
        activity: null,
        recommendation: { policyVersion: "pilot-v1", reason: " ", evidenceAttemptIds: [] },
      };
    },
    async submitAttempt() { throw new Error("unused"); },
  });
  await missing.load();
  assert.equal(missing.getState().phase, "load_error");
  assert.equal(missing.getState().error.code, "invalid_response");
  assert.equal(missing.getState().activity, null);
});

test("fixture errors use the documented status families", async () => {
  const api = createFixtureApi();
  await assert.rejects(
    api.nextSession({ availableMinutes: 0 }),
    (error) => error instanceof ApiError && error.status === 400 && error.code === "validation_error",
  );
  await assert.rejects(
    api.submitAttempt({
      activityId: "missing-activity",
      contentVersion: "v1",
      firstAnswer: "2",
      hintLevel: "none",
      confidence: null,
      outsideStudy: null,
      outsideStudyDetail: null,
      activeSeconds: 1,
    }),
    (error) => error instanceof ApiError && error.status === 404 && error.code === "not_found",
  );
  await assert.rejects(
    createFixtureApi({ scenario: "unavailable" }).nextSession({ availableMinutes: 20 }),
    (error) => error instanceof ApiError && error.status === 503 && error.code === "storage_unavailable",
  );
});
