import { useEffect, useState } from "react";
import ExtractionView from "./ExtractionView";
import DiscrepancyView from "./DiscrepancyView";
import QaChat from "./QaChat";
import "./ContractDetail.css";

const TABS = [
  { id: "extraction", label: "Extracted Fields" },
  { id: "discrepancies", label: "Discrepancies" },
  { id: "ask", label: "Ask a Question" },
];

function ContractDetail({ contractId }) {
  const [activeTab, setActiveTab] = useState("extraction");

  // Per-contract result caches, kept at this level so switching tabs back and forth
  // doesn't re-trigger a Gemini call for data already fetched this session.
  const [extractionCache, setExtractionCache] = useState({});
  const [discrepancyCache, setDiscrepancyCache] = useState({});

  // Land on Extracted Fields whenever the selected contract changes (e.g. after a
  // fresh upload) rather than leaving the user on whatever tab a previous contract was on.
  useEffect(() => {
    setActiveTab("extraction");
  }, [contractId]);

  return (
    <section className="contract-detail">
      <header className="contract-detail__header">
        <h1>{contractId}</h1>
      </header>

      <div className="contract-detail__tabs">
        {TABS.map((tab) => (
          <button
            key={tab.id}
            type="button"
            className={
              "contract-detail__tab" + (activeTab === tab.id ? " contract-detail__tab--active" : "")
            }
            onClick={() => setActiveTab(tab.id)}
          >
            {tab.label}
          </button>
        ))}
      </div>

      <div className="contract-detail__panel">
        {activeTab === "extraction" && (
          <ExtractionView
            contractId={contractId}
            cached={extractionCache[contractId]}
            onFetched={(data) =>
              setExtractionCache((prev) => ({ ...prev, [contractId]: data }))
            }
          />
        )}
        {activeTab === "discrepancies" && (
          <DiscrepancyView
            contractId={contractId}
            cached={discrepancyCache[contractId]}
            onFetched={(data) =>
              setDiscrepancyCache((prev) => ({ ...prev, [contractId]: data }))
            }
          />
        )}
        {activeTab === "ask" && <QaChat contractId={contractId} />}
      </div>
    </section>
  );
}

export default ContractDetail;
