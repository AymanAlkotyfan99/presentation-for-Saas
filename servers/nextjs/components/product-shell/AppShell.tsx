"use client";

import {
  BookOpen,
  ChevronDown,
  CircleHelp,
  Database,
  FolderKanban,
  LayoutDashboard,
  Menu,
  Plus,
  Settings,
  ShieldCheck,
  UsersRound,
  Workflow,
  UserRound,
} from "lucide-react";
import Image from "next/image";
import Link from "next/link";
import { usePathname } from "next/navigation";
import type { LucideIcon } from "lucide-react";
import { useEffect, useState } from "react";

import LogoutButton from "@/components/Auth/LogoutButton";
import { LocaleSwitcher } from "@/components/LocaleSwitcher";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuLabel,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import {
  Sheet,
  SheetContent,
  SheetHeader,
  SheetTitle,
  SheetTrigger,
} from "@/components/ui/sheet";
import { WorkspaceSwitcher } from "@/features/workspaces/WorkspaceSwitcher";
import { useWorkspace } from "@/features/workspaces/WorkspaceProvider";
import { useI18n } from "@/i18n/catalog";
import { localizePathname, stripLocalePrefix } from "@/i18n/routing";
import { BRAND_ASSETS, DISPLAY_PRODUCT } from "@/lib/product-metadata";
import { isProductRouteActive } from "@/lib/product-navigation";
import { loadProductPreferences } from "@/lib/product-preferences";
import { SessionMonitor } from "./SessionMonitor";

type AppShellProps = {
  children: React.ReactNode;
  username: string;
  role: "admin" | "user" | null;
};

type ShellLink = {
  href: string;
  labelKey: string;
  icon: LucideIcon;
  primary?: boolean;
};

const primaryLinks: ShellLink[] = [
  { href: "/dashboard", labelKey: "navigation.dashboard", icon: LayoutDashboard },
  { href: "/presentations", labelKey: "navigation.presentations", icon: FolderKanban },
  { href: "/templates", labelKey: "navigation.templates", icon: BookOpen },
];

function ShellNavigation({ onNavigate }: { onNavigate?: () => void }) {
  const pathname = usePathname() || "/";
  const { locale, t } = useI18n();

  return (
    <nav aria-label={t("navigation.sections")} className="space-y-1.5">
      <Link
        href={localizePathname("/create", locale)}
        onClick={onNavigate}
        className="mb-5 flex min-h-11 items-center justify-center gap-2 rounded-xl bg-[#6F4EF6] px-4 py-3 text-sm font-semibold text-white shadow-[0_8px_24px_rgba(111,78,246,0.22)] transition duration-200 hover:-translate-y-0.5 hover:bg-[#6242E8] focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[#6F4EF6] focus-visible:ring-offset-2 motion-reduce:transform-none"
      >
        <Plus className="h-4 w-4" aria-hidden="true" />
        <span>{t("navigation.create")}</span>
      </Link>
      {primaryLinks.map(({ href, labelKey, icon: Icon }) => {
        const active = isProductRouteActive(pathname, href);
        return (
          <Link
            key={href}
            href={localizePathname(href, locale)}
            onClick={onNavigate}
            aria-current={active ? "page" : undefined}
            className={`group flex min-h-11 items-center gap-3 rounded-xl px-3.5 py-2.5 text-sm font-medium transition duration-200 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[#6F4EF6] ${
              active
                ? "bg-[#F0EDFF] text-[#5538D7]"
                : "text-[#4B5565] hover:bg-[#F7F7FA] hover:text-[#171A24]"
            }`}
          >
            <Icon className="h-[18px] w-[18px]" strokeWidth={1.8} aria-hidden="true" />
            <span>{t(labelKey)}</span>
          </Link>
        );
      })}
    </nav>
  );
}

function BrandLink() {
  const { locale } = useI18n();
  return (
    <Link
      href={localizePathname("/dashboard", locale)}
      className="inline-flex items-center gap-3 rounded-lg focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[#6F4EF6]"
    >
      <span className="flex h-10 w-10 items-center justify-center rounded-xl bg-[#F0EDFF]">
        <Image src={BRAND_ASSETS.compactIcon} alt="" width={28} height={28} className="h-7 w-7 object-contain" />
      </span>
      <span className="text-lg font-bold tracking-[-0.03em] text-[#171A24]">{DISPLAY_PRODUCT.shortName}</span>
    </Link>
  );
}

