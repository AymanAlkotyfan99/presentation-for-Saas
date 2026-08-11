export type CapabilityFamily = "TEXT" | "IMAGE" | "SEARCH";
export type RegionPolicyStatus = "ALLOWED" | "BLOCKED" | "UNKNOWN" | "ADMIN_REVIEW";

export interface ProviderAdapterDescriptor {
  adapterId: string;
  family: CapabilityFamily;
  models: string[];
  metadata: { secretRequired?: boolean; compatibility?: boolean; liveConnectionTest?: boolean };
}

export interface ProviderAccount {
  id: string;
  adapterId: string;
  name: string;
  defaultModel: string | null;
  safeConfig: Record<string, string | number | boolean | null>;
  regionPolicyStatus: RegionPolicyStatus;
  enabled: boolean;
  emergencyDisabled: boolean;
  hasSecret: boolean;
  maskedSecret: string | null;
  capabilities: Array<{ id: string; family: CapabilityFamily; model: string; enabled: boolean; metadata: Record<string, unknown> }>;
  health: { status: "HEALTHY" | "DEGRADED" | "UNHEALTHY" | "UNKNOWN"; latencyMs: number | null; safeErrorCode: string | null; checkedAt: string | null } | null;
}

export interface RoutingPolicy {
  family: CapabilityFamily;
  priority_account_ids: string[];
  allow_fallback: boolean;
  max_fallbacks: number;
  version: number;
}

export interface PolicySimulationResult {
  candidates: Array<{ accountId: string; adapterId: string; model: string; fallbackIndex: number }>;
  exclusions: Record<string, string>;
  policyVersion: number;
}
