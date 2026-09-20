import { useRef, useState } from "react";
import apiClient from "../api/client";
import "./UploadContract.css";

const ALLOWED_EXTENSIONS = [".txt", ".docx", ".pdf"];

function UploadContract({ onUploaded }) {
  const inputRef = useRef(null);
  const [status, setStatus] = useState("idle"); // idle | uploading | error
  const [errorMessage, setErrorMessage] = useState("");

  const handleFileChange = (event) => {
    const file = event.target.files?.[0];
    event.target.value = ""; // allow re-selecting the same file after an error
    if (!file) return;

    const extension = "." + (file.name.split(".").pop() || "").toLowerCase();
    if (!ALLOWED_EXTENSIONS.includes(extension)) {
      setStatus("error");
      setErrorMessage(`Unsupported file type. Allowed: ${ALLOWED_EXTENSIONS.join(", ")}.`);
      return;
    }

    const formData = new FormData();
    formData.append("file", file);

    setStatus("uploading");
    setErrorMessage("");

    apiClient
      .post("/contracts/upload", formData, {
        headers: { "Content-Type": "multipart/form-data" },
      })
      .then((response) => {
        setStatus("idle");
        onUploaded(response.data.contract_id);
      })
      .catch((error) => {
        const detail = error?.response?.data?.detail;
        setStatus("error");
        setErrorMessage(
          typeof detail === "string"
            ? detail
            : "Upload failed. Check that the API server is running and reachable.",
        );
      });
  };

  return (
    <div className="upload-contract">
      <button
        type="button"
        className="upload-contract__button"
        onClick={() => inputRef.current?.click()}
        disabled={status === "uploading"}
      >
        {status === "uploading" ? "Uploading & extracting…" : "+ Upload Contract"}
      </button>
      <input
        ref={inputRef}
        type="file"
        accept=".txt,.docx,.pdf"
        onChange={handleFileChange}
        hidden
      />
      {status === "error" && <p className="upload-contract__error">{errorMessage}</p>}
    </div>
  );
}

export default UploadContract;
