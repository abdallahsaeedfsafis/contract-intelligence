import { useState } from "react";
import apiClient from "../api/client";
import { describeApiError } from "../utils/errors";
import "./QaChat.css";

function QaChat({ contractId }) {
  const [query, setQuery] = useState("");
  const [messages, setMessages] = useState([]);
  const [pending, setPending] = useState(false);

  const handleSubmit = (event) => {
    event.preventDefault();
    const question = query.trim();
    if (!question || pending) return;

    const id = Date.now();
    setMessages((prev) => [...prev, { id, question, state: "pending" }]);
    setQuery("");
    setPending(true);

    apiClient
      .post(`/contracts/${contractId}/ask`, { query: question, contract_id: contractId })
      .then((response) => {
        const result = response.data;
        const notFound = result.cited_clauses.length === 0;
        setMessages((prev) =>
          prev.map((m) => (m.id === id ? { ...m, state: "answered", result, notFound } : m)),
        );
      })
      .catch((error) => {
        const info = describeApiError(error);
        setMessages((prev) =>
          prev.map((m) =>
            m.id === id
              ? { ...m, state: info.kind === "rate-limit" ? "rate-limited" : "error", errorInfo: info }
              : m,
          ),
        );
      })
      .finally(() => setPending(false));
  };

  return (
    <div className="qa-chat">
      <div className="qa-chat__thread">
        {messages.length === 0 && (
          <p className="muted">Ask a question about this contract, in Arabic or English.</p>
        )}

        {messages.map((m) => (
          <div className="qa-chat__exchange" key={m.id}>
            <div className="qa-chat__question" dir="auto">
              {m.question}
            </div>

            {m.state === "pending" && <p className="loading-note">Thinking…</p>}
            {m.state === "error" && <p className="error-note">Could not reach the API.</p>}
            {m.state === "rate-limited" && <p className="rate-limit-note">{m.errorInfo.message}</p>}

            {m.state === "answered" && (
              <div
                className={
                  "qa-chat__answer" + (m.notFound ? " qa-chat__answer--not-found" : "")
                }
                dir={m.result.language_answered_in === "arabic" ? "rtl" : "ltr"}
                lang={m.result.language_answered_in === "arabic" ? "ar" : "en"}
              >
                <p>{m.result.answer}</p>
                {!m.notFound && m.result.cited_clauses.length > 0 && (
                  <div className="qa-chat__citations" dir="ltr">
                    {m.result.cited_clauses.map((n) => (
                      <span className="qa-chat__citation" key={n}>
                        Clause {n}
                      </span>
                    ))}
                  </div>
                )}
              </div>
            )}
          </div>
        ))}
      </div>

      <form className="qa-chat__input-row" onSubmit={handleSubmit}>
        <input
          type="text"
          dir="auto"
          placeholder="e.g. What is the notice period? / ما هي مدة الإشعار؟"
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          disabled={pending}
        />
        <button type="submit" disabled={pending || !query.trim()}>
          Ask
        </button>
      </form>
    </div>
  );
}

export default QaChat;
