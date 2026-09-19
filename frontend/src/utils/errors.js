const DEFAULT_RETRY_AFTER_SECONDS = 30;

/**
 * Turns an axios error into a small, render-friendly description. Backend rate-limit
 * responses (429) get a distinct "rate-limit" kind with a friendly wait message.
 */
export function describeApiError(error) {
  const status = error?.response?.status;

  if (status === 429) {
    const detail = error.response.data?.detail;
    const retryAfterHeader = error.response.headers?.["retry-after"];
    const retryAfter = Number(detail?.retry_after ?? retryAfterHeader) || DEFAULT_RETRY_AFTER_SECONDS;
    return {
      kind: "rate-limit",
      retryAfter,
      message: detail?.message || `Rate limit reached, please wait ${retryAfter} seconds and try again.`,
    };
  }

  return {
    kind: "error",
    message: "Something went wrong talking to the API. Check that the backend is running and reachable.",
  };
}
