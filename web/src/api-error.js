export class ApiError extends Error {
  constructor(code, message, status) {
    super(message);
    this.name = "ApiError";
    this.code = code;
    this.status = status;
  }
}

export function toError(error) {
  if (error instanceof ApiError) {
    return { code: error.code, message: error.message };
  }
  if (error && typeof error.code === "string" && typeof error.message === "string" && error.message) {
    return { code: error.code, message: error.message };
  }
  return {
    code: "request_failed",
    message: "The request failed before it could finish.",
  };
}
