"use client";

import { useCallback, useEffect, useState } from "react";
import { useI18n } from "@/i18n/catalog";
import { useWorkspace } from "@/features/workspaces/WorkspaceProvider";
import { assetsApi } from "./api";
import type { ManagedAsset } from "./types";

export function AssetLibrary({ onSelect }: { onSelect?: (asset: ManagedAsset) => void }) {
  const { t } = useI18n();
  const workspace = useWorkspace();
  const [assets, setAssets] = useState<ManagedAsset[]>([]);
  const [state, setState] = useState("");
  const [mime, setMime] = useState("");
  const [notice, setNotice] = useState<string | null>(null);
  const [busy, setBusy] = useState<string | null>(null);
  const [retryFile, setRetryFile] = useState<File | null>(null);

  const reload = useCallback(async () => {
    try { setAssets(await assetsApi.list(state || undefined, mime || undefined)); setNotice(null); }
    catch { setNotice(t("assets.loadError")); }
  }, [mime, state, t]);

  useEffect(() => { void reload(); }, [reload]);
  useEffect(() => {
    if (!assets.some((asset) => ["UPLOADING", "QUARANTINED", "SCANNING", "DELETING"].includes(asset.state))) return;
    const timer = window.setInterval(() => void reload(), 3000);
    return () => window.clearInterval(timer);
  }, [assets, reload]);

  const upload = async (file: File) => {
    setRetryFile(file); setBusy("upload"); setNotice(null);
    try { await assetsApi.upload(file); setRetryFile(null); await reload(); }
    catch { setNotice(t("assets.uploadFailed")); }
    finally { setBusy(null); }
  };

  return (
    <main className="mx-auto w-full max-w-6xl p-6" aria-labelledby="assets-title">
      <div className="mb-6 flex flex-wrap items-end justify-between gap-4">
        <div><h1 id="assets-title" className="text-2xl font-semibold">{t("assets.title")}</h1><p className="mt-1 text-sm text-slate-600">{t("assets.description")}</p></div>
        {workspace.can("assets:write") && <label className="cursor-pointer rounded-md bg-violet-700 px-4 py-2 text-sm text-white">
          {busy === "upload" ? t("assets.uploading") : t("assets.upload")}
          <input className="sr-only" type="file" disabled={busy === "upload"} onChange={(event) => { const file = event.target.files?.[0]; if (file) void upload(file); }} />
        </label>}
      </div>
      <div className="mb-5 flex flex-wrap gap-3">
        <select aria-label={t("assets.filterState")} value={state} onChange={(event) => setState(event.target.value)} className="rounded-md border px-3 py-2 text-sm">
          <option value="">{t("assets.allStates")}</option>{["READY", "QUARANTINED", "SCANNING", "REJECTED"].map((value) => <option key={value} value={value}>{t(`assets.state.${value.toLowerCase()}`)}</option>)}
        </select>
        <select aria-label={t("assets.filterType")} value={mime} onChange={(event) => setMime(event.target.value)} className="rounded-md border px-3 py-2 text-sm">
          <option value="">{t("assets.allTypes")}</option><option value="image/">{t("assets.images")}</option><option value="application/">{t("assets.documents")}</option><option value="text/">{t("assets.text")}</option>
        </select>
      </div>
      {notice && <div role="alert" className="mb-4 rounded-md bg-red-50 p-3 text-sm text-red-800">{notice}{retryFile && <button className="ms-3 underline" onClick={() => void upload(retryFile)}>{t("assets.retry")}</button>}</div>}
      <ul className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-3">
        {assets.map((asset) => <li key={asset.id} className="rounded-lg border bg-white p-4 shadow-sm">
          <div className="aspect-video rounded-md bg-slate-100 p-3 text-center text-sm text-slate-500" role="img" aria-label={asset.accessibilityMetadata.alt ?? asset.filename ?? t("assets.unnamed")}>
            {(asset.detectedMime ?? asset.declaredMime)?.startsWith("image/") ? t("assets.imagePreviewProtected") : (asset.detectedMime ?? asset.declaredMime ?? t("assets.unknownType"))}
          </div>
          <p className="mt-3 truncate font-medium" title={asset.filename ?? undefined}>{asset.filename ?? t("assets.unnamed")}</p>
          <div className="mt-1 flex justify-between gap-2 text-xs text-slate-600"><span>{t(`assets.state.${asset.state.toLowerCase()}`)}</span><span>{(asset.size / 1024).toFixed(1)} KB</span></div>
          <div className="mt-4 flex flex-wrap gap-2 text-sm">
            {asset.state === "READY" && <button className="text-violet-700" onClick={() => onSelect ? onSelect(asset) : void assetsApi.download(asset.id)}>{onSelect ? t("assets.select") : t("assets.download")}</button>}
            {workspace.can("assets:write") && asset.state === "READY" && <label className="cursor-pointer text-violet-700">{t("assets.replace")}<input type="file" className="sr-only" onChange={async (event) => { const file = event.target.files?.[0]; if (file) { setBusy(asset.id); try { await assetsApi.replace(asset.id, file); await reload(); } catch { setNotice(t("assets.replaceFailed")); } finally { setBusy(null); } } }} /></label>}
            {workspace.can("assets:write") && asset.state === "READY" && <button className="text-red-700" onClick={async () => { try { await assetsApi.delete(asset.id); await reload(); } catch { setNotice(t("assets.deleteBlocked")); } }}>{t("assets.delete")}</button>}
          </div>
        </li>)}
        {assets.length === 0 && <li className="col-span-full rounded-lg border border-dashed p-8 text-center text-slate-600">{t("assets.empty")}</li>}
      </ul>
    </main>
  );
}
