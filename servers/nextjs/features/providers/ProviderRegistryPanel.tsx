"use client";

import { useCallback, useEffect, useMemo, useState } from "react";
import { Loader2, RefreshCw, ShieldAlert } from "lucide-react";
import { notify } from "@/components/ui/sonner";
import { useTranslations } from "@/i18n/catalog";
import { providersApi } from "./api";
import type { CapabilityFamily, ProviderAccount, ProviderAdapterDescriptor, RegionPolicyStatus } from "./types";

const families: CapabilityFamily[] = ["TEXT", "IMAGE", "SEARCH"];
const catalogSegment = (value: string) => value.toLowerCase().replace(/_([a-z])/g, (_, letter: string) => letter.toUpperCase());
type AccountDraft = { name: string; model: string; models: string; safeConfig: string; region: RegionPolicyStatus; enabled: boolean };

const accountDraft = (account: ProviderAccount): AccountDraft => ({
  name: account.name,
  model: account.defaultModel ?? "default",
  models: account.capabilities.filter((item) => item.enabled).map((item) => item.model).join(", "),
  safeConfig: JSON.stringify(account.safeConfig ?? {}, null, 2),
  region: account.regionPolicyStatus,
  enabled: account.enabled,
});

const parseSafeConfig = (value: string): Record<string, string | number | boolean | null> => {
  const parsed: unknown = JSON.parse(value || "{}");
  if (!parsed || Array.isArray(parsed) || typeof parsed !== "object") throw new Error("invalid safe config");
  return parsed as Record<string, string | number | boolean | null>;
};

