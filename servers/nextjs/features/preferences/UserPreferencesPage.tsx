"use client";

import { useEffect, useState } from "react";
import { Check, Image as ImageIcon, LayoutTemplate, Monitor, Palette, Presentation } from "lucide-react";

import { LocaleSwitcher } from "@/components/LocaleSwitcher";
import { Button } from "@/components/ui/button";
import { useI18n } from "@/i18n/catalog";
import {
  ASPECT_RATIOS,
  COLOR_PALETTES,
  DEFAULT_PRODUCT_PREFERENCES,
  DESIGN_STYLES,
  IMAGE_PREFERENCES,
  MOTION_PREFERENCES,
  loadProductPreferences,
  saveProductPreferences,
  type ProductPreferences,
} from "@/lib/product-preferences";
import { LanguageType } from "@/app/(presentation-generator)/upload/type";
import { notify } from "@/components/ui/sonner";

const fieldClass = "min-h-11 w-full rounded-xl border border-[#DDE0E6] bg-white px-3 text-sm text-[#303442] outline-none transition focus:border-[#8D79F6] focus:ring-2 focus:ring-[#6F4EF6]/15";

export default function UserPreferencesPage() {
  const { t } = useI18n();
  const [preferences, setPreferences] = useState<ProductPreferences>(DEFAULT_PRODUCT_PREFERENCES);

  useEffect(() => setPreferences(loadProductPreferences()), []);

  const update = <K extends keyof ProductPreferences>(key: K, value: ProductPreferences[K]) => {
    setPreferences((current) => ({ ...current, [key]: value }));
  };

  const save = () => {
    setPreferences(saveProductPreferences(preferences));
    notify.success(t("common.saved"), t("preferences.savedDescription"), { id: "product-preferences-saved" });
  };

  return (
    <div className="mx-auto max-w-5xl">
      <header className="mb-8 max-w-2xl">
        <p className="text-xs font-bold uppercase tracking-[0.12em] text-[#6F4EF6]">{t("navigation.settings")}</p>
        <h2 className="mt-2 text-3xl font-semibold tracking-[-0.04em] text-[#171A24] sm:text-4xl">{t("preferences.title")}</h2>
        <p className="mt-3 text-sm leading-6 text-[#667085] sm:text-base">{t("preferences.description")}</p>
      </header>

      <div className="grid gap-6 lg:grid-cols-[minmax(0,1fr)_280px]">
        <section className="rounded-2xl border border-[#E7E7ED] bg-white p-5 shadow-[0_10px_35px_rgba(36,31,65,0.05)] sm:p-7" aria-labelledby="presentation-defaults-heading">
          <div className="mb-6 flex items-center gap-3">
            <span className="flex h-10 w-10 items-center justify-center rounded-xl bg-[#F0EDFF] text-[#6344E8]"><Presentation className="h-4 w-4" aria-hidden="true" /></span>
            <h3 id="presentation-defaults-heading" className="text-base font-semibold text-[#20232D]">{t("preferences.presentationDefaults")}</h3>
          </div>
          <div className="grid gap-5 sm:grid-cols-2">
            <label className="space-y-2 text-sm font-semibold text-[#303442]">
              <span>{t("preferences.presentationLanguage")}</span>
              <select value={preferences.presentationLanguage} onChange={(event) => update("presentationLanguage", event.target.value)} className={fieldClass}>
                {Object.values(LanguageType).map((language) => <option key={language} value={language}>{language}</option>)}
              </select>
            </label>
            <label className="space-y-2 text-sm font-semibold text-[#303442]">
              <span>{t("preferences.slideCount")}</span>
              <select value={preferences.slideCount} onChange={(event) => update("slideCount", event.target.value)} className={fieldClass}>
                {["5", "8", "10", "12", "15", "20"].map((count) => <option key={count} value={count}>{t("generation.slideCount", { count })}</option>)}
              </select>
            </label>
          </div>

          <fieldset className="mt-7">
            <legend className="mb-3 flex items-center gap-2 text-sm font-semibold text-[#303442]"><LayoutTemplate className="h-4 w-4 text-[#6F4EF6]" />{t("preferences.designStyle")}</legend>
            <div className="grid grid-cols-2 gap-2 sm:grid-cols-5" role="radiogroup" aria-label={t("preferences.designStyle")}>
              {DESIGN_STYLES.map((style) => <PreferenceButton key={style} selected={preferences.designStyle === style} onClick={() => update("designStyle", style)}>{t(`preferences.design.${style}`)}</PreferenceButton>)}
            </div>
          </fieldset>

          <fieldset className="mt-7">
            <legend className="mb-3 flex items-center gap-2 text-sm font-semibold text-[#303442]"><Palette className="h-4 w-4 text-[#6F4EF6]" />{t("preferences.colorPalette")}</legend>
            <div className="grid grid-cols-2 gap-2 sm:grid-cols-5" role="radiogroup" aria-label={t("preferences.colorPalette")}>
              {COLOR_PALETTES.map((palette) => <PreferenceButton key={palette} selected={preferences.colorPalette === palette} onClick={() => update("colorPalette", palette)}>{t(`preferences.palette.${palette}`)}</PreferenceButton>)}
            </div>
          </fieldset>

          <div className="mt-7 grid gap-6 sm:grid-cols-2">
            <fieldset>
              <legend className="mb-3 flex items-center gap-2 text-sm font-semibold text-[#303442]"><Monitor className="h-4 w-4 text-[#6F4EF6]" />{t("preferences.aspectRatio")}</legend>
              <div className="grid grid-cols-2 gap-2" role="radiogroup" aria-label={t("preferences.aspectRatio")}>{ASPECT_RATIOS.map((ratio) => <PreferenceButton key={ratio} selected={preferences.aspectRatio === ratio} onClick={() => update("aspectRatio", ratio)}>{ratio}</PreferenceButton>)}</div>
            </fieldset>
            <fieldset>
              <legend className="mb-3 flex items-center gap-2 text-sm font-semibold text-[#303442]"><ImageIcon className="h-4 w-4 text-[#6F4EF6]" />{t("preferences.imagePreference")}</legend>
              <div className="space-y-2" role="radiogroup" aria-label={t("preferences.imagePreference")}>{IMAGE_PREFERENCES.map((images) => <PreferenceButton key={images} selected={preferences.imagePreference === images} onClick={() => update("imagePreference", images)}>{t(`preferences.images.${images}`)}</PreferenceButton>)}</div>
            </fieldset>
          </div>

          <Button onClick={save} className="mt-8 min-h-11 rounded-xl bg-[#6F4EF6] px-6 text-sm font-semibold text-white hover:bg-[#6242E8] focus-visible:ring-[#6F4EF6]">{t("preferences.save")}</Button>
        </section>

        <aside className="space-y-6">
          <section className="rounded-2xl border border-[#E7E7ED] bg-white p-5">
            <h3 className="text-sm font-semibold text-[#20232D]">{t("account.interfaceLanguage")}</h3>
            <p className="mt-1 text-xs leading-5 text-[#667085]">{t("generation.presentationLanguageHelp")}</p>
            <div className="mt-4"><LocaleSwitcher /></div>
          </section>
          <section className="rounded-2xl border border-[#E7E7ED] bg-white p-5">
            <h3 className="text-sm font-semibold text-[#20232D]">{t("preferences.motion")}</h3>
            <div className="mt-4 space-y-2" role="radiogroup" aria-label={t("preferences.motion")}>
              {MOTION_PREFERENCES.map((motion) => <PreferenceButton key={motion} selected={preferences.motion === motion} onClick={() => update("motion", motion)}>{motion === "reduced" ? t("preferences.motionReduced") : t("preferences.motionSystem")}</PreferenceButton>)}
            </div>
          </section>
        </aside>
      </div>
    </div>
  );
}

function PreferenceButton({ selected, onClick, children }: { selected: boolean; onClick: () => void; children: React.ReactNode }) {
  return (
    <button type="button" role="radio" aria-checked={selected} onClick={onClick} className={`flex min-h-11 w-full items-center justify-between gap-2 rounded-xl border px-3 py-2 text-start text-xs font-semibold transition focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[#6F4EF6] ${selected ? "border-[#8D79F6] bg-[#F5F2FF] text-[#5538D7]" : "border-[#E7E7ED] bg-white text-[#4B5565] hover:border-[#CFC7F8]"}`}>
      <span>{children}</span>{selected && <Check className="h-3.5 w-3.5 shrink-0" aria-hidden="true" />}
    </button>
  );
}
