"use client";

import { useI18n } from "@/i18n/catalog";
import type { RevisionSaveStatus } from "./types";

const messageKeys: Record<RevisionSaveStatus, string> = {
  idle: "presentation.revisionIdle",
  unsaved: "presentation.revisionUnsaved",
  saving: "presentation.revisionSaving",
  saved: "presentation.revisionSaved",
  offline: "presentation.revisionOffline",
  conflict: "presentation.revisionConflict",
  error: "presentation.revisionError",
  "read-only": "presentation.revisionReadOnly",
};

export function RevisionStatus({
  status,
  pendingCommands,
  onRetry,
  onReloadServer,
  recoveryPayload,
}: {
  status: RevisionSaveStatus;
  pendingCommands: number;
  onRetry?: () => void;
  onReloadServer?: () => void;
  recoveryPayload?: () => string;
}) {
  const { t } = useI18n();
  const download = () => {
    const payload = recoveryPayload?.();
    if (!payload) return;
    const url = URL.createObjectURL(new Blob([payload], { type: "application/json" }));
    const anchor = document.createElement("a"); anchor.href = url; anchor.download = "bayanly-recovery.json"; anchor.click();
    URL.revokeObjectURL(url);
  };
  return <div role="status" aria-live="polite" className="flex items-center gap-2 text-sm" data-save-status={status}>
    <span>{t(messageKeys[status], { count: pendingCommands })}</span>
    {(status === "offline" || status === "error") && onRetry && <button type="button" onClick={onRetry}>{t("common.retry")}</button>}
    {status === "conflict" && <>
      {onReloadServer && <button type="button" onClick={onReloadServer}>{t("presentation.revisionLoadServer")}</button>}
      {recoveryPayload && <button type="button" onClick={download}>{t("presentation.revisionDownloadRecovery")}</button>}
    </>}
  </div>;
}
