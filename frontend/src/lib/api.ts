const BASE_URL = import.meta.env.VITE_API_BASE_URL || "http://localhost:8000";

async function request<T>(endpoint: string, options?: RequestInit): Promise<T> {
  const response = await fetch(`${BASE_URL}${endpoint}`, {
    headers: {
      "Content-Type": "application/json",
      ...options?.headers,
    },
    ...options,
  });

  if (!response.ok) {
    const errorBody = await response.text();
    throw new Error(`API Error [${response.status}]: ${errorBody}`);
  }

  return response.json() as Promise<T>;
}

export const api = {
  // Read Alpaca paper portfolio & risk snapshot
  getPortfolio: () => request<any>("/api/v1/portfolio"),

  // Start a new hedge auction run
  startRun: () =>
    request<any>("/api/v1/runs", {
      method: "POST",
    }),

  // Read current run status
  getRun: (runId: string) => request<any>(`/api/v1/runs/${runId}`),

  // Execute dry-run or paper order for an approved bid
  executeRun: (runId: string, payload?: { mode?: "dry_run" | "paper" }) =>
    request<any>(`/api/v1/runs/${runId}/execute`, {
      method: "POST",
      body: JSON.stringify(payload ?? { mode: "dry_run" }),
    }),

  // Trigger controlled state drift / re-auction
  triggerReauction: (runId: string) =>
    request<any>(`/api/v1/runs/${runId}/reauction`, {
      method: "POST",
    }),
};