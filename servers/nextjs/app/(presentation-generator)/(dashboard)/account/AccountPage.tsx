"use client";

import { Languages, PlayCircle, ShieldCheck, UserRound } from "lucide-react";
import type { LucideIcon } from "lucide-react";
import { useRouter } from "next/navigation";

import LogoutButton from "@/components/Auth/LogoutButton";
import { LocaleSwitcher } from "@/components/LocaleSwitcher";
import { useI18n } from "@/i18n/catalog";
import { localizePathname } from "@/i18n/routing";
import { ONBOARDING_STORAGE_KEY } from "@/lib/product-preferences";

export default function AccountPage({ username }: { username: string }) {
  const { locale, t } = useI18n();
  const router = useRouter();
  const replayOnboarding = () => {
    window.localStorage.removeItem(ONBOARDING_STORAGE_KEY);
    router.push(localizePathname("/dashboard", locale));
  };
  return (
    <div className="mx-auto max-w-4xl">
      <header className="mb-8 max-w-2xl">
        <p className="text-xs font-bold uppercase tracking-[0.12em] text-[#6F4EF6]">{t("navigation.account")}</p>
        <h2 className="mt-2 text-3xl font-semibold tracking-[-0.04em] text-[#171A24] sm:text-4xl">{t("account.title")}</h2>
        <p className="mt-3 text-sm leading-6 text-[#667085] sm:text-base">{t("account.description")}</p>
      </header>
      <div className="grid gap-5 sm:grid-cols-2">
        <AccountCard icon={UserRound} title={t("account.profile")} description={t("account.profileDescription")}>
          <div className="rounded-xl bg-[#F7F7FA] px-4 py-3">
            <p className="text-xs text-[#7A8190]">{t("settings.signedInAs")}</p>
            <p className="mt-1 font-semibold text-[#20232D]" dir="auto">{username}</p>
          </div>
        </AccountCard>
        <AccountCard icon={Languages} title={t("account.interfaceLanguage")} description={t("generation.presentationLanguageHelp")}>
          <LocaleSwitcher />
        </AccountCard>
        <AccountCard icon={PlayCircle} title={t("account.onboarding")} description={t("account.onboardingDescription")}>
          <button type="button" onClick={replayOnboarding} className="min-h-11 rounded-xl border border-[#D9D4F8] bg-[#F7F5FF] px-4 text-sm font-semibold text-[#5538D7] transition hover:bg-[#F0EDFF] focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[#6F4EF6]">{t("account.replayOnboarding")}</button>
        </AccountCard>
        <AccountCard icon={ShieldCheck} title={t("account.security")} description={t("account.securityDescription")}>
          <LogoutButton label={t("navigation.logout")} pendingLabel={t("navigation.signingOut")} className="flex min-h-11 items-center justify-center gap-2 rounded-xl border border-[#F3C7C2] bg-[#FFF7F6] px-4 text-sm font-semibold text-[#B42318] transition hover:bg-[#FFF0EE] focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[#D92D20]" />
        </AccountCard>
      </div>
    </div>
  );
}

function AccountCard({ icon: Icon, title, description, children }: { icon: LucideIcon; title: string; description: string; children: React.ReactNode }) {
  return <section className="flex min-h-[230px] flex-col rounded-2xl border border-[#E7E7ED] bg-white p-6 shadow-[0_10px_35px_rgba(36,31,65,0.04)]"><span className="flex h-10 w-10 items-center justify-center rounded-xl bg-[#F0EDFF] text-[#6344E8]"><Icon className="h-4 w-4" aria-hidden="true" /></span><h3 className="mt-5 text-base font-semibold text-[#20232D]">{title}</h3><p className="mt-1 text-xs leading-5 text-[#667085]">{description}</p><div className="mt-auto pt-5">{children}</div></section>;
}
