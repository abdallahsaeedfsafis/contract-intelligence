import apiClient from "../api/client";
import { useCachedFetch } from "../hooks/useCachedFetch";
import { humanizeFieldName } from "../utils/text";
import FieldValue from "./FieldValue";
import "./ExtractionView.css";

function ExtractionView({ contractId, cached, onFetched }) {
  const { data, status, errorInfo, retry } = useCachedFetch({
    contractId,
    cached,
    onFetched,
    fetcher: () => apiClient.post(`/contracts/${contractId}/extract`).then((r) => r.data),
  });

  if (status === "loading") {
    return (
      <p className="loading-note">
        Extracting fields from both language sections… this calls the model twice, so it can take a
        little while.
      </p>
    );
  }

  if (status === "rate-limited") {
    return (
      <div className="rate-limit-note">
        <p>{errorInfo.message}</p>
        <button type="button" className="inline-retry-button" onClick={retry}>
          Try again
        </button>
      </div>
    );
  }

  if (status === "error") {
    return (
      <div className="error-note">
        <p>Extraction failed. Check that the API server is running and reachable.</p>
        <button type="button" className="inline-retry-button" onClick={retry}>
          Try again
        </button>
      </div>
    );
  }

  const fields = Array.from(new Set([...Object.keys(data.arabic), ...Object.keys(data.english)]));

  return (
    <div className="extraction-view">
      <div className="extraction-view__header">
        <span className="extraction-view__col-label" />
        <span className="extraction-view__col-label text-rtl" dir="rtl" lang="ar">
          النسخة العربية
        </span>
        <span className="extraction-view__col-label text-ltr" dir="ltr" lang="en">
          English
        </span>
      </div>

      {fields.map((field) => (
        <div className="extraction-view__row" key={field}>
          <h4 className="extraction-view__field-name">{humanizeFieldName(field)}</h4>
          <div className="extraction-view__cell text-rtl" dir="rtl" lang="ar">
            <FieldValue value={data.arabic[field]} />
          </div>
          <div className="extraction-view__cell text-ltr" dir="ltr" lang="en">
            <FieldValue value={data.english[field]} />
          </div>
        </div>
      ))}
    </div>
  );
}

export default ExtractionView;
