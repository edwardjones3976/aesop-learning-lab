import { nextHintLevel } from "./practice-session.js";

const HINT_LABEL = {
  nudge: "Show a small hint",
  targeted: "Show another hint",
  worked_solution: "Show a worked answer",
};

export function escapeHtml(value) {
  return String(value)
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#39;");
}

function scoreLabel(status) {
  if (status === "correct") return "Matches the answer key";
  if (status === "incorrect") return "Does not match the answer key";
  if (status === "ungraded") return "Not graded";
  return String(status);
}

function hintLabel(level) {
  return {
    none: "No hint",
    nudge: "Small hint",
    targeted: "Second hint",
    worked_solution: "Worked answer",
  }[level] ?? String(level);
}

function gradingLabel(method) {
  return {
    reviewed_exact_key: "Compared with an answer key",
    development_fixture_exact_key: "Compared with a test answer key",
    ungraded_pending_review: "Waiting for your guided review",
  }[method] ?? String(method).replaceAll("_", " ");
}

function choiceId(choice) {
  return typeof choice === "string" ? choice : choice.id;
}

function choiceText(choice) {
  return typeof choice === "string" ? choice : choice.label;
}

function answerFields(state) {
  const activity = state.activity;
  if (state.firstAnswer) {
    return `<p class="field-label">Your first answer</p><p class="recorded">${escapeHtml(state.firstAnswer)}</p><p class="meta">Saved. Hints will not change this answer.</p>`;
  }
  if (activity.type === "choice") {
    const choices = activity.choices.map((choice, index) => {
      const id = choiceId(choice);
      const checked = state.selectedChoice === id ? " checked" : "";
      const control = index === 0 ? ' data-control="choice"' : "";
      return `<label class="choice"><input type="radio" name="choice" value="${escapeHtml(id)}"${control}${checked}> ${escapeHtml(choiceText(choice))}</label>`;
    }).join("");
    return `<fieldset><legend>Your first answer</legend><p class="meta">Choose an answer before opening a hint. You cannot change it after saving.</p>${choices}<button type="button" data-control="record">Save first answer</button></fieldset>`;
  }
  const multiline = activity.type === "explanation" || activity.type === "code_design";
  const spellcheck = activity.type === "explanation" ? "true" : "false";
  const described = ' aria-describedby="answer-note"';
  const control = multiline
    ? `<textarea id="first-answer" data-control="draft" spellcheck="${spellcheck}"${described}>${escapeHtml(state.draft)}</textarea>`
    : `<input id="first-answer" type="text" data-control="draft" value="${escapeHtml(state.draft)}" autocomplete="off" spellcheck="false"${described}>`;
  const note = multiline
    ? "Answer before opening a hint. Press Ctrl+Enter to save it. You cannot change it later."
    : "Answer before opening a hint. Press Enter to save it. You cannot change it later.";
  return `<label class="stack-field" for="first-answer">Your first answer</label><p id="answer-note" class="meta">${note}</p>${control}<button type="button" data-control="record">Save first answer</button>`;
}

function confidenceField(state) {
  const selected = state.confidence == null ? "" : state.confidence.toFixed(1);
  const options = [`<option value=""${selected === "" ? " selected" : ""}>Not answered</option>`];
  for (let step = 0; step <= 10; step += 1) {
    const value = (step / 10).toFixed(1);
    options.push(`<option value="${value}"${value === selected ? " selected" : ""}>${step * 10}%</option>`);
  }
  return `<label class="stack-field">How sure are you before seeing the result?
    <select data-control="confidence">${options.join("")}</select>
  </label><p class="meta">You can leave this blank. A blank answer is different from 0%.</p>`;
}

function outsideField(state) {
  const current = state.outsideStudy ?? "";
  const option = (value, label) => `<option value="${value}"${current === value ? " selected" : ""}>${label}</option>`;
  return `<label class="stack-field">Have you studied this elsewhere? (optional)
    <select data-control="outside">
      ${option("", "Not answered")}
      ${option("none", "None")}
      ${option("some", "Some")}
      ${option("unknown", "Unknown")}
    </select>
  </label>
  <label class="stack-field">Where did you study it? (optional)
    <input type="text" data-control="detail" value="${escapeHtml(state.outsideStudyDetail ?? "")}" autocomplete="off">
  </label>`;
}

