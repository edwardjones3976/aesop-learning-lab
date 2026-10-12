import { nextHintLevel } from "./practice-session.js";

const HINT_LABEL = {
  nudge: "Show nudge",
  targeted: "Show targeted hint",
  worked_solution: "Show worked solution",
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
  if (status === "correct") return "Correct";
  if (status === "incorrect") return "Incorrect";
  if (status === "ungraded") return "Not graded yet";
  return String(status);
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
    return `<p class="field-label">First answer</p><p class="recorded">${escapeHtml(state.firstAnswer)}</p><p class="meta">Recorded. Later hints do not replace it.</p>`;
  }
  if (activity.type === "choice") {
    const choices = activity.choices.map((choice, index) => {
      const id = choiceId(choice);
      const checked = state.selectedChoice === id ? " checked" : "";
      const control = index === 0 ? ' data-control="choice"' : "";
      return `<label class="choice"><input type="radio" name="choice" value="${escapeHtml(id)}"${control}${checked}> ${escapeHtml(choiceText(choice))}</label>`;
    }).join("");
    return `<fieldset><legend>First answer</legend><p class="meta">Choose the answer you would give before any hint. Recording locks it.</p>${choices}<button type="button" data-control="record">Record first answer</button></fieldset>`;
  }
  const multiline = activity.type === "explanation" || activity.type === "code_design";
  const spellcheck = activity.type === "explanation" ? "true" : "false";
  const described = ' aria-describedby="answer-note"';
  const control = multiline
    ? `<textarea id="first-answer" data-control="draft" spellcheck="${spellcheck}"${described}>${escapeHtml(state.draft)}</textarea>`
    : `<input id="first-answer" type="text" data-control="draft" value="${escapeHtml(state.draft)}" autocomplete="off" spellcheck="false"${described}>`;
  const note = multiline
    ? "Write the answer you would give before any hint. Ctrl+Enter records it and locks it."
    : "Write the answer you would give before any hint. Enter records it and locks it.";
  return `<label class="stack-field" for="first-answer">First answer</label><p id="answer-note" class="meta">${note}</p>${control}<button type="button" data-control="record">Record first answer</button>`;
}

function confidenceField(state) {
  const selected = state.confidence == null ? "" : state.confidence.toFixed(1);
  const options = [`<option value=""${selected === "" ? " selected" : ""}>Not answered</option>`];
  for (let step = 0; step <= 10; step += 1) {
    const value = (step / 10).toFixed(1);
    options.push(`<option value="${value}"${value === selected ? " selected" : ""}>${step * 10}%</option>`);
  }
  return `<label class="stack-field">Confidence before the result is shown
    <select data-control="confidence">${options.join("")}</select>
  </label><p class="meta">Leave this unanswered if you prefer. Unanswered is not zero.</p>`;
}

function outsideField(state) {
  const current = state.outsideStudy ?? "";
  const option = (value, label) => `<option value="${value}"${current === value ? " selected" : ""}>${label}</option>`;
  return `<label class="stack-field">Outside study, optional
    <select data-control="outside">
      ${option("", "Not answered")}
      ${option("none", "None")}
      ${option("some", "Some")}
      ${option("unknown", "Unknown")}
    </select>
  </label>
  <label class="stack-field">Outside study detail, optional
    <input type="text" data-control="detail" value="${escapeHtml(state.outsideStudyDetail ?? "")}" autocomplete="off">
  </label>`;
}

