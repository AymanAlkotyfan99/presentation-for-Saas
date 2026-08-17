"use client";

import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { ArrowRight, LayoutGrid, List, Loader2, Plus, Search, Sparkles } from "lucide-react";
import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";

import { PresentationGrid } from "./PresentationGrid";
import { LegacyPresentationsTable } from "./LegacyPresentationsTable";
import { ProductOnboarding } from "./ProductOnboarding";
import { DashboardApi, type PresentationResponse } from "@/app/(presentation-generator)/services/api/dashboard";
import { PresentationGenerationApi } from "@/app/(presentation-generator)/services/api/presentation-generation";
import { notify } from "@/components/ui/sonner";
import { useI18n } from "@/i18n/catalog";
import { localizePathname } from "@/i18n/routing";
import { sanitizeAnalyticsError } from "@/utils/analytics";
import { MixpanelEvent, trackEvent } from "@/utils/mixpanel";

type DashboardPageProps = { mode?: "dashboard" | "library"; username?: string };
type SortMode = "updated" | "created" | "title";
const PAGE_SIZE = 12;

function byDate(value: string | undefined): number {
  const parsed = Date.parse(value || "");
  return Number.isNaN(parsed) ? 0 : parsed;
}

function sortPresentations(items: PresentationResponse[], sort: SortMode) {
  return [...items].sort((left, right) => {
    if (sort === "title") return (left.title || "").localeCompare(right.title || "");
    if (sort === "created") return byDate(right.created_at) - byDate(left.created_at);
    return byDate(right.updated_at || right.created_at) - byDate(left.updated_at || left.created_at);
  });
}

