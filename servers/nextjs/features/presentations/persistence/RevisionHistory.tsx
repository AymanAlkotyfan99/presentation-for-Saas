"use client";

import { useEffect, useState } from "react";
import { useI18n } from "@/i18n/catalog";
import { persistenceFeatureFlags } from "./feature-flags";
import { RevisionClient } from "./revision-client";
import type { RevisionEnvelope } from "./types";

export function RevisionHistory({
  presentationId,
  currentRevision,
  onRestored,
}: {
  presentationId: string;
  currentRevision: number;
  onRestored: (revision: RevisionEnvelope) => void;
}) {
  const { t } = useI18n();
  const [items, setItems] = useState<Array<Omit<RevisionEnvelope, "document">>>([]);
  const [error, setError] = useState(false);
  const flags = persistenceFeatureFlags();
  useEffect(() => {
    if (!flags.versionHistory) return;
    new RevisionClient().history(presentationId).then(setItems).catch(() => setError(true));
  }, [flags.versionHistory, presentationId]);
  if (!flags.versionHistory) return null;
  const restore = async (revision: number) => {
    try {
      const restored = await new RevisionClient().restore(presentationId, revision, currentRevision, crypto.randomUUID());
      onRestored(restored);
    } catch { setError(true); }
  };
  return <aside aria-label={t("presentation.revisionHistory")} className="space-y-2">
    <h2>{t("presentation.revisionHistory")}</h2>
    {error && <p role="alert">{t("presentation.revisionHistoryError")}</p>}
    <ol>{items.map((item) => <li key={item.revision} className="flex justify-between gap-2">
      <span>{t("presentation.revisionNumber", { count: item.revision })}</span>
      <button type="button" disabled={item.revision === currentRevision} onClick={() => void restore(item.revision)}>{t("presentation.revisionRestore")}</button>
    </li>)}</ol>
  </aside>;
}
