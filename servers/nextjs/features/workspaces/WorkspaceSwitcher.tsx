"use client";

import { Building2, ChevronDown, UserRound } from "lucide-react";
import { useI18n } from "@/i18n/catalog";
import { useWorkspace } from "./WorkspaceProvider";

export function WorkspaceSwitcher() {
  const { t } = useI18n();
  const { available, loading, current, workspaces, error, switchWorkspace } = useWorkspace();
  if (!available) return null;
  return (
    <div className="w-full" aria-live="polite">
      <label className="mb-2 block text-[11px] font-semibold uppercase tracking-[0.08em] text-[#8A90A0]" htmlFor="workspace-switcher">
        {t("workspace.current")}
      </label>
      <div className="relative">
        <span className="pointer-events-none absolute inset-y-0 start-3 flex items-center text-[#6F4EF6]">
          {current?.isPersonal ? <UserRound className="h-4 w-4" /> : <Building2 className="h-4 w-4" />}
        </span>
        <select
          id="workspace-switcher"
          className="min-h-11 w-full appearance-none truncate rounded-xl border border-[#E7E7ED] bg-[#FBFBFD] py-2 pe-9 ps-10 text-sm font-medium text-[#303442] outline-none transition hover:border-[#D7D2F8] focus:border-[#A99AF8] focus:ring-2 focus:ring-[#6F4EF6]/15"
          value={current?.id ?? ""}
          disabled={loading}
          aria-label={t("workspace.switcher")}
          onChange={(event) => void switchWorkspace(event.target.value)}
        >
          {!current && <option value="">{t("workspace.loading")}</option>}
          {workspaces.map((workspace) => <option key={workspace.id} value={workspace.id}>{workspace.name}</option>)}
        </select>
        <ChevronDown className="pointer-events-none absolute end-3 top-1/2 h-4 w-4 -translate-y-1/2 text-[#8A90A0]" aria-hidden="true" />
      </div>
      {error && <p className="mt-2 text-xs text-[#B42318]" role="alert">{t("workspace.loadError")}</p>}
    </div>
  );
}
