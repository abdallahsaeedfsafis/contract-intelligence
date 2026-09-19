import apiClient from "../api/client";
import { useCachedFetch } from "../hooks/useCachedFetch";
import { humanizeFieldName } from "../utils/text";
import FieldValue from "./FieldValue";
import "./DiscrepancyView.css";

function statusBadgeClass(field) {
  if (field.status === "match") return "status-badge status-badge--match";
  if (field.status === "discrepancy" && field.severity === "significant") {
    return "status-badge status-badge--discrepancy";
  }
  if (field.status === "discrepancy") return "status-badge status-badge--minor";
  return "status-badge status-badge--uncertain";
}

function statusBadgeLabel(field) {
  if (field.status === "match") return "Match";
  if (field.status === "discrepancy") return `Discrepancy · ${field.severity}`;
  return "Uncertain";
}

function DiscrepancyView({ contractId, cached, onFetched }) {
  const { data: report, status, errorInfo, retry } = useCachedFetch({
    contractId,
    cached,
    onFetched,
    fetcher: () => apiClient.get(`/contracts/${contractId}/discrepancies`).then((r) => r.data),
  });

  if (status === "loading") {
    return (
      <p className="loading-note">
        Comparing every field across both language versions… this runs several model calls, so it
        can take a little while.
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
        <p>Discrepancy check failed. Check that the API server is running and reachable.</p>
        <button type="button" className="inline-retry-button" onClick={retry}>
          Try again
        </button>
      </div>
    );
  }

  return (
    <div className="discrepancy-view">
      <div className="discrepancy-view__summary">
        <div>
          <span className="discrepancy-view__summary-number">{report.discrepancy_count}</span>
          <span className="muted"> discrepancies found</span>
        </div>
        <div>
          <span
            className="discrepancy-view__summary-number"
            style={report.significant_discrepancy_count > 0 ? { color: "var(--color-seal-red)" } : undefined}
          >
            {report.significant_discrepancy_count}
          </span>
          <span className="muted"> significant</span>
        </div>
      </div>

      {report.fields.map((field) => (
        <div className="discrepancy-field" key={field.field_name}>
          <div className="discrepancy-field__header">
            <h4>{humanizeFieldName(field.field_name)}</h4>
            <span className={statusBadgeClass(field)}>{statusBadgeLabel(field)}</span>
          </div>

          <div className="discrepancy-field__values">
            <div className="discrepancy-field__cell text-rtl" dir="rtl" lang="ar">
              <FieldValue value={field.arabic_value} />
            </div>
            <div className="discrepancy-field__cell text-ltr" dir="ltr" lang="en">
              <FieldValue value={field.english_value} />
            </div>
          </div>

          {field.explanation && <p className="discrepancy-field__explanation">{field.explanation}</p>}
        </div>
      ))}
    </div>
  );
}

export default DiscrepancyView;
