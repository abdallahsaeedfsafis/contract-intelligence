import { useState } from "react";
import ContractList from "./components/ContractList";
import ContractDetail from "./components/ContractDetail";
import "./App.css";

function App() {
  const [selectedId, setSelectedId] = useState(null);

  return (
    <div className="app">
      <header className="app__header">
        <h1>Bilingual Contract Intelligence</h1>
      </header>

      <div className="app__body">
        <ContractList selectedId={selectedId} onSelect={setSelectedId} />

        <main className="app__main">
          {selectedId ? (
            <ContractDetail contractId={selectedId} />
          ) : (
            <p className="app__empty-state muted">Select a contract from the list to get started.</p>
          )}
        </main>
      </div>
    </div>
  );
}

export default App;
