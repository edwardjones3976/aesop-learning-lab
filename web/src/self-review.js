export const REVIEW_RATINGS = ["shown", "partial", "not_shown", "unsure"];

export function validRubric(rubric) {
  return Boolean(rubric && typeof rubric.id === "string" && rubric.id
    && typeof rubric.version === "string" && rubric.version
    && Array.isArray(rubric.criteria) && rubric.criteria.length > 0
    && new Set(rubric.criteria.map((item) => item.id)).size === rubric.criteria.length
    && rubric.criteria.every((item) => typeof item.id === "string" && item.id
      && typeof item.description === "string" && item.description
      && typeof item.shownDescription === "string" && item.shownDescription
      && typeof item.partialDescription === "string" && item.partialDescription));
}

export function validComparison(comparison) {
  return Boolean(comparison && typeof comparison.annotatedExample === "string"
    && comparison.annotatedExample && Array.isArray(comparison.commonMistakes)
    && comparison.commonMistakes.every((text) => typeof text === "string" && text));
}

export function reviewProblem(rubric, firstAnswer, judgments) {
  if (!validRubric(rubric)) return "The review rubric is incomplete.";
  if (!Array.isArray(judgments) || judgments.length !== rubric.criteria.length) {
    return "Review every criterion before comparing answers.";
  }
  const expected = new Set(rubric.criteria.map((item) => item.id));
  const seen = new Set();
  for (const item of judgments) {
    if (!expected.has(item.criterionId) || seen.has(item.criterionId)) return "Review each criterion once.";
    seen.add(item.criterionId);
    if (!REVIEW_RATINGS.includes(item.rating)) return "Choose a rating for each criterion.";
    const evidence = String(item.evidence ?? "").trim();
    if (item.rating === "shown" || item.rating === "partial") {
      if (!evidence) return "Quote your first answer for shown or partly shown criteria.";
      if (!firstAnswer.includes(evidence)) return "The evidence must be copied from your first answer.";
    } else if (evidence) return "Only shown or partly shown ratings can include evidence.";
  }
  return null;
}

export function reviewNextStep(judgments) {
  return judgments.every((item) => item.rating === "shown") ? "independent_check" : "targeted_retry";
}