function hintFields(state) {
  const lastHint = state.viewedHints.length - 1;
  const frames = state.viewedHints.map((hint, index) => {
    const current = index === lastHint ? ' tabindex="-1" data-control="shown-hint"' : "";
    return `<li class="stack-frame" style="--depth:${index}"${current}><p class="stack-level">${escapeHtml(hintLabel(hint.level))}</p><p>${escapeHtml(hint.text)}</p></li>`;
  }).join("");
  const next = nextHintLevel(state.activity, state.viewedHints.map((hint) => hint.level));
  let action = `<p>No further hints.</p>`;
  if (state.activity.hints.length === 0) action = `<p>This activity has no hints.</p>`;
  else if (next) {
    const note = next === "worked_solution"
      ? `<p id="solution-note" class="meta">Looking at this answer will not count as solving the question on your own.</p>`
      : "";
    const described = next === "worked_solution" ? ' aria-describedby="solution-note"' : "";
    const locked = state.firstAnswer ? "" : " disabled";
    action = `${note}<button type="button" data-control="hint"${described}${locked}>${HINT_LABEL[next]}</button>`;
  }
  return `<section class="hints" aria-labelledby="hint-heading"><h3 id="hint-heading">Need help?</h3><p class="meta">Save your first answer before opening hints. We record which hints you used.</p><ol class="stack">${frames}</ol>${action}</section>`;
}

function practiceForm(state) {
  const activity = state.activity;
  const frozen = state.phase === "paused" || state.phase === "submitting" ? " inert" : "";
  const body = activity.body
    ? `<pre><code>${escapeHtml(activity.body)}</code></pre>`
    : "";
  return `<article>
    <details class="meta"><summary>Question details</summary><p>Concept: ${escapeHtml(activity.conceptId)} · Content version: ${escapeHtml(activity.contentVersion)} · Question type: ${escapeHtml(activity.type.replaceAll("_", " "))} · Skill: ${escapeHtml(activity.evidenceKind)} · Question family: ${escapeHtml(activity.familyId)}</p></details>
    <h2 class="prompt">${escapeHtml(activity.prompt)}</h2>
    ${body}
    <form${frozen}>
      ${answerFields(state)}
      ${confidenceField(state)}
      ${outsideField(state)}
      ${hintFields(state)}
      <button type="button" class="submit" data-control="submit"${state.firstAnswer ? "" : " disabled"}>Check my answer</button>
    </form>
    <p class="keys">Use Tab to move between controls. Enter saves a short answer; Ctrl+Enter saves a longer one. When you are not typing, H opens a hint and P pauses.</p>
  </article>`;
}

function resultPanel(state) {
  const result = state.result;
  const order = ["none", "nudge", "targeted", "worked_solution"];
  let hintLevel = "none";
  for (const hint of state.viewedHints) {
    if (order.indexOf(hint.level) > order.indexOf(hintLevel)) hintLevel = hint.level;
  }
  const assistance = result.assisted ? "Used a hint or answer" : "No hints used";
  return `<article>
    <h2 id="result-heading" data-control="result" tabindex="-1">Your answer was saved</h2>
    <p class="prompt">${escapeHtml(state.activity.prompt)}</p>
    <p class="field-label">Your first answer</p>
    <p class="recorded">${escapeHtml(state.firstAnswer)}</p>
    <dl class="score">
      <dt>Result</dt><dd>${escapeHtml(scoreLabel(result.scoreStatus))}</dd>
      <dt>How it was checked</dt><dd>${escapeHtml(state.developmentOnly ? "Compared with a test answer key" : gradingLabel(result.gradingMethod))}</dd>
      <dt>Help used</dt><dd>${assistance}</dd>
      <dt>Last hint opened</dt><dd>${escapeHtml(hintLabel(hintLevel))}</dd>
      <dt>Answer record</dt><dd>${escapeHtml(result.attemptId)}</dd>
      <dt>What to do next</dt><dd>${escapeHtml(result.nextReason)}</dd>
    </dl>
    <button type="button" data-control="continue">Continue</button>
    <button type="button" class="secondary" data-control="practice">More practice</button>
  </article>`;
}

