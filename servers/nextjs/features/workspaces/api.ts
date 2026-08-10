import { getApiUrl } from "@/utils/api";
import type { WorkspaceInvitation, WorkspaceMember, WorkspaceRole, WorkspaceSummary } from "./types";

async function request<T>(path: string, init: RequestInit = {}): Promise<T> {
  const response = await fetch(getApiUrl(`/api/v1/workspaces${path}`), {
    ...init,
    credentials: "include",
    headers: { "Content-Type": "application/json", ...init.headers },
  });
  if (!response.ok) {
    const payload = await response.json().catch(() => ({}));
    const error = new Error(payload.detail ?? "Workspace request failed") as Error & { code?: string; status?: number };
    error.code = payload.code;
    error.status = response.status;
    throw error;
  }
  return response.status === 204 ? (undefined as T) : response.json();
}

export const workspaceApi = {
  list: () => request<WorkspaceSummary[]>(""),
  current: () => request<WorkspaceSummary>("/current"),
  select: (workspaceId: string) => request<WorkspaceSummary>("/current", { method: "PUT", body: JSON.stringify({ workspaceId }) }),
  members: (workspaceId: string) => request<WorkspaceMember[]>(`/${workspaceId}/members`),
  invitations: (workspaceId: string) => request<WorkspaceInvitation[]>(`/${workspaceId}/invitations`),
  invite: (workspaceId: string, invitedIdentity: string, role: WorkspaceRole) => request<{ id: string; token: string; expiresAt: string }>(`/${workspaceId}/invitations`, { method: "POST", body: JSON.stringify({ invitedIdentity, role }) }),
  revokeInvitation: (workspaceId: string, invitationId: string) => request<void>(`/${workspaceId}/invitations/${invitationId}`, { method: "DELETE" }),
  updateMember: (workspaceId: string, userId: string, role: WorkspaceRole) => request<WorkspaceMember>(`/${workspaceId}/members/${userId}`, { method: "PATCH", body: JSON.stringify({ role }) }),
  removeMember: (workspaceId: string, userId: string) => request<void>(`/${workspaceId}/members/${userId}`, { method: "DELETE" }),
  acceptInvitation: (token: string) => request<{ workspaceId: string; role: WorkspaceRole }>("/invitations/accept", { method: "POST", body: JSON.stringify({ token }) }),
};
