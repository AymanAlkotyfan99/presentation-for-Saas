"use client";

import Link from "next/link";
import Image from "next/image";
import { MixpanelEvent, trackEvent } from "@/utils/mixpanel";
import { useI18n } from "@/i18n/catalog";
import { localizePathname } from "@/i18n/routing";

export const EmptyState = () => {
  const { locale, t } = useI18n();
  return (
    <div className="w-full rounded-2xl bg-[#FAFAFC]">
      <Link
        href={localizePathname("/create", locale)}
        aria-label={t("dashboard.emptyTitle")}
        className="group mx-auto flex min-h-[280px] w-full max-w-xl flex-col items-center justify-center px-5 text-center outline-none transition-colors focus-visible:ring-2 focus-visible:ring-inset focus-visible:ring-[#7A5AF8]"
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
          className="h-[64px] w-[86px] object-cover transition-transform group-hover:-translate-y-1 motion-reduce:transform-none"
          aria-hidden="true"
        />
        <span className="mt-1 text-lg font-semibold text-[#20232D]">{t("dashboard.emptyTitle")}</span>
        <span className="max-w-sm text-sm leading-6 text-[#7A8190]">{t("dashboard.emptyDescription")}</span>
        <span className="mt-2 rounded-xl bg-[#6F4EF6] px-5 py-3 text-sm font-semibold text-white shadow-[0_8px_20px_rgba(111,78,246,0.2)]">{t("navigation.create")}</span>
      </Link>
    </div>
  );
};
