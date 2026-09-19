import { useEffect, useState } from "react";
import { describeApiError } from "../utils/errors";

/**
 * Fetches data for a contract, skipping the network call entirely if `cached` is already
 * populated (the parent, e.g. ContractDetail, owns the cache and passes it in per tab).
 * On success, reports the result back via onFetched so the parent can store it.
 */
export function useCachedFetch({ contractId, cached, onFetched, fetcher }) {
  const [data, setData] = useState(cached ?? null);
  const [status, setStatus] = useState(cached ? "ready" : "loading");
  const [errorInfo, setErrorInfo] = useState(null);
  const [attempt, setAttempt] = useState(0);

  useEffect(() => {
    if (cached) {
      setData(cached);
      setStatus("ready");
      setErrorInfo(null);
      return;
    }

    let cancelled = false;
    setStatus("loading");
    setErrorInfo(null);

    fetcher()
      .then((result) => {
        if (cancelled) return;
        setData(result);
        setStatus("ready");
        onFetched(result);
      })
      .catch((error) => {
        if (cancelled) return;
        const info = describeApiError(error);
        setErrorInfo(info);
        setStatus(info.kind === "rate-limit" ? "rate-limited" : "error");
      });

    return () => {
      cancelled = true;
    };
    // fetcher/onFetched intentionally excluded: they're recreated every render, only
    // contractId/cached/attempt should trigger a re-fetch.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [contractId, cached, attempt]);

  const retry = () => setAttempt((n) => n + 1);

  return { data, status, errorInfo, retry };
}