function UtilityLinks({ role, onNavigate }: { role: AppShellProps["role"]; onNavigate?: () => void }) {
  const pathname = usePathname() || "/";
  const { locale, t } = useI18n();
  const workspace = useWorkspace();
  const links: ShellLink[] = [
    { href: "/settings", labelKey: "navigation.preferences", icon: Settings },
    { href: "/account", labelKey: "navigation.account", icon: UserRound },
  ];
  if (workspace.can("members:view")) {
    links.push({ href: "/workspaces/members", labelKey: "navigation.team", icon: UsersRound });
  }
  if (role === "admin") {
    links.push(
      { href: "/admin/platform", labelKey: "navigation.admin", icon: ShieldCheck },
      { href: "/jobs", labelKey: "navigation.jobs", icon: Workflow },
      { href: "/assets", labelKey: "navigation.assets", icon: Database },
    );
  }
  return (
    <div className="space-y-1.5">
      {links.map(({ href, labelKey, icon: Icon }) => {
        const active = isProductRouteActive(pathname, href);
        return (
          <Link
            key={href}
            href={localizePathname(href, locale)}
            onClick={onNavigate}
            aria-current={active ? "page" : undefined}
            className={`flex min-h-10 items-center gap-3 rounded-xl px-3.5 py-2 text-sm transition focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[#6F4EF6] ${active ? "bg-[#F0EDFF] font-medium text-[#5538D7]" : "text-[#667085] hover:bg-[#F7F7FA] hover:text-[#171A24]"}`}
          >
            <Icon className="h-[17px] w-[17px]" strokeWidth={1.8} aria-hidden="true" />
            <span>{t(labelKey)}</span>
          </Link>
        );
      })}
      <a
        href={`mailto:${DISPLAY_PRODUCT.supportEmail}`}
        className="flex min-h-10 items-center gap-3 rounded-xl px-3.5 py-2 text-sm text-[#667085] transition hover:bg-[#F7F7FA] hover:text-[#171A24] focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[#6F4EF6]"
      >
        <CircleHelp className="h-[17px] w-[17px]" strokeWidth={1.8} aria-hidden="true" />
        <span>{t("navigation.help")}</span>
      </a>
    </div>
  );
}

function AccountMenu({ username, role }: Pick<AppShellProps, "username" | "role">) {
  const { locale, t } = useI18n();
  return (
    <DropdownMenu>
      <DropdownMenuTrigger asChild>
        <button
          type="button"
          className="flex min-h-11 items-center gap-3 rounded-xl border border-[#E7E7ED] bg-white px-3 py-2 text-start transition hover:border-[#D7D2F8] hover:bg-[#FCFBFF] focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[#6F4EF6]"
          aria-label={t("navigation.accountMenu")}
        >
          <span className="flex h-8 w-8 shrink-0 items-center justify-center rounded-full bg-[#EEEAFE] text-sm font-bold uppercase text-[#5538D7]">
            {username.trim().slice(0, 1) || "B"}
          </span>
          <span className="min-w-0 flex-1">
            <span className="block truncate text-sm font-semibold text-[#171A24]" dir="auto">{username}</span>
            <span className="block text-[11px] text-[#7A8190]">{role === "admin" ? t("admin.administrator") : t("admin.userRole")}</span>
          </span>
          <ChevronDown className="h-4 w-4 text-[#7A8190]" aria-hidden="true" />
        </button>
      </DropdownMenuTrigger>
      <DropdownMenuContent align="end" sideOffset={8} className="w-72 rounded-2xl border-[#E7E7ED] p-2 shadow-[0_18px_48px_rgba(28,25,46,0.14)]">
        <DropdownMenuLabel className="px-3 py-2">
          <span className="block truncate text-sm font-semibold" dir="auto">{username}</span>
          <span className="mt-0.5 block text-xs font-normal text-muted-foreground">{t("account.signedIn")}</span>
        </DropdownMenuLabel>
        <DropdownMenuSeparator />
        <DropdownMenuItem asChild>
          <Link href={localizePathname("/account", locale)} className="min-h-10 rounded-lg px-3 text-sm focus:bg-[#F7F7FA]">
            <UserRound className="h-4 w-4" aria-hidden="true" /> {t("navigation.account")}
          </Link>
        </DropdownMenuItem>
        <DropdownMenuItem asChild>
          <Link href={localizePathname("/settings", locale)} className="min-h-10 rounded-lg px-3 text-sm focus:bg-[#F7F7FA]">
            <Settings className="h-4 w-4" aria-hidden="true" /> {t("navigation.preferences")}
          </Link>
        </DropdownMenuItem>
        {role === "admin" && (
          <DropdownMenuItem asChild>
            <Link href={localizePathname("/admin/platform", locale)} className="min-h-10 rounded-lg px-3 text-sm focus:bg-[#F7F7FA]">
              <ShieldCheck className="h-4 w-4" aria-hidden="true" /> {t("navigation.admin")}
            </Link>
          </DropdownMenuItem>
        )}
        <div className="my-1 rounded-xl bg-[#F8F8FB] px-3 py-2">
          <LocaleSwitcher />
        </div>
        <DropdownMenuSeparator />
        <LogoutButton
          label={t("navigation.logout")}
          pendingLabel={t("navigation.signingOut")}
          className="flex min-h-10 w-full items-center gap-2 rounded-lg px-3 text-sm font-medium text-[#B42318] transition hover:bg-[#FFF3F1] focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[#D92D20] disabled:opacity-60"
        />
      </DropdownMenuContent>
    </DropdownMenu>
  );
}

