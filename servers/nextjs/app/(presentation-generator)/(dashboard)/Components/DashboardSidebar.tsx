"use client";

import React from "react";
import { LayoutDashboard, Star, Brain, Settings, HelpCircle, UsersRound, ListChecks, Library } from "lucide-react";
import { usePathname } from "next/navigation";
import Link from "next/link";
import { PRODUCT_IDENTITY } from "@/lib/product-identity";
import { BRAND_ASSETS, DISPLAY_PRODUCT } from "@/lib/product-metadata";
import { useI18n } from "@/i18n/catalog";
import { localizePathname, stripLocalePrefix } from "@/i18n/routing";
import { WorkspaceSwitcher } from "@/features/workspaces/WorkspaceSwitcher";
import { useWorkspace } from "@/features/workspaces/WorkspaceProvider";



export const defaultNavItems = [
    { key: "dashboard" as const, label: "Dashboard", icon: LayoutDashboard },
    { key: "templates" as const, label: "Standard", icon: Star },
    { key: "designs" as const, label: "Smart", icon: Brain },



];
export const BelongingNavItems = [
    { key: "settings" as const, label: "Settings", icon: Settings },
]

const DashboardSidebar = () => {
    const { locale, t } = useI18n();
    const pathname = usePathname();
    const routePath = stripLocalePrefix(pathname);
    const workspace = useWorkspace();

    return (
        <aside
            className="sticky top-0 flex h-screen w-[114px] shrink-0 flex-col justify-between border-e border-[#E1E1E5] bg-[#F6F6F9] px-4 py-8 backdrop-blur"
            aria-label={t("navigation.sidebar")}
        >
            <div>
                <WorkspaceSwitcher />

                <Link href={localizePathname("/dashboard", locale)} className="flex items-center gap-2 border-b border-[#E1E1E5] pb-6">
                    <div className="rounded-full cursor-pointer p-1 flex justify-center items-center mx-auto" style={{ backgroundColor: PRODUCT_IDENTITY.colors.primary }}>
                        <img src={BRAND_ASSETS.compactIcon} alt={`${DISPLAY_PRODUCT.shortName} logo`} className="h-[40px] object-contain w-full rounded-full" />
                    </div>
                </Link>
                <nav className="pt-6 font-syne" aria-label={t("navigation.sections")}>
                    <div className="  space-y-6">

                        {/* Dashboard */}
                        <Link
                            prefetch={false}
                            href={localizePathname("/dashboard", locale)}
                            className={[
                                "flex flex-col tex-center items-center gap-2  transition-colors",
                                routePath === "/dashboard" ? "" : "ring-transparent",
                            ].join(" ")}
                            aria-label={t("navigation.dashboard")}
                            title={t("navigation.dashboard")}
                        >
                            <LayoutDashboard className={["h-4 w-4", routePath === "/dashboard" ? "text-[#5146E5]" : "text-slate-600"].join(" ")} />
                            <span className="text-[11px] text-slate-800">{t("navigation.dashboard")}</span>
                        </Link>
                        {workspace.available && workspace.can("members:view") && <Link
                            prefetch={false}
                            href={localizePathname("/workspaces/members", locale)}
                            className="flex flex-col items-center gap-2 transition-colors"
                            aria-label={t("workspace.members")}
                            title={t("workspace.members")}
                        >
                            <UsersRound className={["h-4 w-4", routePath === "/workspaces/members" ? "text-[#5146E5]" : "text-slate-600"].join(" ")} />
                            <span className="text-[11px] text-slate-800">{t("workspace.members")}</span>
                        </Link>}
                        {process.env.NEXT_PUBLIC_DURABLE_JOBS_ENABLED === "true" && workspace.available && workspace.can("jobs:read") && <Link
                            prefetch={false}
                            href={localizePathname("/jobs", locale)}
                            className="flex flex-col items-center gap-2 transition-colors"
                            aria-label={t("jobs.title")}
                            title={t("jobs.title")}
                        >
                            <ListChecks className={["h-4 w-4", routePath === "/jobs" ? "text-[#5146E5]" : "text-slate-600"].join(" ")} />
                            <span className="text-[11px] text-slate-800">{t("jobs.nav")}</span>
                        </Link>}
                        {process.env.NEXT_PUBLIC_ASSET_LIBRARY_ENABLED === "true" && workspace.available && workspace.can("assets:read") && <Link
                            prefetch={false}
                            href={localizePathname("/assets", locale)}
                            className="flex flex-col items-center gap-2 transition-colors"
                            aria-label={t("assets.title")}
                            title={t("assets.title")}
                        >
                            <Library className={["h-4 w-4", routePath === "/assets" ? "text-[#5146E5]" : "text-slate-600"].join(" ")} />
                            <span className="text-[11px] text-slate-800">{t("assets.nav")}</span>
                        </Link>}
                        <Link
                            prefetch={false}
                            href={localizePathname("/templates", locale)}
                            className={[
                                "flex flex-col tex-center items-center gap-2  transition-colors",
                                routePath === "/templates" ? "" : "ring-transparent",
                            ].join(" ")}
                            aria-label={t("navigation.templates")}
                            title={t("navigation.templates")}
                        >
                            <div className="flex flex-col cursor-pointer tex-center items-center gap-2  transition-colors">
                                <svg xmlns="http://www.w3.org/2000/svg" width="24" height="24" viewBox="0 0 24 24" fill="none" stroke={`${routePath === "/templates" ? "#5146E5" : "#475569"}`} strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" className="h-4 w-4"><path d="M4 14h6" /><path d="M4 2h10" /><rect x="4" y="18" width="16" height="4" rx="1" /><rect x="4" y="6" width="16" height="4" rx="1" /></svg>
                                <span className="text-[11px] text-slate-800">{t("navigation.templates")}</span>
                            </div>
                        </Link>
                        {/* <Link
                            prefetch={false}
                            href={`/theme`}
                            className={[
                                "flex flex-col tex-center items-center gap-2  transition-colors",
                                pathname === "/theme" ? "" : "ring-transparent",
                            ].join(" ")}
                            aria-label="Theme"
                            title="Theme"
                        >
                            <div className="flex flex-col cursor-pointer tex-center items-center gap-2  transition-colors">
                                <Palette className={`h-4 w-4 ${pathname === "/theme" ? "text-[#5146E5]" : "text-slate-600"}`} />
                                <span className="text-[11px] text-slate-800">Themes</span>
                            </div>
                        </Link> */}
                    </div>
                </nav>
            </div>

            <div className="border-t border-[#E1E1E5] pt-5 font-syne">
                <Link
                    href={`mailto:${DISPLAY_PRODUCT.supportEmail}`}
                    className="flex flex-col items-center gap-2 transition-colors"
                >
                    <HelpCircle className="h-4 w-4" />
                    <span className="text-[11px] text-slate-800">{t("navigation.help")}</span>
                </Link>
            </div>

        </aside>
    );
};

export default DashboardSidebar;
