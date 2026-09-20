import { useEffect, useState } from "react";
import apiClient from "../api/client";
import UploadContract from "./UploadContract";
import "./ContractList.css";

function ContractList({ selectedId, onSelect, onContractUploaded }) {
  const [contracts, setContracts] = useState([]);
  const [status, setStatus] = useState("loading");

  useEffect(() => {
    let cancelled = false;

    apiClient
      .get("/contracts")
      .then((response) => {
        if (cancelled) return;
        setContracts(response.data);
        setStatus("ready");
      })
      .catch(() => {
        if (cancelled) return;
        setStatus("error");
      });

    return () => {
      cancelled = true;
    };
  }, []);

  const handleUploaded = (contractId, extractionMethod) => {
    setContracts((prev) => (prev.includes(contractId) ? prev : [...prev, contractId].sort()));
    setStatus("ready");
    onSelect(contractId);
    onContractUploaded?.(contractId, extractionMethod);
  };

  return (
    <nav className="contract-list">
      <h2 className="contract-list__title">Contracts</h2>

      <UploadContract onUploaded={handleUploaded} />

      {status === "loading" && <p className="loading-note">Loading contracts…</p>}
      {status === "error" && (
        <p className="error-note">Could not reach the API. Is the backend running on :8000?</p>
      )}

      {status === "ready" && (
        <ul className="contract-list__items">
          {contracts.map((contractId) => (
            <li key={contractId}>
              <button
                type="button"
                className={
                  "contract-list__item" +
                  (contractId === selectedId ? " contract-list__item--active" : "")
                }
                onClick={() => onSelect(contractId)}
              >
                {contractId}
              </button>
            </li>
          ))}
        </ul>
      )}
    </nav>
  );
}

export default ContractList;
