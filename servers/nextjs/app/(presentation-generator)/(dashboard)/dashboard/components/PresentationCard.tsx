"use client";

import { useState } from "react";
import { Archive, AlertTriangle, CheckCircle2, Copy, Ellipsis, Loader2, Trash2 } from "lucide-react";
import { usePathname, useRouter } from "next/navigation";

import { DashboardApi, type PresentationResponse } from "@/app/(presentation-generator)/services/api/dashboard";
import SlideScale from "@/app/(presentation-generator)/components/PresentationRender";
import { shouldRenderTemplateV2HtmlPreview, TemplateV2HtmlSlidePreview } from "@/app/(presentation-generator)/components/TemplateV2HtmlSlidePreview";
import MarkdownRenderer from "@/components/MarkDownRender";
import { Dialog, DialogContent, DialogDescription, DialogFooter, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import { Popover, PopoverContent, PopoverTrigger } from "@/components/ui/popover";
import { notify } from "@/components/ui/sonner";
import { useI18n } from "@/i18n/catalog";
import { localizePathname } from "@/i18n/routing";
import { formatDate } from "@/lib/locale-format";
import { MixpanelEvent, trackEvent } from "@/utils/mixpanel";

type PresentationCardProps = {
  id: string;
  title: string;
  presentation: PresentationResponse;
  viewMode?: "grid" | "list";
  onDeleted?: (presentationId: string) => void;
  onDuplicated?: (presentation: PresentationResponse) => void;
};

export function PresentationCard({ id, title, presentation, viewMode = "grid", onDeleted, onDuplicated }: PresentationCardProps) {
  const { locale, t } = useI18n();
  const router = useRouter();
  const pathname = usePathname();
  const [showDeleteDialog, setShowDeleteDialog] = useState(false);
  const [isDeleting, setIsDeleting] = useState(false);
  const [isDuplicating, setIsDuplicating] = useState(false);
  const isUnsupported = presentation.version === "v1-standard";
  const displayTitle = title || t("presentation.untitled");

  const openPresentation = () => {
    if (isUnsupported) {
      notify.warning(t("dashboard.unsupportedPresentation"), t("dashboard.legacyNotice", { release: "Presenton 0.9.3-beta" }));
      return;
    }
    trackEvent(MixpanelEvent.Dashboard_Presentation_Opened, { pathname, presentation_id: id, title_length: displayTitle.length, slide_count: presentation.slides?.length || 0 });
    router.push(`${localizePathname("/presentation", locale)}?id=${encodeURIComponent(id)}&type=standard`);
  };

  const handleDelete = async () => {
    if (isDeleting) return;
    setIsDeleting(true);
    const response = await DashboardApi.deletePresentation(id);
    if (response.success) {
      notify.success(t("dashboard.deleteSuccessTitle"), t("dashboard.deleteSuccessDescription"), { id: `delete-${id}` });
      setShowDeleteDialog(false);
      onDeleted?.(id);
    } else {
      notify.error(t("dashboard.deleteFailedTitle"), t("dashboard.deleteFailed"), { id: `delete-${id}` });
    }
    setIsDeleting(false);
  };

  const handleDuplicate = async () => {
    if (isDuplicating) return;
    setIsDuplicating(true);
    try {
      const duplicated = await DashboardApi.duplicatePresentation(id) as PresentationResponse;
      notify.success(t("dashboard.duplicateSuccessTitle"), t("dashboard.duplicateSuccessDescription"), { id: `duplicate-${id}` });
      onDuplicated?.(duplicated);
    } catch {
      notify.error(t("dashboard.duplicateFailedTitle"), t("dashboard.duplicateFailed"), { id: `duplicate-${id}` });
    } finally {
      setIsDuplicating(false);
    }
  };

  const firstSlide = presentation.slides?.[0];
  const useHtmlPreview = shouldRenderTemplateV2HtmlPreview(firstSlide, presentation.version);
  const preview = isUnsupported ? (
    <div className="flex flex-col items-center gap-2 px-5 text-center text-[#667085]"><span className="flex h-10 w-10 items-center justify-center rounded-full bg-[#F0EDFF] text-[#6F4EF6]"><Archive className="h-4 w-4" /></span><span className="text-xs font-medium">{t("dashboard.previewUnavailable")}</span></div>
  ) : useHtmlPreview ? (
    <TemplateV2HtmlSlidePreview slide={firstSlide} fonts={presentation.fonts} />
  ) : (
    <SlideScale slide={firstSlide} isClickable={false} presentationLayout={presentation.layout} />
  );

  return (
    <article className={`group relative overflow-hidden rounded-2xl border border-[#E5E6EB] bg-white transition duration-300 hover:-translate-y-1 hover:border-[#D6D0F8] hover:shadow-[0_16px_38px_rgba(34,29,63,0.11)] motion-reduce:transform-none ${viewMode === "list" ? "flex min-h-[146px]" : "flex flex-col"}`}>
      <button type="button" onClick={openPresentation} disabled={isUnsupported} aria-label={t("dashboard.openNamed", { title: displayTitle })} className={`relative flex items-center justify-center overflow-hidden bg-[#F5F4FA] focus-visible:z-10 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-inset focus-visible:ring-[#6F4EF6] ${viewMode === "list" ? "m-3 aspect-video w-[190px] max-w-[38%] shrink-0 rounded-xl" : "aspect-video w-full"}`}>
        <span className="absolute inset-0 bg-[radial-gradient(circle_at_top_right,rgba(111,78,246,0.10),transparent_48%)]" aria-hidden="true" />
        <span className={`relative block overflow-hidden rounded-lg border border-black/[0.06] bg-white shadow-sm ${viewMode === "list" ? "h-full w-full" : "w-[84%]"}`}>{preview}</span>
        <span className="absolute end-3 top-3 rounded-full border border-white/70 bg-white/90 px-2 py-1 text-[10px] font-semibold text-[#4B5565] shadow-sm">{t("presentation.slideCount", { count: presentation.n_slides || presentation.slides?.length || 0 })}</span>
      </button>

      <div className={`flex min-w-0 flex-1 items-center gap-3 bg-white p-4 ${viewMode === "grid" ? "border-t border-[#EEEEF2]" : ""}`}>
        <button type="button" onClick={openPresentation} disabled={isUnsupported} className="min-w-0 flex-1 text-start focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[#6F4EF6] focus-visible:ring-offset-2">
          <div className="line-clamp-1 text-sm font-semibold text-[#20232D]" dir="auto"><MarkdownRenderer content={displayTitle} className="mb-0 line-clamp-1 text-sm font-semibold text-[#20232D]" /></div>
          <div className="mt-2 flex flex-wrap items-center gap-2 text-xs text-[#7A8190]"><span>{formatDate(presentation.updated_at || presentation.created_at, locale)}</span>{!isUnsupported && <><span aria-hidden="true">·</span><span className="inline-flex items-center gap-1 text-[#28735C]"><CheckCircle2 className="h-3 w-3" />{t("dashboard.readyStatus")}</span></>}</div>
        </button>
        <Popover>
          <PopoverTrigger asChild><button type="button" className="flex h-10 w-10 shrink-0 items-center justify-center rounded-xl text-[#667085] transition hover:bg-[#F5F4FA] hover:text-[#303442] focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[#6F4EF6]" aria-label={t("dashboard.openMenu", { title: displayTitle })}><Ellipsis className="h-5 w-5" /></button></PopoverTrigger>
          <PopoverContent align="end" className="w-48 rounded-xl border-[#E5E6EB] bg-white p-1.5 shadow-[0_16px_36px_rgba(34,29,63,0.14)]">
            {!isUnsupported && <button type="button" disabled={isDuplicating} onClick={() => void handleDuplicate()} className="flex min-h-10 w-full items-center gap-2 rounded-lg px-3 text-sm text-[#303442] transition hover:bg-[#F7F7FA] focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[#6F4EF6] disabled:opacity-60">{isDuplicating ? <Loader2 className="h-4 w-4 animate-spin" /> : <Copy className="h-4 w-4" />}{isDuplicating ? t("dashboard.duplicating") : t("common.duplicate")}</button>}
            <button type="button" onClick={() => setShowDeleteDialog(true)} className="flex min-h-10 w-full items-center gap-2 rounded-lg px-3 text-sm text-[#B42318] transition hover:bg-[#FFF3F1] focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[#D92D20]"><Trash2 className="h-4 w-4" />{t("common.delete")}</button>
          </PopoverContent>
        </Popover>
      </div>

      <Dialog open={showDeleteDialog} onOpenChange={(open) => !isDeleting && setShowDeleteDialog(open)}>
        <DialogContent className="w-[calc(100vw-32px)] max-w-md rounded-2xl border-0 p-0 shadow-[0_24px_80px_rgba(24,20,46,0.2)]">
          <DialogHeader className="px-6 pb-4 pt-7 text-start sm:px-7">
            <span className="mb-3 flex h-11 w-11 items-center justify-center rounded-full bg-[#FFF0EE] text-[#B42318]"><AlertTriangle className="h-5 w-5" /></span>
            <DialogTitle className="text-xl font-semibold tracking-[-0.02em] text-[#20232D]" dir="auto">{t("dashboard.deleteNamed", { title: displayTitle })}</DialogTitle>
            <DialogDescription className="pt-1 text-sm leading-6 text-[#667085]">{t("dashboard.deleteNamedDescription")}</DialogDescription>
          </DialogHeader>
          <DialogFooter className="flex-row border-t border-[#EEEEF2] p-4 sm:justify-end sm:space-x-0">
            <button type="button" disabled={isDeleting} onClick={() => setShowDeleteDialog(false)} className="min-h-10 rounded-xl px-5 text-sm font-semibold text-[#4B5565] hover:bg-[#F7F7FA] focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[#6F4EF6] disabled:opacity-60">{t("common.cancel")}</button>
            <button type="button" disabled={isDeleting} onClick={() => void handleDelete()} className="inline-flex min-h-10 items-center justify-center gap-2 rounded-xl bg-[#B42318] px-5 text-sm font-semibold text-white transition hover:bg-[#912018] focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[#B42318] disabled:opacity-60">{isDeleting && <Loader2 className="h-4 w-4 animate-spin" />}{isDeleting ? t("dashboard.deleting") : t("common.delete")}</button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </article>
  );
}
