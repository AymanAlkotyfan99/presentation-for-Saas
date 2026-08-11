import { getApiUrl } from "@/utils/api";
import type { CapabilityFamily, PolicySimulationResult, ProviderAccount, ProviderAdapterDescriptor, RegionPolicyStatus, RoutingPolicy } from "./types";

async function request<T>(path: string, init: RequestInit = {}): Promise<T> {
  const response = await fetch(getApiUrl(`/api/v1/providers${path}`), {
    ...init,
    credentials: "include",
    headers: { "Content-Type": "application/json", ...init.headers },
  });
  if (!response.ok) {
    const payload = await response.json().catch(() => ({}));
    const error = new Error(payload.message ?? payload.detail ?? "Provider request failed") as Error & { status?: number };
    error.status = response.status;
    throw error;
  }
  return response.status === 204 ? (undefined as T) : response.json();
}

export const providersApi = {
  adapters: () => request<ProviderAdapterDescriptor[]>("/adapters"),
  accounts: () => request<ProviderAccount[]>("/accounts"),
  create: (value: { adapterId: string; name: string; defaultModel: string; capabilityModels: string[]; safeConfig?: Record<string, string | number | boolean | null>; regionPolicyStatus: RegionPolicyStatus; secret?: string }) =>
    request<ProviderAccount>("/accounts", { method: "POST", body: JSON.stringify(value) }),
  update: (id: string, value: Partial<Pick<ProviderAccount, "name" | "defaultModel" | "safeConfig" | "enabled" | "emergencyDisabled" | "regionPolicyStatus">> & { capabilityModels?: string[] }) =>
    request<ProviderAccount>(`/accounts/${encodeURIComponent(id)}`, { method: "PATCH", body: JSON.stringify(value) }),
  setCapability: (accountId: string, capabilityId: string, enabled: boolean) =>
    request<{ id: string; enabled: boolean }>(`/accounts/${encodeURIComponent(accountId)}/capabilities/${encodeURIComponent(capabilityId)}`, { method: "PUT", body: JSON.stringify({ enabled }) }),
  rotateSecret: (id: string, secret: string) => request<void>(`/accounts/${encodeURIComponent(id)}/secret`, { method: "PUT", body: JSON.stringify({ secret }) }),
  deleteSecret: (id: string) => request<void>(`/accounts/${encodeURIComponent(id)}/secret`, { method: "DELETE" }),
  test: (id: string) => request<{ jobId: string; replayed: boolean }>(`/accounts/${encodeURIComponent(id)}/connection-tests`, { method: "POST" }),
  policy: (family: CapabilityFamily) => request<RoutingPolicy | null>(`/routing-policies/${family}`),
  savePolicy: (family: CapabilityFamily, value: { priorityAccountIds: string[]; allowFallback: boolean; maxFallbacks: number; regionRules: Record<string, string>; planRules: Record<string, string> }) =>
    request<RoutingPolicy>(`/routing-policies/${family}`, { method: "PUT", body: JSON.stringify(value) }),
  simulate: (value: { family: CapabilityFamily; model?: string; pinnedAccountId?: string }) =>
    request<PolicySimulationResult>("/routing-policies/simulate", { method: "POST", body: JSON.stringify(value) }),
};
