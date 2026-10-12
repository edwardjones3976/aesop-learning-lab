export function assertLearningApi(api) {
  if (!api || typeof api.nextSession !== "function" || typeof api.submitAttempt !== "function") {
    throw new TypeError("LearningApi requires nextSession and submitAttempt");
  }
}
