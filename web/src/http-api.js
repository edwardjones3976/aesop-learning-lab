import { ApiError } from "./api-error.js";

export function createHttpApi({ baseUrl = "http://127.0.0.1:8766", fetchImpl = fetch } = {}) {
  async function request(path, method = "GET", body) {
    let response;
    try {
      response = await fetchImpl(`${baseUrl}${path}`, {
        method,
        headers: body === undefined ? {} : { "Content-Type": "application/json" },
        body: body === undefined ? undefined : JSON.stringify(body),
      });
    } catch {
      throw new ApiError("service_unavailable", "The local practice service is unavailable.", 503);
    }
    let payload;
    try { payload = await response.json(); }
    catch { throw new ApiError("invalid_response", "The local service returned invalid JSON.", 502); }
    if (!response.ok) {
      throw new ApiError(payload?.code ?? "service_error",
        payload?.message ?? "The local service rejected the request.", response.status);
    }
    return payload;
  }
  return {
    nextSession({ availableMinutes = 20, mode = "recommended" } = {}) {
      return request(`/api/v1/session/next?availableMinutes=${encodeURIComponent(availableMinutes)}&mode=${encodeURIComponent(mode)}`);
    },
    submitAttempt(body) { return request("/api/v1/attempts", "POST", body); },
    submitSelfReview(body) { return request("/api/v1/self-reviews", "POST", body); },
    submitRevision(body) { return request("/api/v1/answer-revisions", "POST", body); },
    exportData() { return request("/api/v1/export"); },
    deleteData() { return request("/api/v1/data", "DELETE"); },
  };
}
