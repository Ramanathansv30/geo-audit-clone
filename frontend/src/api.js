// Local development talks to the FastAPI server on port 8000. In production the
// frontend and the API share one domain, so requests use relative paths like /api/audit.
const API_BASE_URL = import.meta.env.VITE_API_URL ?? (import.meta.env.DEV ? "http://localhost:8000" : "");
const NETWORK_ERROR = import.meta.env.DEV
  ? "Can't reach the backend. Is it running on port 8000?"
  : "Can't reach the server. Please try again in a moment.";

/**
 * Send a JSON request to the backend and return the parsed body.
 * Throws an Error whose message is safe to show to the user.
 */
async function request(path, options = {}) {
  let response;
  try {
    response = await fetch(`${API_BASE_URL}${path}`, {
      ...options,
      headers: { "Content-Type": "application/json", ...options.headers },
    });
  } catch {
    throw new Error(NETWORK_ERROR);
  }

  const data = await response.json().catch(() => null);
  if (!response.ok) {
    const detail = typeof data?.detail === "string" ? data.detail : `Request failed (HTTP ${response.status})`;
    throw new Error(detail);
  }
  return data;
}

export function auditUrl(url) {
  return request("/api/audit", { method: "POST", body: JSON.stringify({ url }) });
}

export function getBenchmarks() {
  return request("/api/benchmarks");
}
