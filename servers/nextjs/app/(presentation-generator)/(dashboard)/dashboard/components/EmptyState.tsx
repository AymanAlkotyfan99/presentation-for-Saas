"use client";

import Link from "next/link";
import Image from "next/image";
import { MixpanelEvent, trackEvent } from "@/utils/mixpanel";
import { useI18n } from "@/i18n/catalog";
import { localizePathname } from "@/i18n/routing";

export const EmptyState = () => {
  const { locale, t } = useI18n();
  return (
    <div className="w-full border-y border-[#EDEEEF]">
      <Link
        href={localizePathname("/upload", locale)}
        aria-label={t("dashboard.emptyTitle")}
        className="group mx-auto flex h-[250px] w-full max-w-[577px] flex-col items-center justify-center gap-[14px] border-x border-[#EDEEEF] bg-white px-5 outline-none transition-colors hover:bg-[#FDFDFF] focus-visible:ring-2 focus-visible:ring-inset focus-visible:ring-[#7A5AF8]"
        onClick={() =>
          trackEvent(MixpanelEvent.Dashboard_New_Presentation_Clicked, {
            source: "dashboard_empty_state",
          })
        }
      >
        <Image
          src="/dashboard-body/empty-folder.png"
          alt=""
          width={1453}
          height={1083}
          className="h-[48.817px] w-[65.495px] object-cover transition-transform group-hover:-translate-y-0.5"
          aria-hidden="true"
        />
        <span className="flex flex-wrap items-center justify-center gap-x-1.5 text-center font-syne text-sm font-medium">
          <span className="text-[#191919]">{t("dashboard.noPresentationsInline")}</span>
          <span className="text-[#7A5AF8]">{t("dashboard.getStarted")}</span>
        </span>
      </Link>
    </div>
  );
};
