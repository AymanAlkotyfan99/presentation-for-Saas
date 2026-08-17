"use client";

import Wrapper from "@/components/Wrapper";
import React from "react";
import Link from "next/link";
import Image from "next/image";
import { usePathname } from "next/navigation";
import { trackEvent, MixpanelEvent } from "@/utils/mixpanel";
import { ArrowLeft } from "lucide-react";
import { BRAND_ASSETS, DISPLAY_PRODUCT } from "@/lib/product-metadata";
import { LocaleSwitcher } from "@/components/LocaleSwitcher";
import { localizePathname, stripLocalePrefix } from "@/i18n/routing";
import { useI18n } from "@/i18n/catalog";

const PATHS_WITH_HEADER_BACK = [
  "/upload",
  "/create",
  "/outline",
  "/documents-preview",
  "/template-preview",
] as const;

function pathMatches(pathname: string | null, base: string) {
  const normalized = stripLocalePrefix(pathname || "/");
  return normalized === base || normalized.startsWith(`${base}/`);
}

const Header = () => {
  const pathname = usePathname();
  const { locale, t } = useI18n();
  const showHeaderBack = PATHS_WITH_HEADER_BACK.some((p) => pathMatches(pathname, p));

  const backToUpload =
    pathMatches(pathname, "/outline") || pathMatches(pathname, "/documents-preview");
  const backToTemplates = pathMatches(pathname, "/template-preview");

  const backHref = localizePathname(
    backToUpload ? "/create" : backToTemplates ? "/templates" : "/dashboard",
    locale,
  );
  const backLabel = backToUpload
    ? t("common.back")
    : backToTemplates
      ? t("common.back")
      : t("common.back");

  return (
    <div className="w-full   sticky top-0 z-50 py-7 "
      style={{
        background: "linear-gradient(180deg, #FFF 0%, rgba(255, 255, 255, 0.00) 110.67%)",

      }}
    >
      <Wrapper className="px-5 sm:px-10 lg:px-20">
        <div className="flex items-center justify-between py-1">
          <div className="flex items-center gap-3">
            <Link href={localizePathname("/dashboard", locale)} onClick={() => trackEvent(MixpanelEvent.Navigation, { from: pathname, to: "/dashboard" })}>
              <Image
                src={BRAND_ASSETS.compactIcon}
                alt={`${DISPLAY_PRODUCT.shortName} logo`}
                height={40}
                width={40}
                className="h-[40px] w-[40px]"
              />
            </Link>
          </div>
          <div className="flex items-center gap-4">
            <LocaleSwitcher compact />
            {showHeaderBack ? (
              <Link
                href={backHref}
                className="text-[#333333] text-xs font-syne font-semibold flex items-center gap-2"
                onClick={() =>
                  trackEvent(MixpanelEvent.Navigation, { from: pathname, to: backHref })
                }
              >
                <ArrowLeft className="rtl-flip w-4 h-4 shrink-0 text-[#333333]" aria-hidden />
                <span>{backLabel}</span>
              </Link>
            ) : null}
          </div>
        </div>
      </Wrapper>
    </div>
  );
};

export default Header;