function hintFields(state) {
  const lastHint = state.viewedHints.length - 1;
  const frames = state.viewedHints.map((hint, index) => {
    const current = index === lastHint ? ' tabindex="-1" data-control="shown-hint"' : "";
    return `<li class="stack-frame" style="--depth:${index}"${current}><p class="stack-level">${escapeHtml(hint.level)}</p><p>${escapeHtml(hint.text)}</p></li>`;
  }).join("");
  const next = nextHintLevel(state.activity, state.viewedHints.map((hint) => hint.level));
  let action = `<p>No further hints.</p>`;
  if (state.activity.hints.length === 0) action = `<p>This activity has no hints.</p>`;
  else if (next) {
    const note = next === "worked_solution"
      ? `<p id="solution-note" class="meta">A revealed solution cannot count as a correct attempt.</p>`
      : "";
    const described = next === "worked_solution" ? ' aria-describedby="solution-note"' : "";
    const locked = state.firstAnswer ? "" : " disabled";
    action = `${note}<button type="button" data-control="hint"${described}${locked}>${HINT_LABEL[next]}</button>`;
  }
  return `<section class="hints" aria-labelledby="hint-heading"><h3 id="hint-heading">Hint ladder</h3><p class="meta">Hints stay closed until the first answer is recorded. The highest one you open is sent with the attempt.</p><ol class="stack">${frames}</ol>${action}</section>`;
}

function practiceForm(state) {
  const activity = state.activity;
  const frozen = state.phase === "paused" || state.phase === "submitting" ? " inert" : "";
  const body = activity.body
    ? `<pre><code>${escapeHtml(activity.body)}</code></pre>`
    : "";
  return `<article>
    <p class="meta">${escapeHtml(activity.conceptId)} · ${escapeHtml(activity.contentVersion)} · ${escapeHtml(activity.type)} · ${escapeHtml(activity.evidenceKind)} · ${escapeHtml(activity.familyId)}</p>
    <h2 class="prompt">${escapeHtml(activity.prompt)}</h2>
    ${body}
    <form${frozen}>
      ${answerFields(state)}
      ${confidenceField(state)}
      ${outsideField(state)}
      ${hintFields(state)}
      <button type="button" class="submit" data-control="submit"${state.firstAnswer ? "" : " disabled"}>Submit attempt</button>
    </form>
    <p class="keys">Tab moves between controls. Enter records a one-line answer. Ctrl+Enter records a longer answer. When you are not typing, H opens the next hint and P pauses.</p>
  </article>`;
}

function resultPanel(state) {
  const result = state.result;
  const order = ["none", "nudge", "targeted", "worked_solution"];
  let hintLevel = "none";
  for (const hint of state.viewedHints) {
    if (order.indexOf(hint.level) > order.indexOf(hintLevel)) hintLevel = hint.level;
  }
  const assistance = result.assisted ? "Assisted" : "Unassisted";
  return `<article>
    <h2 id="result-heading" data-control="result" tabindex="-1">Attempt recorded</h2>
    <p class="prompt">${escapeHtml(state.activity.prompt)}</p>
    <p class="field-label">First answer</p>
    <p class="recorded">${escapeHtml(state.firstAnswer)}</p>
    <dl class="score">
      <dt>Score status</dt><dd>${escapeHtml(scoreLabel(result.scoreStatus))} (${escapeHtml(result.scoreStatus)})</dd>
      <dt>Grading method</dt><dd>${escapeHtml(result.gradingMethod)}</dd>
      <dt>Assistance</dt><dd>${assistance}</dd>
      <dt>Hint level sent</dt><dd>${escapeHtml(hintLevel)}</dd>
      <dt>Attempt</dt><dd>${escapeHtml(result.attemptId)}</dd>
      <dt>Next</dt><dd>${escapeHtml(result.nextReason)}</dd>
    </dl>
    <button type="button" data-control="continue">Continue</button>
  </article>`;
}

export function practiceMarkup(state) {
  if (state.phase === "loading") return `<p>Loading the next activity.</p>`;
  if (state.phase === "load_error") {
    return `<section><h2>The activity did not load</h2><button type="button" data-control="retry">Try again</button></section>`;
  }
  if (state.phase === "empty") {
    return `<section><h2>No activity right now</h2><p>${escapeHtml(state.recommendation.reason)}</p><button type="button" data-control="check">Check again</button></section>`;
  }
  if (state.phase === "rejected") {
    return `<section><h2>Score not shown</h2><p>This page did not accept the response, so it is not shown as recorded.</p><button type="button" data-control="continue">Continue</button></section>`;
  }
  if (state.phase === "result") return resultPanel(state);
  if (!state.activity) return `<p>Loading the next activity.</p>`;
  return practiceForm(state);
}
