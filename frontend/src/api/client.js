import axios from "axios";

// VITE_API_URL points at the deployed backend in production (set it in Vercel's project
// env vars); falls back to the local FastAPI dev server otherwise.
const API_URL = import.meta.env.VITE_API_URL || "http://localhost:8000";

const apiClient = axios.create({
  baseURL: API_URL,
  headers: {
    "Content-Type": "application/json",
  },
});

export default apiClient;
