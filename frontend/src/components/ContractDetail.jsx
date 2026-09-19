import { useState } from "react";
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
        {activeTab === "extraction" && <ExtractionView contractId={contractId} />}
        {activeTab === "discrepancies" && <DiscrepancyView contractId={contractId} />}
        {activeTab === "ask" && <QaChat contractId={contractId} />}
      </div>
    </section>
  );
}

export default ContractDetail;