export function ProviderRegistryPanel() {
  const t = useTranslations();
  const [adapters, setAdapters] = useState<ProviderAdapterDescriptor[]>([]);
  const [accounts, setAccounts] = useState<ProviderAccount[]>([]);
  const [loading, setLoading] = useState(true);
  const [unavailable, setUnavailable] = useState(false);
  const [adapterId, setAdapterId] = useState("");
  const [name, setName] = useState("");
  const [model, setModel] = useState("default");
  const [secret, setSecret] = useState("");
  const [safeConfig, setSafeConfig] = useState("{}");
  const [regionStatus, setRegionStatus] = useState<RegionPolicyStatus>("ADMIN_REVIEW");
  const [busy, setBusy] = useState<string | null>(null);
  const [rotation, setRotation] = useState<Record<string, string>>({});
  const [policyFamily, setPolicyFamily] = useState<CapabilityFamily>("TEXT");
  const [allowFallback, setAllowFallback] = useState(false);
  const [maxFallbacks, setMaxFallbacks] = useState(0);
  const [priorityIds, setPriorityIds] = useState<string[]>([]);
  const [pinnedAccountId, setPinnedAccountId] = useState("");
  const [simulation, setSimulation] = useState("");
  const [drafts, setDrafts] = useState<Record<string, AccountDraft>>({});

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const [nextAdapters, nextAccounts] = await Promise.all([providersApi.adapters(), providersApi.accounts()]);
      setAdapters(nextAdapters);
      setAccounts(nextAccounts);
      setDrafts(Object.fromEntries(nextAccounts.map((account) => [account.id, accountDraft(account)])));
      setAdapterId((current) => current || nextAdapters[0]?.adapterId || "");
      setUnavailable(false);
    } catch (error) {
      setUnavailable((error as Error & { status?: number }).status === 404);
      if ((error as Error & { status?: number }).status !== 404) notify.error(t("providers.loadError"));
    } finally {
      setLoading(false);
    }
  }, [t]);

  useEffect(() => { void load(); }, [load]);
  useEffect(() => {
    if (unavailable) return;
    void providersApi.policy(policyFamily).then((policy) => {
      setAllowFallback(policy?.allow_fallback ?? false);
      setMaxFallbacks(policy?.max_fallbacks ?? 0);
      const available = accounts.filter((account) => account.capabilities.some((capability) => capability.family === policyFamily)).map((account) => account.id);
      const configured = (policy?.priority_account_ids ?? []).filter((id) => available.includes(id));
      setPriorityIds([...configured, ...available.filter((id) => !configured.includes(id))]);
      setPinnedAccountId((current) => available.includes(current) ? current : available[0] ?? "");
    }).catch(() => undefined);
  }, [accounts, policyFamily, unavailable]);

  const selectedAdapter = useMemo(() => adapters.find((item) => item.adapterId === adapterId), [adapterId, adapters]);
  const policyAccounts = accounts.filter((account) => account.capabilities.some((capability) => capability.family === policyFamily));

  const statusReason = (account: ProviderAccount) => {
    if (account.emergencyDisabled || !account.enabled) return t("providers.unavailablePolicy");
    if (["BLOCKED", "UNKNOWN", "ADMIN_REVIEW"].includes(account.regionPolicyStatus)) return t(`providers.region.${catalogSegment(account.regionPolicyStatus)}`);
    if (!account.hasSecret && adapters.find((item) => item.adapterId === account.adapterId)?.metadata.secretRequired) return t("providers.credentialsMissing");
    if (account.health?.status === "UNHEALTHY") return t("providers.unhealthy");
    return t(`providers.health.${(account.health?.status ?? "UNKNOWN").toLowerCase()}`);
  };

  const create = async () => {
    if (!adapterId || !name.trim() || !model.trim()) return;
    setBusy("create");
    try {
      await providersApi.create({ adapterId, name: name.trim(), defaultModel: model.trim(), capabilityModels: [model.trim()], safeConfig: parseSafeConfig(safeConfig), regionPolicyStatus: regionStatus, ...(secret ? { secret } : {}) });
      setName(""); setSecret(""); setSafeConfig("{}"); await load(); notify.success(t("providers.created"));
    } catch { notify.error(t("providers.saveError")); } finally { setBusy(null); }
  };

  const act = async (id: string, action: () => Promise<unknown>, message: string) => {
    setBusy(id);
    try { await action(); await load(); notify.success(message); } catch { notify.error(t("providers.saveError")); } finally { setBusy(null); }
  };

  const movePriority = (id: string, offset: number) => {
    setPriorityIds((current) => {
      const index = current.indexOf(id);
      const target = index + offset;
      if (index < 0 || target < 0 || target >= current.length) return current;
      const next = [...current];
      [next[index], next[target]] = [next[target], next[index]];
      return next;
    });
  };

  const saveAccount = async (account: ProviderAccount) => {
    const draft = drafts[account.id] ?? accountDraft(account);
    const capabilityModels = draft.models.split(",").map((value) => value.trim()).filter(Boolean);
    if (!draft.name.trim() || !draft.model.trim() || !capabilityModels.length) return;
    await act(account.id, () => providersApi.update(account.id, {
      name: draft.name.trim(),
      defaultModel: draft.model.trim(),
      capabilityModels,
      safeConfig: parseSafeConfig(draft.safeConfig),
      regionPolicyStatus: draft.region,
      enabled: draft.enabled,
    }), t("providers.updated"));
  };

  if (loading) return <div className="flex items-center gap-2 p-8"><Loader2 className="h-4 w-4 animate-spin" />{t("providers.loading")}</div>;
  if (unavailable) return <div className="max-w-2xl rounded-2xl border border-amber-200 bg-amber-50 p-6 text-sm text-amber-900"><ShieldAlert className="mb-3 h-5 w-5" />{t("providers.rolloutDisabled")}</div>;

  return (
    <div className="max-h-[calc(100vh-130px)] overflow-y-auto pe-6 pb-24" dir="auto">
      <div className="mb-6 flex items-start justify-between"><div><h4 className="font-unbounded text-lg">{t("providers.title")}</h4><p className="mt-2 text-sm text-[#494A4D]">{t("providers.description")}</p></div><button onClick={() => void load()} aria-label={t("providers.refresh")} className="rounded-full border p-2"><RefreshCw className="h-4 w-4" /></button></div>

      <section className="mb-7 rounded-2xl border border-[#EDEEEF] bg-white p-5">
        <h5 className="font-semibold">{t("providers.addAccount")}</h5>
        <div className="mt-4 grid gap-3 md:grid-cols-2">
          <select value={adapterId} onChange={(event) => setAdapterId(event.target.value)} className="rounded-lg border p-3 text-sm">{adapters.map((adapter) => <option key={adapter.adapterId} value={adapter.adapterId}>{adapter.adapterId} · {adapter.family}</option>)}</select>
          <input value={name} onChange={(event) => setName(event.target.value)} placeholder={t("providers.accountName")} className="rounded-lg border p-3 text-sm" />
          <input value={model} onChange={(event) => setModel(event.target.value)} placeholder={t("providers.model")} className="rounded-lg border p-3 text-sm" />
          <input type="password" value={secret} onChange={(event) => setSecret(event.target.value)} placeholder={selectedAdapter?.metadata.secretRequired ? t("providers.secretRequired") : t("providers.secretOptional")} autoComplete="new-password" className="rounded-lg border p-3 text-sm" />
          <textarea value={safeConfig} onChange={(event) => setSafeConfig(event.target.value)} aria-label={t("providers.safeConfig")} placeholder={t("providers.safeConfig")} className="min-h-20 rounded-lg border p-3 font-mono text-xs" />
          <select value={regionStatus} onChange={(event) => setRegionStatus(event.target.value as RegionPolicyStatus)} className="rounded-lg border p-3 text-sm"><option value="ALLOWED">{t("providers.region.allowed")}</option><option value="ADMIN_REVIEW">{t("providers.region.adminReview")}</option><option value="UNKNOWN">{t("providers.region.unknown")}</option><option value="BLOCKED">{t("providers.region.blocked")}</option></select>
          <button disabled={busy === "create"} onClick={() => void create()} className="rounded-lg bg-[#7C51F8] p-3 text-sm font-semibold text-white disabled:opacity-50">{t("providers.create")}</button>
        </div>
      </section>

      <section className="mb-7 rounded-2xl border border-[#EDEEEF] bg-white p-5">
        <h5 className="font-semibold">{t("providers.workspacePolicy")}</h5>
        <div className="mt-4 flex flex-wrap items-center gap-4">
          <select value={policyFamily} onChange={(event) => setPolicyFamily(event.target.value as CapabilityFamily)} className="rounded-lg border p-2 text-sm">{families.map((family) => <option key={family}>{family}</option>)}</select>
          <label className="flex items-center gap-2 text-sm"><input type="checkbox" checked={allowFallback} onChange={(event) => { setAllowFallback(event.target.checked); if (!event.target.checked) setMaxFallbacks(0); }} />{t("providers.allowFallback")}</label>
          <input type="number" min={0} max={3} disabled={!allowFallback} value={maxFallbacks} onChange={(event) => setMaxFallbacks(Math.min(3, Math.max(0, Number(event.target.value))))} className="w-20 rounded-lg border p-2 text-sm" />
          <button onClick={() => void act("policy", () => providersApi.savePolicy(policyFamily, { priorityAccountIds: priorityIds, allowFallback, maxFallbacks: allowFallback ? maxFallbacks : 0, regionRules: {}, planRules: {} }), t("providers.policySaved"))} className="rounded-lg border px-4 py-2 text-sm font-semibold">{t("common.save")}</button>
        </div>
        <ol className="mt-4 space-y-2" aria-label={t("providers.priorityOrder")}>
          {priorityIds.map((id, index) => {
            const account = policyAccounts.find((item) => item.id === id);
            if (!account) return null;
            return <li key={id} className="flex items-center justify-between rounded-lg border px-3 py-2 text-sm"><span>{index + 1}. {account.name}</span><span className="flex gap-1"><button aria-label={t("providers.moveUp")} disabled={index === 0} onClick={() => movePriority(id, -1)} className="rounded border px-2 disabled:opacity-40">↑</button><button aria-label={t("providers.moveDown")} disabled={index === priorityIds.length - 1} onClick={() => movePriority(id, 1)} className="rounded border px-2 disabled:opacity-40">↓</button></span></li>;
          })}
        </ol>
        <div className="mt-4 flex flex-wrap items-center gap-2">
          <select value={pinnedAccountId} onChange={(event) => setPinnedAccountId(event.target.value)} aria-label={t("providers.pinnedAccount")} className="rounded-lg border p-2 text-sm"><option value="">{t("providers.noPin")}</option>{policyAccounts.map((account) => <option key={account.id} value={account.id}>{account.name}</option>)}</select>
          <button onClick={() => void providersApi.simulate({ family: policyFamily, ...(pinnedAccountId ? { pinnedAccountId } : {}) }).then((value) => setSimulation(value.candidates.map((item) => `${item.fallbackIndex + 1}. ${item.adapterId} · ${item.model}`).join("; ") || Object.values(value.exclusions).join("; "))).catch(() => notify.error(t("providers.saveError")))} className="rounded-lg border px-4 py-2 text-sm">{t("providers.simulate")}</button>
          {simulation && <output className="text-xs text-[#667085]">{simulation}</output>}
        </div>
        <p className="mt-3 text-xs text-[#667085]">{t("providers.fallbackBounded")}</p>
      </section>

      <div className="space-y-4">{accounts.length === 0 ? <p className="rounded-2xl border p-6 text-sm">{t("providers.empty")}</p> : accounts.map((account) => (
        <article key={account.id} className="rounded-2xl border border-[#EDEEEF] bg-white p-5">
          <div className="flex flex-wrap items-start justify-between gap-3"><div><h5 className="font-semibold">{account.name}</h5><p className="text-xs text-[#667085]">{account.adapterId} · {account.defaultModel ?? "default"}</p></div><span className="rounded-full bg-[#F4F3FF] px-3 py-1 text-xs">{statusReason(account)}</span></div>
          <div className="mt-4 grid gap-3 md:grid-cols-[1fr_auto_auto]">
            <input type="password" value={rotation[account.id] ?? ""} onChange={(event) => setRotation((current) => ({ ...current, [account.id]: event.target.value }))} placeholder={account.maskedSecret ?? t("providers.newSecret")} autoComplete="new-password" className="rounded-lg border p-2 text-sm" />
            <button disabled={!rotation[account.id] || busy === account.id} onClick={() => void act(account.id, () => providersApi.rotateSecret(account.id, rotation[account.id]), t("providers.rotated"))} className="rounded-lg border px-3 text-xs disabled:opacity-50">{t("providers.rotate")}</button>
            <button disabled={!account.hasSecret || busy === account.id} onClick={() => void act(account.id, () => providersApi.deleteSecret(account.id), t("providers.deleted"))} className="rounded-lg border px-3 text-xs text-red-700 disabled:opacity-50">{t("providers.deleteSecret")}</button>
          </div>
          <div className="mt-4 grid gap-3 rounded-xl bg-[#FAFAFB] p-3 md:grid-cols-2">
            <input value={(drafts[account.id] ?? accountDraft(account)).name} onChange={(event) => setDrafts((current) => ({ ...current, [account.id]: { ...(current[account.id] ?? accountDraft(account)), name: event.target.value } }))} aria-label={t("providers.accountName")} className="rounded-lg border p-2 text-sm" />
            <input value={(drafts[account.id] ?? accountDraft(account)).model} onChange={(event) => setDrafts((current) => ({ ...current, [account.id]: { ...(current[account.id] ?? accountDraft(account)), model: event.target.value } }))} aria-label={t("providers.defaultModel")} className="rounded-lg border p-2 text-sm" />
            <input value={(drafts[account.id] ?? accountDraft(account)).models} onChange={(event) => setDrafts((current) => ({ ...current, [account.id]: { ...(current[account.id] ?? accountDraft(account)), models: event.target.value } }))} aria-label={t("providers.capabilityModels")} className="rounded-lg border p-2 text-sm" />
            <select value={(drafts[account.id] ?? accountDraft(account)).region} onChange={(event) => setDrafts((current) => ({ ...current, [account.id]: { ...(current[account.id] ?? accountDraft(account)), region: event.target.value as RegionPolicyStatus } }))} aria-label={t("providers.regionPolicy")} className="rounded-lg border p-2 text-sm"><option value="ALLOWED">{t("providers.region.allowed")}</option><option value="ADMIN_REVIEW">{t("providers.region.adminReview")}</option><option value="UNKNOWN">{t("providers.region.unknown")}</option><option value="BLOCKED">{t("providers.region.blocked")}</option></select>
            <textarea value={(drafts[account.id] ?? accountDraft(account)).safeConfig} onChange={(event) => setDrafts((current) => ({ ...current, [account.id]: { ...(current[account.id] ?? accountDraft(account)), safeConfig: event.target.value } }))} aria-label={t("providers.safeConfig")} className="min-h-20 rounded-lg border p-2 font-mono text-xs" />
            <div className="flex flex-col justify-between gap-3"><label className="flex items-center gap-2 text-sm"><input type="checkbox" checked={(drafts[account.id] ?? accountDraft(account)).enabled} onChange={(event) => setDrafts((current) => ({ ...current, [account.id]: { ...(current[account.id] ?? accountDraft(account)), enabled: event.target.checked } }))} />{t("providers.accountEnabled")}</label><button disabled={busy === account.id} onClick={() => void saveAccount(account)} className="rounded-lg border px-3 py-2 text-xs font-semibold">{t("providers.saveAccount")}</button></div>
          </div>
          <div className="mt-3 flex flex-wrap gap-2">{account.capabilities.map((capability) => <label key={capability.id} className="flex items-center gap-2 rounded-full border px-3 py-1 text-xs"><input type="checkbox" checked={capability.enabled} onChange={(event) => void act(account.id, () => providersApi.setCapability(account.id, capability.id, event.target.checked), t("providers.updated"))} />{capability.family} · {capability.model}</label>)}</div>
          <div className="mt-4 flex flex-wrap gap-2"><button disabled={busy === account.id} onClick={() => void act(account.id, async () => { const job = await providersApi.test(account.id); notify.success(t("providers.testQueued"), job.jobId); }, t("providers.testQueued"))} className="rounded-lg bg-[#101323] px-4 py-2 text-xs text-white">{t("providers.test")}</button><button onClick={() => void act(account.id, () => providersApi.update(account.id, { emergencyDisabled: !account.emergencyDisabled }), t("providers.updated"))} className="rounded-lg border px-4 py-2 text-xs">{account.emergencyDisabled ? t("providers.enable") : t("providers.emergencyDisable")}</button></div>
        </article>
      ))}</div>
    </div>
  );
}
