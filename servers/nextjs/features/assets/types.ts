export type AssetState = "UPLOADING" | "QUARANTINED" | "SCANNING" | "READY" | "REJECTED" | "EXPIRED" | "DELETING" | "DELETED";

export interface ManagedAsset {
  id: string;
  workspaceId: string;
  filename: string | null;
  size: number;
  declaredMime: string | null;
  detectedMime: string | null;
  checksumSha256: string | null;
  state: AssetState;
  malwareScanStatus: "PENDING" | "CLEAN" | "INFECTED" | "ERROR" | "UNAVAILABLE";
  retentionClass: "TEMPORARY" | "WORKSPACE" | "DERIVED" | "EXPORT";
  accessibilityMetadata: Record<string, string>;
  createdAt: string;
  expiresAt: string | null;
}

export interface UploadOrchestration {
  asset: ManagedAsset;
  uploadSessionId: string;
  targetVersion?: number;
  expiresAt: string;
  directUpload: null | { url: string; method: string; headers: Record<string, string>; expiresAt: string };
}
