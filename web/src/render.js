import { assertLearningApi } from "./learning-api.js";
import { practiceMarkup } from "./markup.js";
import { createPracticeSession } from "./practice-session.js";

const SKIP_BODY = new Set(["draft", "detail", "minutes", "confidence", "outside", "choice"]);

export function formatActive(seconds) {
  const safe = Math.max(0, Math.floor(Number(seconds) || 0));
  const minutes = Math.floor(safe / 60);
  const remainder = safe % 60;
  return `${minutes}:${String(remainder).padStart(2, "0")}`;
}

/** True while an IME is composing; Enter must not commit a partial draft. */
export function isImeComposingKeyEvent(event) {
  return Boolean(event.isComposing || event.keyCode === 229);
}

function focusControl(root, control) {
  const node = root.querySelector(`[data-control="${control}"]`);
  if (!node) return false;
  node.focus();
  return true;
}

export function mountPracticeApp(root, session) {
  root.innerHTML = `
    <a class="skip" href="#practice">Skip to practice</a>
    <div class="sheet">
      <header class="mast">
        <p class="eyebrow">Aesop Learning Lab</p>
        <h1>Practice</h1>
        <p id="reason" class="reason"></p>
        <p id="policy" class="meta"></p>
        <div id="evidence-wrap" hidden>
          <p id="evidence-label" class="meta">Evidence attempts</p>
          <ul id="evidence" aria-labelledby="evidence-label"></ul>
        </div>
        <div class="tools">
          <label>Available minutes
            <input class="minutes" type="number" min="1" step="1" value="20" data-control="minutes" inputmode="numeric">
          </label>
          <p class="timer">Active time <span data-timer>0:00</span></p>
          <button type="button" class="secondary" data-control="pause">Pause</button>
        </div>
        <p class="meta">Available minutes are used the next time an activity is requested.</p>
        <p id="status" class="status" role="status" aria-atomic="true"></p>
        <div id="error" class="error" role="alert" aria-atomic="true" tabindex="-1" hidden></div>
      </header>
      <main id="practice"></main>
    </div>
  `;

  const reasonEl = root.querySelector("#reason");
  const policyEl = root.querySelector("#policy");
  const evidenceWrap = root.querySelector("#evidence-wrap");
  const evidenceEl = root.querySelector("#evidence");
  const statusEl = root.querySelector("#status");
  const errorEl = root.querySelector("#error");
  const pauseButton = root.querySelector('[data-control="pause"]');
  const minutesInput = root.querySelector('[data-control="minutes"]');
  const timerEl = root.querySelector("[data-timer]");
  const main = root.querySelector("#practice");

  function paintError(state) {
    const next = state.error ? `${state.error.code} ${state.error.message}` : "";
    if (errorEl.dataset.current === next) return;
    errorEl.dataset.current = next;
    errorEl.replaceChildren();
    if (!state.error) {
      errorEl.hidden = true;
      return;
    }
    const code = document.createElement("strong");
    code.textContent = state.error.code;
    errorEl.append(code, document.createTextNode(` ${state.error.message}`));
    errorEl.hidden = false;
  }

  function paint(state, meta) {
    reasonEl.textContent = state.recommendation?.reason ?? "";
    policyEl.textContent = state.recommendation ? `Policy ${state.recommendation.policyVersion}` : "";
    const evidenceIds = state.recommendation?.evidenceAttemptIds ?? [];
    evidenceWrap.hidden = evidenceIds.length === 0;
    evidenceEl.replaceChildren();
    for (const id of evidenceIds) {
      const item = document.createElement("li");
      item.textContent = id;
      evidenceEl.append(item);
    }
    statusEl.textContent = state.status;
    paintError(state);
    pauseButton.textContent = state.phase === "paused" ? "Resume" : "Pause";
    pauseButton.disabled = state.phase !== "practicing" && state.phase !== "paused";
    timerEl.textContent = formatActive(session.activeSeconds());
    if (!meta || !SKIP_BODY.has(meta.reason)) {
      if (document.activeElement !== minutesInput) {
        minutesInput.value = state.availableMinutes ?? "";
      }
      main.innerHTML = practiceMarkup(state);
    }
  }

  root.addEventListener("submit", (event) => event.preventDefault());
  root.addEventListener("click", (event) => {
    const control = event.target.closest("[data-control]")?.dataset.control;
    if (control === "record") session.recordFirstAnswer();
    if (control === "hint") session.revealNextHint();
    if (control === "submit") session.submit();
    if (control === "pause") session.togglePause();
    if (control === "continue" || control === "retry" || control === "check") session.load();
  });
  root.addEventListener("input", (event) => {
    const control = event.target.dataset.control;
    if (control === "draft") session.setDraft(event.target.value);
    if (control === "detail") session.setOutsideStudyDetail(event.target.value);
    if (control === "minutes") session.setAvailableMinutes(event.target.value);
  });
  root.addEventListener("change", (event) => {
    const control = event.target.dataset.control;
    if (control === "confidence") session.setConfidence(event.target.value);
    if (control === "outside") session.setOutsideStudy(event.target.value);
    if (event.target.name === "choice") session.setChoice(event.target.value);
  });
  document.addEventListener("keydown", (event) => {
    if (!root.isConnected || event.defaultPrevented) return;
    const target = event.target;
    const typing = target instanceof HTMLInputElement
      || target instanceof HTMLTextAreaElement
      || target instanceof HTMLSelectElement;
    if (event.key === "Enter" && target instanceof HTMLInputElement && target.dataset.control === "draft") {
      if (isImeComposingKeyEvent(event)) return;
      event.preventDefault();
      session.recordFirstAnswer();
      return;
    }
    if ((event.ctrlKey || event.metaKey) && event.key === "Enter" && target instanceof HTMLTextAreaElement && target.dataset.control === "draft") {
      if (isImeComposingKeyEvent(event)) return;
      event.preventDefault();
      session.recordFirstAnswer();
      return;
    }
    if (typing || event.altKey || event.ctrlKey || event.metaKey) return;
    if (event.key === "h" || event.key === "H") {
      event.preventDefault();
      session.revealNextHint();
    } else if (event.key === "p" || event.key === "P") {
      event.preventDefault();
      session.togglePause();
    }
  });

  session.subscribe((state, meta) => {
    paint(state, meta);
    if (meta?.reason === "record") {
      if (!focusControl(root, "hint")) focusControl(root, "submit");
    } else if (meta?.reason === "hint") {
      if (!focusControl(root, "shown-hint")) focusControl(root, "submit");
    } else if (meta?.reason === "error" && !errorEl.hidden) {
      errorEl.focus();
    } else if (meta?.reason === "pause" || meta?.reason === "resume") {
      focusControl(root, "pause");
    } else if (meta?.reason === "load" && state.phase === "practicing") {
      if (!focusControl(root, "draft")) focusControl(root, "choice");
    } else if (meta?.reason === "load" && state.phase === "empty") {
      focusControl(root, "check");
    } else if (meta?.reason === "submit") {
      focusControl(root, "result");
    }
  });

  paint(session.getState());
  setInterval(() => {
    timerEl.textContent = formatActive(session.activeSeconds());
  }, 250);
}

export function startApp(root, api) {
  assertLearningApi(api);
  const session = createPracticeSession(api);
  mountPracticeApp(root, session);
  void session.load();
  return session;
}
