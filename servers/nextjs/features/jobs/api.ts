import { getApiUrl } from "@/utils/api";
import type { DurableJob } from "./types";

async function request<T>(path: string, init: RequestInit = {}): Promise<T> {
  const response = await fetch(getApiUrl(`/api/v1/jobs${path}`), {
    ...init,
    credentials: "include",
    headers: { "Content-Type": "application/json", ...init.headers },
  });
  if (!response.ok) {
    const payload = await response.json().catch(() => ({}));
    const error = new Error(payload.message ?? payload.detail ?? "Job request failed") as Error & { code?: string; status?: number };
    error.code = payload.code;
    error.status = response.status;
    throw error;
  }
  return response.json();
}

export const jobsApi = {
  list: (limit = 100) => request<DurableJob[]>(`?limit=${limit}`),
  get: (jobId: string) => request<DurableJob>(`/${encodeURIComponent(jobId)}`),
  cancel: (jobId: string) => request<DurableJob>(`/${encodeURIComponent(jobId)}/cancel`, { method: "POST" }),
  retry: (jobId: string) => request<DurableJob>(`/${encodeURIComponent(jobId)}/retry`, { method: "POST" }),
  eventsUrl: (jobId: string, after = 0) => getApiUrl(`/api/v1/jobs/${encodeURIComponent(jobId)}/events?after=${after}`),
};
