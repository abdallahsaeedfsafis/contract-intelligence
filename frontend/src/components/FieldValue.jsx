import { humanizeFieldName } from "../utils/text";

function FieldValue({ value }) {
  if (value === null || value === undefined || value === "") {
    return <span className="muted">—</span>;
  }

  if (Array.isArray(value)) {
    if (value.length === 0) return <span className="muted">—</span>;
    return (
      <ul className="field-value-list">
        {value.map((item, i) => (
          <li key={i}>{typeof item === "object" ? <FieldValue value={item} /> : String(item)}</li>
        ))}
      </ul>
    );
  }

  if (typeof value === "object") {
    return (
      <dl className="field-value-object">
        {Object.entries(value).map(([key, val]) => (
          <div className="field-value-object__row" key={key}>
            <dt>{humanizeFieldName(key)}</dt>
            <dd>{val === null || val === undefined || val === "" ? <span className="muted">—</span> : String(val)}</dd>
          </div>
        ))}
      </dl>
    );
  }

  return <>{String(value)}</>;
}

export default FieldValue;
