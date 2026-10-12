export const exampleNextSession = {
  activity: {
    id: "functions-base-case-01",
    conceptId: "base-case",
    contentVersion: "v1",
    familyId: "base-case-trace-a",
    type: "trace",
    evidenceKind: "application",
    prompt: "What value does this function return for n = 2?",
    body: "def f(n):\n    if n == 0: return 1\n    return n * f(n - 1)",
    choices: [],
    hints: [
      { level: "nudge", text: "Find the stopping condition." },
      { level: "targeted", text: "Evaluate f(0), then f(1)." },
      { level: "worked_solution", text: "f(0)=1, f(1)=1, f(2)=2." },
    ],
  },
  recommendation: {
    policyVersion: "pilot-v1",
    reason: "This concept is due for an independent check.",
    evidenceAttemptIds: [],
  },
};

export const exampleAttemptRequest = {
  activityId: "functions-base-case-01",
  contentVersion: "v1",
  firstAnswer: "2",
  hintLevel: "none",
  confidence: 0.7,
  outsideStudy: "none",
  outsideStudyDetail: null,
  activeSeconds: 54,
};

export const exampleAttemptResponse = {
  attemptId: "example-attempt-1",
  scoreStatus: "correct",
  gradingMethod: "reviewed_exact_key",
  assisted: false,
  nextReason: "Try a different application tomorrow.",
};

export const choiceActivity = {
  id: "functions-base-case-02",
  conceptId: "base-case",
  contentVersion: "v1",
  familyId: "base-case-choice-b",
  type: "choice",
  evidenceKind: "recognition",
  prompt: "Which line stops the recursion?",
  body: "def f(n):\n    if n == 0: return 1\n    return n * f(n - 1)",
  choices: [
    { id: "guard", label: "if n == 0: return 1" },
    { id: "multiply", label: "return n * f(n - 1)" },
    { id: "signature", label: "def f(n):" },
  ],
  hints: [
    { level: "nudge", text: "A base case does not call the function again." },
    { level: "targeted", text: "Look for the branch that returns without a recursive call." },
    { level: "worked_solution", text: "The base case is if n == 0: return 1." },
  ],
};

export const explanationActivity = {
  id: "functions-base-case-03",
  conceptId: "base-case",
  contentVersion: "v1",
  familyId: "base-case-explain-c",
  type: "explanation",
  evidenceKind: "explanation",
  prompt: "Explain why this function needs a base case.",
  body: "def f(n):\n    if n == 0: return 1\n    return n * f(n - 1)",
  choices: [],
  hints: [
    { level: "nudge", text: "Think about what happens if every call makes another call." },
  ],
};

export const emptySession = {
  activity: null,
  recommendation: {
    policyVersion: "pilot-v1",
    reason: "Nothing is due in the available time.",
    evidenceAttemptIds: [],
  },
};
