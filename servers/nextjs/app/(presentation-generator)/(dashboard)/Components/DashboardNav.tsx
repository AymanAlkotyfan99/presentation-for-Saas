"use client";

import { ChevronRight } from 'lucide-react';
import Link from 'next/link';
import React, { } from 'react'
import { usePathname } from 'next/navigation';
import { useI18n } from '@/i18n/catalog';
import { localizePathname, stripLocalePrefix } from '@/i18n/routing';

const DashboardNav = () => {
    const { locale, t } = useI18n();
    const pathname = usePathname();
    const activeTab = stripLocalePrefix(pathname).split("?")[0].split("/").pop();
    const activeLabel = activeTab === "dashboard"
        ? t("navigation.dashboard")
        : activeTab === "templates"
            ? t("navigation.templates")
            : activeTab === "settings"
                ? t("navigation.settings")
                : activeTab === "theme"
                    ? t("theme.title")
                    : activeTab;

    return (
        <div className="sticky top-0 right-0 z-50 py-[28px]   backdrop-blur ">
            <div className="flex xl:flex-row flex-col gap-6 xl:gap-0 items-center justify-between">
                <h3 className=" text-[28px] tracking-[-0.84px] font-unbounded font-normal text-[#101828] flex items-center gap-2">

                    {activeLabel}
                </h3>
                <div className="flex  gap-2.5 max-sm:w-full max-md:justify-center max-sm:flex-wrap">



                    {activeTab !== "playground" && activeTab !== "theme" && <Link
                        href={localizePathname("/create", locale)}
                        className="inline-flex items-center gap-2 rounded-xl px-4 py-2.5 text-black text-sm font-medium shadow-sm hover:shadow-md"
                        aria-label={t("navigation.create")}
                        style={{
                            borderRadius: "48px",
                            background: "linear-gradient(270deg, #D5CAFC 2.4%, #E3D2EB 27.88%, #F4DCD3 69.23%, #FDE4C2 100%)",
                        }}
                    >

                        <span className="hidden md:inline">{t("dashboard.newPresentation")}</span>
                        <span className="md:hidden">{t("theme.new")}</span>
                        <ChevronRight className="w-4 h-4" />
                    </Link>}
                    {activeTab === "theme" &&
                        <Link
                            href={`${localizePathname("/theme", locale)}?tab=new-theme`}
                            className="inline-flex items-center font-inter font-normal gap-2 rounded-xl px-4 py-2.5 text-black text-sm  shadow-sm hover:shadow-md"
                            aria-label={t("theme.createNew")}
                            style={{
                                borderRadius: "48px",
                                background: "linear-gradient(270deg, #D5CAFC 2.4%, #E3D2EB 27.88%, #F4DCD3 69.23%, #FDE4C2 100%)",
                            }}
                        >
                            <span className="hidden md:inline">{t("theme.newTheme")}</span>
                            <span className="md:hidden">{t("theme.new")}</span>
                            <ChevronRight className="w-4 h-4" />
                        </Link>
                    }
                </div>
            </div>
        </div>
    )
}

export default DashboardNav
