"use client";

import { useCallback, useEffect, useState } from "react";
import { useI18n } from "@/i18n/catalog";
import { localizePathname } from "@/i18n/routing";
import { workspaceApi } from "./api";
import { editableRolesFor } from "./capabilities";
import { useWorkspace } from "./WorkspaceProvider";
import type { WorkspaceInvitation, WorkspaceMember, WorkspaceRole } from "./types";

export function MembersPanel() {
  const { t, locale } = useI18n();
  const { current, can } = useWorkspace();
  const [members, setMembers] = useState<WorkspaceMember[]>([]);
  const [invitations, setInvitations] = useState<WorkspaceInvitation[]>([]);
  const [identity, setIdentity] = useState("");
  const [role, setRole] = useState<WorkspaceRole>("VIEWER");
  const [notice, setNotice] = useState<string | null>(null);
  const [invitationLink, setInvitationLink] = useState<string | null>(null);
  const mayManage = can("members:manage");
  const mayInvite = can("invitations:manage");
  const roles = editableRolesFor(current?.role ?? null);

  const reload = useCallback(async () => {
    if (!current) return;
    try {
      const nextMembers = await workspaceApi.members(current.id);
      setMembers(nextMembers);
      setInvitations(mayInvite ? await workspaceApi.invitations(current.id) : []);
    } catch (cause) {
      setNotice((cause as { status?: number }).status === 403 ? t("workspace.permissionDenied") : t("workspace.loadError"));
    }
  }, [current, mayInvite, t]);

  useEffect(() => { void reload(); }, [reload]);
  if (!current) return <p className="p-8 text-slate-600">{t("workspace.loading")}</p>;

  async function invite() {
    try {
      const created = await workspaceApi.invite(current!.id, identity, role);
      setIdentity("");
      await reload();
      const url = new URL(localizePathname("/workspace-invitation", locale), window.location.origin);
      url.searchParams.set("token", created.token);
      setInvitationLink(url.toString());
      setNotice(t("workspace.invitationCreated"));
    } catch (cause) {
      setNotice((cause as { status?: number }).status === 403 ? t("workspace.permissionDenied") : t("workspace.invitationFailed"));
    }
  }

  return (
    <section className="mx-auto max-w-4xl p-6" aria-labelledby="workspace-members-title">
      <header className="mb-6">
        <p className="text-sm text-violet-700">{current.isPersonal ? t("workspace.personal") : t("workspace.team")}</p>
        <h1 id="workspace-members-title" className="text-2xl font-semibold text-slate-950">{t("workspace.membersTitle", { name: current.name })}</h1>
      </header>
      {notice && <p className="mb-4 rounded-md bg-slate-100 p-3 text-sm" role="status">{notice}</p>}
      {invitationLink && <div className="mb-4 flex gap-2 rounded-md border border-violet-200 bg-violet-50 p-3">
        <label className="sr-only" htmlFor="invitation-link">{t("workspace.invitationLink")}</label>
        <input id="invitation-link" className="min-w-0 flex-1 bg-transparent text-sm" readOnly value={invitationLink} />
        <button type="button" className="text-sm font-medium text-violet-800" onClick={() => void navigator.clipboard.writeText(invitationLink)}>{t("workspace.copyInvitation")}</button>
      </div>}
      {mayInvite && !current.isPersonal && (
        <form className="mb-8 grid gap-3 rounded-lg border border-slate-200 p-4 sm:grid-cols-[1fr_auto_auto]" onSubmit={(event) => { event.preventDefault(); void invite(); }}>
          <label className="sr-only" htmlFor="invite-identity">{t("workspace.inviteeIdentity")}</label>
          <input id="invite-identity" required minLength={3} maxLength={128} className="rounded-md border px-3 py-2" value={identity} onChange={(event) => setIdentity(event.target.value)} placeholder={t("workspace.inviteeIdentity")} />
          <label className="sr-only" htmlFor="invite-role">{t("workspace.role")}</label>
          <select id="invite-role" className="rounded-md border px-3 py-2" value={role} onChange={(event) => setRole(event.target.value as WorkspaceRole)}>
            {roles.map((value) => <option key={value} value={value}>{t(`workspace.roles.${value.toLowerCase()}`)}</option>)}
          </select>
          <button className="rounded-md bg-violet-700 px-4 py-2 text-white" type="submit">{t("workspace.invite")}</button>
        </form>
      )}
      <h2 className="mb-3 text-lg font-medium">{t("workspace.activeMembers")}</h2>
      <ul className="divide-y rounded-lg border">
        {members.map((member) => (
          <li key={member.id} className="flex flex-wrap items-center gap-3 p-4">
            <span className="min-w-0 flex-1 truncate">{member.username}</span>
            <select aria-label={t("workspace.changeRole", { name: member.username })} className="rounded border px-2 py-1" value={member.role} disabled={!mayManage || member.role === "OWNER"} onChange={async (event) => { try { await workspaceApi.updateMember(current.id, member.userId, event.target.value as WorkspaceRole); await reload(); } catch { setNotice(t("workspace.permissionDenied")); } }}>
              {member.role === "OWNER" && <option value="OWNER">{t("workspace.roles.owner")}</option>}
              {roles.map((value) => <option key={value} value={value}>{t(`workspace.roles.${value.toLowerCase()}`)}</option>)}
            </select>
            {mayManage && member.role !== "OWNER" && <button className="text-sm text-red-700" onClick={async () => { try { await workspaceApi.removeMember(current.id, member.userId); await reload(); } catch { setNotice(t("workspace.permissionDenied")); } }}>{t("workspace.remove")}</button>}
          </li>
        ))}
      </ul>
      {mayInvite && !current.isPersonal && <>
        <h2 className="mb-3 mt-8 text-lg font-medium">{t("workspace.pendingInvitations")}</h2>
        <ul className="divide-y rounded-lg border">
          {invitations.filter((item) => !item.acceptedAt && !item.revokedAt).map((item) => <li key={item.id} className="flex items-center gap-3 p-4"><span className="min-w-0 flex-1 truncate">{item.invitedIdentity}</span><span className="text-sm text-slate-600">{t(`workspace.roles.${item.role.toLowerCase()}`)}</span><button className="text-sm text-red-700" onClick={async () => { try { await workspaceApi.revokeInvitation(current.id, item.id); await reload(); } catch { setNotice(t("workspace.permissionDenied")); } }}>{t("workspace.revoke")}</button></li>)}
          {!invitations.some((item) => !item.acceptedAt && !item.revokedAt) && <li className="p-4 text-sm text-slate-500">{t("workspace.noPendingInvitations")}</li>}
        </ul>
      </>}
    </section>
  );
}
