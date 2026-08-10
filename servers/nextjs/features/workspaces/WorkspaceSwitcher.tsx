"use client";

import { Building2, UserRound } from "lucide-react";
import { useI18n } from "@/i18n/catalog";
import { useWorkspace } from "./WorkspaceProvider";

export function WorkspaceSwitcher() {
  const { t } = useI18n();
  const { available, loading, current, workspaces, error, switchWorkspace } = useWorkspace();
  if (!available) return null;
  return (
    <div className="w-full border-b border-[#E1E1E5] pb-4" aria-live="polite">
      <label className="mb-1 flex items-center justify-center gap-1 text-[10px] text-slate-600" htmlFor="workspace-switcher">
        {current?.isPersonal ? <UserRound className="h-3 w-3" /> : <Building2 className="h-3 w-3" />}
        <span>{t("workspace.current")}</span>
      </label>
      <select
        id="workspace-switcher"
        className="w-full rounded-md border border-slate-300 bg-white px-1 py-1 text-[10px] text-slate-800"
        value={current?.id ?? ""}
        disabled={loading}
        aria-label={t("workspace.switcher")}
        onChange={(event) => void switchWorkspace(event.target.value)}
      >
        {!current && <option value="">{t("workspace.loading")}</option>}
        {workspaces.map((workspace) => <option key={workspace.id} value={workspace.id}>{workspace.name}</option>)}
      </select>
      {error && <p className="mt-1 text-[9px] text-red-700" role="alert">{t("workspace.loadError")}</p>}
    </div>
  );
}
