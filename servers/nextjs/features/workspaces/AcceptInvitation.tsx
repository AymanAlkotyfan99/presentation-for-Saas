"use client";

import { useState } from "react";
import { useSearchParams } from "next/navigation";
import { useI18n } from "@/i18n/catalog";
import { workspaceApi } from "./api";
import { useWorkspace } from "./WorkspaceProvider";

export function AcceptInvitation() {
  const { t } = useI18n();
  const params = useSearchParams();
  const { refresh, switchWorkspace } = useWorkspace();
  const token = params.get("token") ?? "";
  const [state, setState] = useState<"idle" | "loading" | "accepted" | "invalid" | "expired" | "used" | "denied">("idle");

  async function accept() {
    if (!token) { setState("invalid"); return; }
    setState("loading");
    try {
      const result = await workspaceApi.acceptInvitation(token);
      await refresh();
      await switchWorkspace(result.workspaceId);
      setState("accepted");
    } catch (cause) {
      const code = (cause as { code?: string }).code;
      if (code === "INVITATION_EXPIRED" || code === "INVITATION_REVOKED") setState("expired");
      else if (code === "INVITATION_ALREADY_USED") setState("used");
      else if ((cause as { status?: number }).status === 403) setState("denied");
      else setState("invalid");
    }
  }

  const message = state === "accepted" ? t("workspace.membershipCreated")
    : state === "expired" ? t("workspace.invitationExpired")
    : state === "used" ? t("workspace.invitationUsed")
    : state === "denied" ? t("workspace.permissionDenied")
    : state === "invalid" ? t("workspace.invitationInvalid") : null;

  return <section className="mx-auto mt-20 max-w-lg rounded-xl border bg-white p-8 text-center shadow-sm">
    <h1 className="text-2xl font-semibold">{t("workspace.acceptTitle")}</h1>
    <p className="mt-3 text-slate-600">{t("workspace.acceptDescription")}</p>
    {message && <p className="mt-5 rounded-md bg-slate-100 p-3" role="status">{message}</p>}
    {state !== "accepted" && <button type="button" disabled={state === "loading"} onClick={() => void accept()} className="mt-6 rounded-md bg-violet-700 px-5 py-2 text-white disabled:opacity-60">{state === "loading" ? t("workspace.loading") : t("workspace.accept")}</button>}
  </section>;
}