function ShellSidebar({ username, role }: Pick<AppShellProps, "username" | "role">) {
  return (
    <aside className="fixed inset-y-0 start-0 z-40 hidden w-[264px] flex-col border-e border-[#E9E9EF] bg-white px-5 py-5 lg:flex">
      <BrandLink />
      <div className="mt-7">
        <WorkspaceSwitcher />
      </div>
      <div className="mt-6 flex-1 overflow-y-auto pe-1">
        <ShellNavigation />
      </div>
      <div className="space-y-4 border-t border-[#EEEEF2] pt-4">
        <UtilityLinks role={role} />
        <AccountMenu username={username} role={role} />
      </div>
    </aside>
  );
}

function pageTitle(pathname: string, t: (key: string) => string) {
  const route = stripLocalePrefix(pathname);
  if (route.startsWith("/presentations")) return t("navigation.presentations");
  if (route.startsWith("/create")) return t("navigation.create");
  if (route.startsWith("/templates")) return t("navigation.templates");
  if (route.startsWith("/settings")) return t("navigation.preferences");
  if (route.startsWith("/account")) return t("navigation.account");
  if (route.startsWith("/admin")) return t("navigation.admin");
  return t("navigation.dashboard");
}

export function AppShell({ children, username, role }: AppShellProps) {
  const pathname = usePathname() || "/";
  const { direction, t } = useI18n();
  const [mobileOpen, setMobileOpen] = useState(false);
  useEffect(() => {
    document.documentElement.dataset.motion = loadProductPreferences().motion;
  }, []);
  return (
    <div className="min-h-screen bg-[#F8F8FB] text-[#171A24]">
      <SessionMonitor />
      <ShellSidebar username={username} role={role} />
      <div className="min-h-screen lg:ps-[264px]">
        <header className="sticky top-0 z-30 flex h-[72px] items-center justify-between border-b border-[#E9E9EF] bg-white/95 px-4 backdrop-blur sm:px-6 lg:px-8">
          <div className="flex min-w-0 items-center gap-3">
            <Sheet open={mobileOpen} onOpenChange={setMobileOpen}>
              <SheetTrigger asChild>
                <button type="button" className="flex h-11 w-11 items-center justify-center rounded-xl border border-[#E7E7ED] lg:hidden" aria-label={t("navigation.openMenu")}>
                  <Menu className="h-5 w-5" aria-hidden="true" />
                </button>
              </SheetTrigger>
              <SheetContent side={direction === "rtl" ? "right" : "left"} className="flex w-[min(88vw,320px)] flex-col bg-white p-5">
                <SheetHeader className="text-start">
                  <SheetTitle><BrandLink /></SheetTitle>
                </SheetHeader>
                <div className="mt-6"><WorkspaceSwitcher /></div>
                <div className="mt-6 flex-1 overflow-y-auto"><ShellNavigation onNavigate={() => setMobileOpen(false)} /></div>
                <div className="space-y-4 border-t border-[#EEEEF2] pt-4"><UtilityLinks role={role} onNavigate={() => setMobileOpen(false)} /></div>
              </SheetContent>
            </Sheet>
            <div className="lg:hidden"><BrandLink /></div>
            <h1 className="hidden truncate text-lg font-semibold tracking-[-0.02em] sm:block lg:text-xl">{pageTitle(pathname, t)}</h1>
          </div>
          <div className="flex items-center gap-3">
            <div className="hidden xl:block"><LocaleSwitcher compact /></div>
            <AccountMenu username={username} role={role} />
          </div>
        </header>
        <div key={pathname} className="app-shell-page mx-auto w-full max-w-[1600px] px-4 py-5 sm:px-6 sm:py-7 lg:px-8 lg:py-8">
          {children}
        </div>
      </div>
    </div>
  );
}
