"use client";
import React, { useCallback, useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { ChevronRight } from "lucide-react";
import CreateCustomTemplate from "./CreateCustomTemplate";
import Link from "next/link";
import { trackEvent, MixpanelEvent } from "@/utils/mixpanel";
import { useTemplateSummaries, TemplateTab } from "../../../hooks/useTemplateSummaries";
import {
  ProcessingTemplateListCard,
  TemplateListCard,
  TemplateTabSwitcher,
  TemplateListLoadingState,
  TemplateListEmptyState,
} from "../../../components/TemplateListUi";
import { useI18n } from "@/i18n/catalog";
import { localizePathname } from "@/i18n/routing";

const LayoutPreview = () => {
  const { locale, t } = useI18n();
  const [tab, setTab] = useState<TemplateTab>("default");
  const router = useRouter();
  const {
    defaultTemplates,
    customTemplates,
    processingTemplateTasks,
    loading,
  } = useTemplateSummaries({ includeProcessingTemplateTasks: true });

  useEffect(() => {
    const requestedTab = new URLSearchParams(window.location.search).get("tab");
    if (requestedTab === "custom" || requestedTab === "default") {
      setTab(requestedTab);
    }

    trackEvent(MixpanelEvent.Templates_Page_Viewed);
  }, []);

  const handleOpenTemplate = useCallback(
    (templateId: string, isDefault: boolean) => {
      trackEvent(
        isDefault
          ? MixpanelEvent.Templates_Inbuilt_Opened
          : MixpanelEvent.Templates_Custom_Opened,
        {
          template_id: templateId,
        }
      );
      router.push(`${localizePathname("/template-preview", locale)}?templateV2Id=${encodeURIComponent(templateId)}`);
    },
    [locale, router]
  );

  const handleTabChange = useCallback((nextTab: TemplateTab) => {
    trackEvent(MixpanelEvent.Templates_Tab_Switched, { tab: nextTab });
    setTab(nextTab);
  }, []);

  const activeTemplates = tab === "default" ? defaultTemplates : customTemplates;

  return (
    <div className="min-h-screen relative font-syne">
      <div className="sticky top-0 end-0 z-50 py-[28px] px-6 backdrop-blur">
        <div className="flex xl:flex-row flex-col gap-6 xl:gap-0 items-center justify-between">
          <h3 className="text-[28px] tracking-[-0.84px] font-unbounded font-normal text-[#101828] flex items-center gap-2">
            {t("templates.title")}
          </h3>
          <div className="flex gap-2.5 max-sm:w-full max-md:justify-center max-sm:flex-wrap">
            <Link
              href={localizePathname("/custom-template", locale)}
              onClick={() => trackEvent(MixpanelEvent.Templates_New_Template_Clicked)}
              className="inline-flex items-center font-syne font-semibold gap-2 rounded-xl px-4 py-2.5 text-black text-sm shadow-sm hover:shadow-md"
              aria-label={t("templates.createCustom")}
              style={{
                borderRadius: "48px",
                background:
                  "linear-gradient(270deg, #D5CAFC 2.4%, #E3D2EB 27.88%, #F4DCD3 69.23%, #FDE4C2 100%)",
              }}
            >
              <span className="hidden md:inline">{t("templates.newTemplate")}</span>
              <span className="md:hidden">{t("templates.new")}</span>
              <ChevronRight className="w-4 h-4 rtl:rotate-180" />
            </Link>
          </div>
        </div>
      </div>

      <div className="mx-auto px-6 py-8">
        <TemplateTabSwitcher tab={tab} onTabChange={handleTabChange} />

        <section className="my-12">
          {loading ? (
            <TemplateListLoadingState />
          ) : tab === "custom" ? (
            <div className="grid grid-cols-1 items-center gap-6 md:grid-cols-2 xl:grid-cols-3 2xl:grid-cols-4">
              <CreateCustomTemplate />
              {processingTemplateTasks.map((task) => (
                <ProcessingTemplateListCard key={task.id} task={task} />
              ))}
              {customTemplates.map((template) => (
                <TemplateListCard
                  key={template.id}
                  template={template}
                  showArrow
                  onClick={() => handleOpenTemplate(template.id, false)}
                />
              ))}
            </div>
          ) : activeTemplates.length === 0 ? (
            <TemplateListEmptyState message={t("templates.noBuiltIn")} />
          ) : (
            <div className="grid grid-cols-1 gap-6 md:grid-cols-2 xl:grid-cols-3 2xl:grid-cols-4">
              {activeTemplates.map((template) => (
                <TemplateListCard
                  key={template.id}
                  template={template}
                  showArrow
                  onClick={() => handleOpenTemplate(template.id, true)}
                />
              ))}
            </div>
          )}
        </section>
      </div>
    </div>
  );
};

export default LayoutPreview;