export default function DashboardPage({ mode = "dashboard", username }: DashboardPageProps) {
  const { locale, t } = useI18n();
  const pathname = usePathname() || "/";
  const router = useRouter();
  const [presentations, setPresentations] = useState<PresentationResponse[]>([]);
  const [legacyPresentations, setLegacyPresentations] = useState<PresentationResponse[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [isCreatingBlank, setIsCreatingBlank] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [viewMode, setViewMode] = useState<"grid" | "list">("grid");
  const [search, setSearch] = useState("");
  const [sort, setSort] = useState<SortMode>("updated");
  const [visibleCount, setVisibleCount] = useState(PAGE_SIZE);
  const blankRequest = useRef(false);

  const fetchPresentations = useCallback(async () => {
    setIsLoading(true);
    setError(null);
    try {
      const [supported, legacy] = await Promise.all([
        DashboardApi.getPresentations("v2-standard"),
        DashboardApi.getPresentations("v1-standard", { includeSlides: false }),
      ]);
      setPresentations(supported);
      setLegacyPresentations(legacy);
      trackEvent(MixpanelEvent.Dashboard_Page_Viewed, { pathname, presentation_count: supported.length + legacy.length, load_failed: false });
    } catch (cause) {
      console.error("Dashboard presentation load failed", cause);
      setError(t("dashboard.loadFailedDescription"));
      trackEvent(MixpanelEvent.Dashboard_Page_Viewed, { pathname, presentation_count: 0, load_failed: true, error_message: sanitizeAnalyticsError(cause, "Presentation load failed") });
    } finally {
      setIsLoading(false);
    }
  }, [pathname, t]);

  useEffect(() => void fetchPresentations(), [fetchPresentations]);
  useEffect(() => setVisibleCount(PAGE_SIZE), [search, sort]);

  const filtered = useMemo(() => {
    const query = search.trim().toLocaleLowerCase(locale);
    const matching = query
      ? presentations.filter((item) => `${item.title || ""} ${item.prompt || ""}`.toLocaleLowerCase(locale).includes(query))
      : presentations;
    return sortPresentations(matching, sort);
  }, [locale, presentations, search, sort]);
  const shownPresentations = mode === "dashboard" ? filtered.slice(0, 4) : filtered.slice(0, visibleCount);

  const createBlankPresentation = useCallback(async () => {
    if (blankRequest.current) return;
    blankRequest.current = true;
    setIsCreatingBlank(true);
    try {
      const presentation = await PresentationGenerationApi.createBlankPresentation();
      router.push(`${localizePathname("/presentation", locale)}?id=${encodeURIComponent(presentation.id)}&type=standard`);
    } catch (cause) {
      console.error("Blank presentation creation failed", cause);
      notify.error(t("dashboard.createFailedTitle"), t("dashboard.createFailed"), { id: "blank-presentation-failed" });
    } finally {
      blankRequest.current = false;
      setIsCreatingBlank(false);
    }
  }, [locale, router, t]);

  const removePresentation = (presentationId: string) => {
    setPresentations((items) => items.filter((item) => item.id !== presentationId));
    setLegacyPresentations((items) => items.filter((item) => item.id !== presentationId));
  };
  const removeLegacyPresentations = (presentationIds: string[]) => {
    const deleted = new Set(presentationIds);
    setLegacyPresentations((items) => items.filter((item) => !deleted.has(item.id)));
  };

  return (
    <div className="space-y-8">
      {mode === "dashboard" ? (
        <>
          <ProductOnboarding />
          <section className="relative overflow-hidden rounded-[24px] bg-[#17142B] px-6 py-8 text-white shadow-[0_18px_50px_rgba(24,20,46,0.14)] sm:px-8 sm:py-10 lg:px-10" aria-labelledby="dashboard-welcome-heading">
            <div className="absolute -end-20 -top-28 h-72 w-72 rounded-full bg-[#7758F6]/35 blur-3xl" aria-hidden="true" />
            <div className="absolute -bottom-24 end-36 h-56 w-56 rounded-full bg-[#42C9B8]/15 blur-3xl" aria-hidden="true" />
            <div className="relative max-w-2xl">
              <p className="mb-3 inline-flex items-center gap-2 text-xs font-bold uppercase tracking-[0.12em] text-[#C9BEFF]"><Sparkles className="h-4 w-4" aria-hidden="true" />Bayanly</p>
              <h2 id="dashboard-welcome-heading" className="text-3xl font-semibold tracking-[-0.04em] sm:text-4xl">{username ? t("dashboard.welcome", { name: username }) : t("dashboard.welcomeGeneric")}</h2>
              <p className="mt-3 text-sm leading-6 text-white/70 sm:text-base">{t("dashboard.welcomeDescription")}</p>
              <div className="mt-7 flex flex-col gap-3 sm:flex-row">
                <Link href={localizePathname("/create", locale)} className="inline-flex min-h-12 items-center justify-center gap-2 rounded-xl bg-white px-5 text-sm font-semibold text-[#3F2BAF] transition hover:-translate-y-0.5 hover:bg-[#F7F5FF] focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-white focus-visible:ring-offset-2 focus-visible:ring-offset-[#17142B] motion-reduce:transform-none"><Plus className="h-4 w-4" aria-hidden="true" />{t("navigation.create")}</Link>
                <button type="button" onClick={() => void createBlankPresentation()} disabled={isCreatingBlank} className="inline-flex min-h-12 items-center justify-center gap-2 rounded-xl border border-white/20 bg-white/5 px-5 text-sm font-semibold text-white transition hover:bg-white/10 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-white disabled:opacity-60">
                  {isCreatingBlank ? <Loader2 className="h-4 w-4 animate-spin" aria-hidden="true" /> : <LayoutGrid className="h-4 w-4" aria-hidden="true" />}{isCreatingBlank ? t("dashboard.creatingBlank") : t("dashboard.createBlank")}
                </button>
              </div>
            </div>
          </section>
        </>
      ) : (
        <header className="max-w-2xl">
          <p className="text-xs font-bold uppercase tracking-[0.12em] text-[#6F4EF6]">{t("navigation.presentations")}</p>
          <h2 className="mt-2 text-3xl font-semibold tracking-[-0.04em] text-[#171A24] sm:text-4xl">{t("dashboard.allPresentations")}</h2>
          <p className="mt-3 text-sm leading-6 text-[#667085] sm:text-base">{t("dashboard.libraryDescription")}</p>
        </header>
      )}

      <section className="rounded-[20px] border border-[#E7E7ED] bg-white p-4 shadow-[0_10px_35px_rgba(36,31,65,0.04)] sm:p-6" aria-labelledby="presentation-library-heading">
        <div className="mb-6 flex flex-col gap-4 lg:flex-row lg:items-center lg:justify-between">
          <div><h2 id="presentation-library-heading" className="text-xl font-semibold tracking-[-0.02em] text-[#20232D]">{mode === "dashboard" ? t("dashboard.recent") : t("dashboard.title")}</h2>{!isLoading && !error && <p className="mt-1 text-xs text-[#7A8190]">{t("dashboard.allPresentations")} · {presentations.length}</p>}</div>
          <div className="flex flex-col gap-2 sm:flex-row sm:items-center">
            {mode === "library" && <>
              <label className="relative block min-w-0 sm:w-64"><span className="sr-only">{t("dashboard.searchPlaceholder")}</span><Search className="pointer-events-none absolute start-3 top-1/2 h-4 w-4 -translate-y-1/2 text-[#8A90A0]" aria-hidden="true" /><input value={search} onChange={(event) => setSearch(event.target.value)} placeholder={t("dashboard.searchPlaceholder")} className="min-h-11 w-full rounded-xl border border-[#DDE0E6] bg-[#FAFAFC] pe-3 ps-10 text-sm outline-none transition focus:border-[#8D79F6] focus:bg-white focus:ring-2 focus:ring-[#6F4EF6]/15" /></label>
              <select value={sort} onChange={(event) => setSort(event.target.value as SortMode)} aria-label={t("dashboard.sortLabel")} className="min-h-11 rounded-xl border border-[#DDE0E6] bg-[#FAFAFC] px-3 text-sm outline-none transition focus:border-[#8D79F6] focus:ring-2 focus:ring-[#6F4EF6]/15"><option value="updated">{t("dashboard.sortUpdated")}</option><option value="created">{t("dashboard.sortCreated")}</option><option value="title">{t("dashboard.sortTitle")}</option></select>
            </>}
            <div className="flex rounded-xl border border-[#DDE0E6] bg-[#FAFAFC] p-1">
              <button type="button" onClick={() => setViewMode("grid")} aria-pressed={viewMode === "grid"} aria-label={t("dashboard.gridView")} className={`flex h-9 w-9 items-center justify-center rounded-lg transition focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[#6F4EF6] ${viewMode === "grid" ? "bg-white text-[#5538D7] shadow-sm" : "text-[#7A8190]"}`}><LayoutGrid className="h-4 w-4" /></button>
              <button type="button" onClick={() => setViewMode("list")} aria-pressed={viewMode === "list"} aria-label={t("dashboard.listView")} className={`flex h-9 w-9 items-center justify-center rounded-lg transition focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[#6F4EF6] ${viewMode === "list" ? "bg-white text-[#5538D7] shadow-sm" : "text-[#7A8190]"}`}><List className="h-4 w-4" /></button>
            </div>
          </div>
        </div>

        <PresentationGrid presentations={shownPresentations} viewMode={viewMode} isLoading={isLoading} error={error} searchActive={Boolean(search.trim())} onRetry={() => void fetchPresentations()} onClearSearch={() => setSearch("")} onPresentationDeleted={removePresentation} onPresentationDuplicated={(presentation) => setPresentations((items) => [presentation, ...items])} />

        {mode === "dashboard" && !isLoading && !error && presentations.length > 4 && <div className="mt-6 flex justify-center border-t border-[#EEEEF2] pt-5"><Link href={localizePathname("/presentations", locale)} className="inline-flex min-h-10 items-center gap-2 rounded-xl px-4 text-sm font-semibold text-[#5538D7] transition hover:bg-[#F5F2FF] focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[#6F4EF6]">{t("dashboard.allPresentations")}<ArrowRight className="rtl-flip h-4 w-4" /></Link></div>}
        {mode === "library" && visibleCount < filtered.length && <div className="mt-6 flex justify-center border-t border-[#EEEEF2] pt-5"><button type="button" onClick={() => setVisibleCount((count) => count + PAGE_SIZE)} className="min-h-10 rounded-xl border border-[#D9D4F8] bg-[#F7F5FF] px-5 text-sm font-semibold text-[#5538D7] hover:bg-[#F0EDFF] focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[#6F4EF6]">{t("dashboard.loadMore")}</button></div>}
      </section>

      {mode === "library" && !isLoading && legacyPresentations.length > 0 && <section className="rounded-[20px] border border-[#E7E7ED] bg-white p-4 sm:p-6"><LegacyPresentationsTable presentations={sortPresentations(legacyPresentations, "created")} onPresentationsDeleted={removeLegacyPresentations} /></section>}
    </div>
  );
}
