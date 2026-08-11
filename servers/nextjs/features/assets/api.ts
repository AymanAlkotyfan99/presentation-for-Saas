import { getApiUrl } from "@/utils/api";
import type { ManagedAsset, UploadOrchestration } from "./types";

async function json<T>(path: string, init: RequestInit = {}): Promise<T> {
  const response = await fetch(getApiUrl(`/api/v1/assets${path}`), {
    ...init,
    credentials: "include",
    headers: { "Content-Type": "application/json", ...init.headers },
  });
  if (!response.ok) {
    const payload = await response.json().catch(() => ({}));
    throw new Error(payload.message ?? payload.detail ?? "Asset request failed");
  }
  return response.status === 204 ? (undefined as T) : response.json();
}

async function checksum(file: File): Promise<string> {
  const digest = await crypto.subtle.digest("SHA-256", await file.arrayBuffer());
  return Array.from(new Uint8Array(digest), (value) => value.toString(16).padStart(2, "0")).join("");
}

async function transfer(orchestration: UploadOrchestration, file: File): Promise<ManagedAsset> {
  const target = orchestration.directUpload;
  const response = target
    ? await fetch(target.url, { method: target.method, headers: target.headers, body: file })
    : await fetch(getApiUrl(`/api/v1/assets/uploads/${orchestration.uploadSessionId}/content`), {
        method: "PUT", credentials: "include", headers: { "Content-Type": file.type }, body: file,
      });
  if (!response.ok) throw new Error("Asset upload failed");
  return json<ManagedAsset>(`/uploads/${orchestration.uploadSessionId}/complete`, { method: "POST" });
}

async function create(file: File, path: string): Promise<UploadOrchestration> {
  return json<UploadOrchestration>(path, {
    method: "POST",
    body: JSON.stringify({ filename: file.name, mimeType: file.type, size: file.size, checksumSha256: await checksum(file), multipart: false }),
  });
}

export const assetsApi = {
  list: (state?: string, mimePrefix?: string) => {
    const query = new URLSearchParams({ limit: "100" });
    if (state) query.set("state", state);
    if (mimePrefix) query.set("mime_prefix", mimePrefix);
    return json<ManagedAsset[]>(`?${query.toString()}`);
  },
  upload: async (file: File) => transfer(await create(file, "/uploads"), file),
  replace: async (assetId: string, file: File) => transfer(await create(file, `/${encodeURIComponent(assetId)}/replacements`), file),
  delete: (assetId: string) => json<{ jobId: string }>(`/${encodeURIComponent(assetId)}`, { method: "DELETE" }),
  thumbnail: (assetId: string) => json<{ jobId: string }>(`/${encodeURIComponent(assetId)}/thumbnail`, { method: "POST" }),
  download: async (assetId: string) => {
    const capability = await json<{ url: string }>(`/${encodeURIComponent(assetId)}/download-capability`, { method: "POST" });
    window.location.assign(/^https?:\/\//i.test(capability.url) ? capability.url : getApiUrl(capability.url));
  },
};
