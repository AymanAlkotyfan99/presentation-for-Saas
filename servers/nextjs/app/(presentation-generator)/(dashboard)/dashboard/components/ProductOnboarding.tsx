"use client";

import { useEffect, useState } from "react";
import { ArrowRight, FileText, LayoutTemplate, PencilRuler, X } from "lucide-react";
import Link from "next/link";
import { useI18n } from "@/i18n/catalog";
import { localizePathname } from "@/i18n/routing";
import { ONBOARDING_STORAGE_KEY } from "@/lib/product-preferences";

export function ProductOnboarding() {
  const { locale, t } = useI18n();
  const [visible, setVisible] = useState(false);
  useEffect(() => setVisible(window.localStorage.getItem(ONBOARDING_STORAGE_KEY) !== "true"), []);
  const dismiss = () => { window.localStorage.setItem(ONBOARDING_STORAGE_KEY, "true"); setVisible(false); };
  if (!visible) return null;
  const steps = [{ key: "productOnboarding.stepOne", icon: FileText }, { key: "productOnboarding.stepTwo", icon: LayoutTemplate }, { key: "productOnboarding.stepThree", icon: PencilRuler }];
  return (
    <section className="relative overflow-hidden rounded-[20px] border border-[#DDD6FE] bg-gradient-to-br from-[#F8F6FF] to-white p-5 shadow-[0_10px_30px_rgba(90,67,190,0.07)] sm:p-7" aria-labelledby="onboarding-title">
      <button type="button" onClick={dismiss} className="absolute end-4 top-4 flex h-10 w-10 items-center justify-center rounded-full text-[#7A8190] transition hover:bg-white hover:text-[#303442] focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[#6F4EF6]" aria-label={t("productOnboarding.skip")}><X className="h-4 w-4" /></button>
      <p className="text-xs font-bold uppercase tracking-[0.12em] text-[#6F4EF6]">{t("productOnboarding.eyebrow")}</p>
      <h2 id="onboarding-title" className="mt-2 max-w-2xl text-2xl font-semibold tracking-[-0.03em] text-[#20232D]">{t("productOnboarding.title")}</h2>
      <p className="mt-2 max-w-2xl text-sm leading-6 text-[#667085]">{t("productOnboarding.description")}</p>
      <ol className="mt-6 grid gap-3 sm:grid-cols-3">{steps.map(({ key, icon: Icon }, index) => <li key={key} className="flex items-center gap-3 rounded-xl border border-white bg-white/80 p-3 text-sm font-medium text-[#404554] shadow-sm"><span className="flex h-8 w-8 shrink-0 items-center justify-center rounded-lg bg-[#EEEAFE] text-[#6344E8]"><Icon className="h-4 w-4" /></span><span>{index + 1}. {t(key)}</span></li>)}</ol>
      <div className="mt-6 flex flex-wrap gap-3"><Link href={localizePathname("/create", locale)} onClick={dismiss} className="inline-flex min-h-11 items-center gap-2 rounded-xl bg-[#6F4EF6] px-5 text-sm font-semibold text-white transition hover:bg-[#6242E8] focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[#6F4EF6] focus-visible:ring-offset-2">{t("productOnboarding.create")}<ArrowRight className="rtl-flip h-4 w-4" /></Link><button type="button" onClick={dismiss} className="min-h-11 rounded-xl px-4 text-sm font-semibold text-[#667085] transition hover:bg-white focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[#6F4EF6]">{t("productOnboarding.skip")}</button></div>
    </section>
  );
}