function reviewPanel(state) {
  const criteria = state.rubric.criteria.map((criterion, index) => {
    const current = state.judgments[criterion.id] ?? { rating: "", evidence: "" };
    const option = (value, label) => `<option value="${value}"${current.rating === value ? " selected" : ""}>${label}</option>`;
    const evidenceField = current.rating === "shown" || current.rating === "partial"
      ? `<label class="stack-field">Copy the part of your first answer that shows this
          <input type="text" data-control="review-evidence" data-criterion="${escapeHtml(criterion.id)}" value="${escapeHtml(current.evidence)}" autocomplete="off">
        </label>` : "";
    return `<fieldset class="review-criterion"><legend>${index + 1}. ${escapeHtml(criterion.description)}</legend>
      <p class="meta"><strong>Shown:</strong> ${escapeHtml(criterion.shownDescription)}</p>
      <p class="meta"><strong>Partly shown:</strong> ${escapeHtml(criterion.partialDescription)}</p>
      <label class="stack-field">How does your answer compare?
        <select data-control="review-rating" data-criterion="${escapeHtml(criterion.id)}">
          ${option("", "Choose one")}${option("shown", "Shown")}${option("partial", "Partly shown")}
          ${option("not_shown", "Not shown")}${option("unsure", "Unsure")}
        </select>
      </label>${evidenceField}</fieldset>`;
  }).join("");
  const confidence = state.reviewConfidence == null ? "" : state.reviewConfidence.toFixed(1);
  const options = [`<option value=""${confidence === "" ? " selected" : ""}>Not answered</option>`];
  for (let step = 0; step <= 10; step += 1) {
    const value = (step / 10).toFixed(1);
    options.push(`<option value="${value}"${confidence === value ? " selected" : ""}>${step * 10}%</option>`);
  }
  return `<article>
    <h2 data-control="result" tabindex="-1">Review your first answer</h2>
    <p class="meta">Answer ${escapeHtml(state.result.attemptId)} · review guide ${escapeHtml(state.rubric.id)} ${escapeHtml(state.rubric.version)} · not automatically graded</p>
    <p class="prompt">${escapeHtml(state.activity.prompt)}</p>
    <p class="field-label">Your saved first answer</p><p class="recorded">${escapeHtml(state.firstAnswer)}</p>
    <p class="meta">For each point, choose how well your answer covers it. If you choose shown or partly shown, copy the part of your answer that supports your choice. You can choose unsure.</p>
    <form${state.phase === "review_submitting" ? " inert" : ""}>${criteria}
      <label class="stack-field">How sure are you about this review? (optional)
        <select data-control="review-confidence">${options.join("")}</select>
      </label>
      <button type="button" data-control="save-review">Save review and show example</button>
    </form>
  </article>`;
}

function comparisonPanel(state) {
  const mistakes = state.comparison.commonMistakes.map((item) => `<li>${escapeHtml(item)}</li>`).join("");
  const next = state.review.nextStep === "independent_check"
    ? "Your review says your answer covered every point. A later question without help is still needed to check this."
    : "Your answer may be missing a point. Try another question about that point.";
  return `<article>
    <h2 data-control="comparison" tabindex="-1">Compare and revise</h2>
    <p class="meta">Review ${escapeHtml(state.review.reviewId)} saved. Your first answer has not changed and has not been graded.</p>
    <p class="field-label">Your first answer</p><p class="recorded">${escapeHtml(state.firstAnswer)}</p>
    <h3>Example answer with explanation</h3><p>${escapeHtml(state.comparison.annotatedExample)}</p>
    <h3>Common mistakes</h3><ul>${mistakes}</ul>
    <p>${escapeHtml(next)}</p>
    <label class="stack-field">Try writing a better answer (optional)
      <textarea data-control="revision-draft"${state.phase === "revision_submitting" ? " disabled" : ""}>${escapeHtml(state.revisionDraft)}</textarea>
    </label>
    <button type="button" data-control="save-revision"${state.phase === "revision_submitting" ? " disabled" : ""}>Save new answer separately</button>
    <button type="button" class="secondary" data-control="finish-review"${state.revisionDraft.trim() || state.phase === "revision_submitting" ? " disabled" : ""}>Finish without a new answer</button>
  </article>`;
}

function reviewDonePanel(state) {
  const next = state.review.nextStep === "independent_check"
    ? "You still need to answer a later question without help to show what you remember."
    : "Try another question about the point you missed before a later check.";
  return `<article><h2 data-control="review-done" tabindex="-1">Review finished</h2>
    <p>Your first answer has not been graded. ${escapeHtml(next)}</p>
    <p class="meta">Review ${escapeHtml(state.review.reviewId)}${state.revisionId ? ` · revision ${escapeHtml(state.revisionId)}` : ""}</p>
    <button type="button" data-control="continue">Continue</button><button type="button" class="secondary" data-control="practice">More practice</button></article>`;
}

export function practiceMarkup(state) {
  if (state.phase === "loading") return `<p>Loading the next activity.</p>`;
  if (state.phase === "load_error") {
    return `<section><h2>The activity did not load</h2><button type="button" data-control="retry">Try again</button></section>`;
  }
  if (state.phase === "empty") {
    return `<section><h2>No activity right now</h2><p>${escapeHtml(state.recommendation.reason)}</p><button type="button" data-control="check">Check again</button><button type="button" class="secondary" data-control="practice">More practice</button></section>`;
  }
  if (state.phase === "rejected") {
    return `<section><h2>Result unavailable</h2><p>The app could not verify this response, so it will not show it as a saved result.</p><button type="button" data-control="continue">Continue</button></section>`;
  }
  if (state.phase === "result") return resultPanel(state);
  if (state.phase === "review" || state.phase === "review_submitting") return reviewPanel(state);
  if (state.phase === "comparison" || state.phase === "revision_submitting") return comparisonPanel(state);
  if (state.phase === "review_done") return reviewDonePanel(state);
  if (!state.activity) return `<p>Loading the next activity.</p>`;
  return practiceForm(state);
}
