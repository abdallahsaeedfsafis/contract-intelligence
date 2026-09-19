import { useEffect, useState } from "react";
import apiClient from "../api/client";
import { humanizeFieldName } from "../utils/text";
import FieldValue from "./FieldValue";
import "./ExtractionView.css";

function ExtractionView({ contractId }) {
  const [data, setData] = useState(null);
  const [status, setStatus] = useState("loading");

  useEffect(() => {
    setStatus("loading");
    setData(null);
    let cancelled = false;

    apiClient
      .post(`/contracts/${contractId}/extract`)
      .then((response) => {
        if (cancelled) return;
        setData(response.data);
        setStatus("ready");
      })
      .catch(() => {
        if (cancelled) return;
        setStatus("error");
      });

    return () => {
      cancelled = true;
    };
  }, [contractId]);

  if (status === "loading") {
    return (
      <p className="loading-note">
        Extracting fields from both language sections… this calls the model twice, so it can take a
        little while.
      </p>
    );
  }

  if (status === "error") {
    return <p className="error-note">Extraction failed. Check that the API server is running and reachable.</p>;
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
