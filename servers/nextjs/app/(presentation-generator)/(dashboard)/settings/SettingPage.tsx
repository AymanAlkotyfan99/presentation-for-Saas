"use client";
import React, { useState, useEffect, useCallback } from "react";
import { Loader2, ChevronRight } from "lucide-react";
import { notify } from "@/components/ui/sonner";
import { RootState } from "@/store/store";
import { useSelector } from "react-redux";
import {
  getImageProviderConfigValidationError,
  getTextProviderConfigValidationError,
  getWebSearchProviderConfigValidationError,
  handleSaveLLMConfig,
  type ProviderConfigSection,
} from "@/utils/storeHelpers";
import { isOllamaModelAvailable } from "@/utils/providerUtils";
import { useRouter, usePathname } from "next/navigation";
import { LLMConfig } from "@/types/llm_config";
import { trackEvent, MixpanelEvent } from "@/utils/mixpanel";
import SettingSideBar, { SettingsSection } from "./SettingSideBar";
import TextProvider from "./TextProvider";
import ImageProvider from "./ImageProvider";
import WebSearchProvider from "./WebSearchProvider";
import PrivacySettings from "./PrivacySettings";
import {
  IMAGE_PROVIDERS,
  LLM_PROVIDERS,
  WEB_SEARCH_PROVIDERS,
} from "@/utils/providerConstants";
import { ImagesApi } from "@/app/(presentation-generator)/services/api/images";
import { getApiUrl } from "@/utils/api";
import LogoutButton from "@/components/Auth/LogoutButton";
import AdminPanel from "../admin/AdminPanel";
import {
  CHATGPT_AUTH_REQUIRED_EVENT,
  requestChatGptReauth,
} from "@/utils/chatgptAuth";
import { useI18n } from "@/i18n/catalog";
import { localizePathname } from "@/i18n/routing";
import { ProviderRegistryPanel } from "@/features/providers/ProviderRegistryPanel";
import { ApiResponseError } from "@/app/(presentation-generator)/services/api/api-error-handler";

const STOCK_IMAGE_PROVIDERS = new Set(["pexels", "pixabay"]);

// Button state interface
interface ButtonState {
  isLoading: boolean;
  isDisabled: boolean;
  text: string;
  showProgress: boolean;
  progressPercentage?: number;
  status?: string;
}

const SettingsPage = () => {
  const { locale, t } = useI18n();
  const router = useRouter();
  const pathname = usePathname();
  const [selectedProvider, setSelectedProvider] = useState<SettingsSection>("text-provider");
  const userConfigState = useSelector((state: RootState) => state.userConfig);
  const [llmConfig, setLlmConfig] = useState<LLMConfig>(
    userConfigState.llm_config
  );
  const canChangeKeys = userConfigState.can_change_keys;
  const [buttonState, setButtonState] = useState<ButtonState>({
    isLoading: false,
    isDisabled: false,
    text: t("common.save"),
    showProgress: false,
  });

  const handleTextProviderInputChange = useCallback(
    (value: string | boolean, field: string) => {
      setLlmConfig((prev) => ({
        ...prev,
        [field]: value,
      }));
    },
    []
  );

  useEffect(() => {
    setLlmConfig(userConfigState.llm_config);
  }, [userConfigState.llm_config]);

  useEffect(() => {
    const handleChatGptReauth = () => {
      setSelectedProvider("text-provider");
    };

    window.addEventListener(CHATGPT_AUTH_REQUIRED_EVENT, handleChatGptReauth);
    return () => {
      window.removeEventListener(CHATGPT_AUTH_REQUIRED_EVENT, handleChatGptReauth);
    };
  }, []);

  const selectSettingsSection = (section: SettingsSection) => {
    trackEvent(MixpanelEvent.Settings_Tab_Switched, {
      from_section: selectedProvider,
      to_section: section,
    });
    setSelectedProvider(section);
  };

  useEffect(() => {
    trackEvent(MixpanelEvent.Settings_Section_Entered, {
      section: selectedProvider,
      image_generation_enabled: !llmConfig.DISABLE_IMAGE_GENERATION,
      web_search_enabled: !!llmConfig.WEB_GROUNDING,
    });
  }, [selectedProvider, llmConfig.DISABLE_IMAGE_GENERATION, llmConfig.WEB_GROUNDING]);

  const ensureSelectedStockProviderReady = async (): Promise<boolean> => {
    if (llmConfig.DISABLE_IMAGE_GENERATION) {
      return true;
    }

    const provider = (llmConfig.IMAGE_PROVIDER || "").toLowerCase();
    if (!STOCK_IMAGE_PROVIDERS.has(provider)) {
      return true;
    }

    const providerApiKey =
      provider === "pexels" ? llmConfig.PEXELS_API_KEY : llmConfig.PIXABAY_API_KEY;

    await ImagesApi.searchStockImages("business", 1, {
      provider,
      apiKey: providerApiKey,
      strictApiKey: true,
    });
    return true;
  };


  const checkCurrentAuthStatus = async () => {
    try {
      const res = await fetch(getApiUrl("/api/v1/ppt/codex/auth/status"));
      if (!res.ok) {
        return false;
      }
      const data = await res.json();
      if (data.status === "authenticated") {
        return true;
      } else {
        return false;
      }
    } catch {
      return false;
    }
  };
  const handleSaveConfig = async () => {
    const persistenceSection: ProviderConfigSection | null =
      selectedProvider === "text-provider"
        ? "text"
        : selectedProvider === "image-provider"
          ? "image"
          : selectedProvider === "web-search-provider"
            ? "web-search"
            : null;
    if (!persistenceSection) return;

    if (persistenceSection === "text" && llmConfig.LLM === 'codex') {
      const isAuthenticated = await checkCurrentAuthStatus();
      if (!isAuthenticated) {
        requestChatGptReauth({
          message: "Please sign in to ChatGPT again from Settings.",
          source: "settings-save",
        });
        return;
      }
    }
    trackEvent(MixpanelEvent.Settings_SaveConfiguration_Button_Clicked, {
      pathname,
    });
    const validationError = persistenceSection === "text"
      ? getTextProviderConfigValidationError(llmConfig)
      : persistenceSection === "image"
        ? getImageProviderConfigValidationError(llmConfig)
        : getWebSearchProviderConfigValidationError(llmConfig);
    if (validationError) {
      const validationMessage = persistenceSection === "text"
        ? t("settings.textValidationFailed")
        : persistenceSection === "image"
          ? t("settings.imageValidationFailed")
          : t("settings.webSearchValidationFailed");
      const validationDescription = persistenceSection === "text"
        ? t("settings.textValidationDescription")
        : persistenceSection === "image"
          ? t("settings.imageValidationDescription")
          : t("settings.webSearchValidationDescription");
      notify.warning(validationMessage, validationDescription);
      return;
    }

    try {
      setButtonState((prev) => ({
        ...prev,
        isLoading: true,
        isDisabled: true,
        text: t("common.saving"),
      }));
      trackEvent(MixpanelEvent.Settings_SaveConfiguration_API_Call);
      if (persistenceSection === "image") {
        await ensureSelectedStockProviderReady();
      }
      if (
        persistenceSection === "text" &&
        llmConfig.LLM === "ollama" &&
        llmConfig.OLLAMA_MODEL &&
        !(await isOllamaModelAvailable(
          llmConfig.OLLAMA_MODEL,
          llmConfig.OLLAMA_URL
        ))
      ) {
        throw new Error(
          `The selected model "${llmConfig.OLLAMA_MODEL}" is not available at ${llmConfig.OLLAMA_URL}. Check models and select an available model.`
        );
      }
      await handleSaveLLMConfig(llmConfig, { section: persistenceSection });
      notify.success(
        t("settings.saved"),
        t("settings.saved")
      );
      setButtonState((prev) => ({
        ...prev,
        isLoading: false,
        isDisabled: false,
        text: t("common.save"),
      }));
    } catch (error) {
      const providerErrorMessages: Record<string, string> = {
        IMAGE_PROVIDER_DNS_UNAVAILABLE: t("settings.imageProviderDnsUnavailable"),
        IMAGE_PROVIDER_TIMEOUT: t("settings.imageProviderTimedOut"),
        IMAGE_PROVIDER_UNREACHABLE: t("settings.imageProviderUnreachable"),
        IMAGE_PROVIDER_DESTINATION_BLOCKED: t("settings.imageProviderDestinationBlocked"),
        IMAGE_PROVIDER_CREDENTIALS_REJECTED: t("settings.imageProviderCredentialsRejected"),
        IMAGE_PROVIDER_RATE_LIMITED: t("settings.imageProviderRateLimited"),
        IMAGE_PROVIDER_REQUEST_REJECTED: t("settings.imageProviderRequestRejected"),
        IMAGE_PROVIDER_UPSTREAM_ERROR: t("settings.imageProviderUpstreamError"),
        IMAGE_PROVIDER_RESPONSE_INVALID: t("settings.imageProviderResponseInvalid"),
      };
      const message = error instanceof ApiResponseError && error.code
        ? providerErrorMessages[error.code] || error.message
        : error instanceof Error
          ? error.message
          : t("settings.saveFailed");
      notify.error(t("settings.saveFailed"), message);
      setButtonState((prev) => ({
        ...prev,
        isLoading: false,
        isDisabled: false,
        text: t("common.save"),
      }));
    }
  };

  useEffect(() => {
    if (!canChangeKeys) {
      router.push(localizePathname("/dashboard", locale));
    }
  }, [canChangeKeys, locale, router]);

  if (!canChangeKeys) {
    return null;
  }

  const textProviderKey = llmConfig.LLM || "openai";
  const textProviderLabel =
    LLM_PROVIDERS[textProviderKey]?.label || textProviderKey;
  const selectedTextModel =
    textProviderKey === "openai"
      ? llmConfig.OPENAI_MODEL
      : textProviderKey === "deepseek"
        ? llmConfig.DEEPSEEK_MODEL
      : textProviderKey === "google"
        ? llmConfig.GOOGLE_MODEL
        : textProviderKey === "vertex"
          ? llmConfig.VERTEX_MODEL
          : textProviderKey === "azure"
            ? llmConfig.AZURE_OPENAI_MODEL
          : textProviderKey === "bedrock"
            ? llmConfig.BEDROCK_MODEL
            : textProviderKey === "openrouter"
              ? llmConfig.OPENROUTER_MODEL
              : textProviderKey === "fireworks"
                ? llmConfig.FIREWORKS_MODEL
                : textProviderKey === "together"
                  ? llmConfig.TOGETHER_MODEL
              : textProviderKey === "cerebras"
                ? llmConfig.CEREBRAS_MODEL
                : textProviderKey === "litellm"
                    ? llmConfig.LITELLM_MODEL
                    : textProviderKey === "lmstudio"
                      ? llmConfig.LMSTUDIO_MODEL
                    : textProviderKey === "anthropic"
                      ? llmConfig.ANTHROPIC_MODEL
                      : textProviderKey === "ollama"
                        ? llmConfig.OLLAMA_MODEL
                        : textProviderKey === "custom"
                          ? llmConfig.CUSTOM_MODEL
                          : textProviderKey === "codex"
                            ? llmConfig.CODEX_MODEL
                            : "";
  const textSummary = selectedTextModel
    ? `${textProviderLabel} (${selectedTextModel})`
    : textProviderLabel;

  const imageSummary = llmConfig.DISABLE_IMAGE_GENERATION
    ? t("settings.imageGenerationDisabled")
    : llmConfig.IMAGE_PROVIDER
      ? IMAGE_PROVIDERS[llmConfig.IMAGE_PROVIDER]?.label ||
      llmConfig.IMAGE_PROVIDER
      : t("settings.noImageProvider");
  const webSearchProviderKey = (llmConfig.WEB_SEARCH_PROVIDER || "").toLowerCase();
  const webSearchSummary = llmConfig.WEB_GROUNDING
    ? t("settings.webProvider", {
        provider: WEB_SEARCH_PROVIDERS[webSearchProviderKey]?.label || t("settings.noProvider"),
      })
    : t("settings.webSearchDisabled");


  useEffect(() => {

    if (
      (llmConfig.LLM === "codex" && !llmConfig.CODEX_MODEL) ||
      (llmConfig.LLM === "openai" && !llmConfig.OPENAI_MODEL) ||
      (llmConfig.LLM === "deepseek" && !llmConfig.DEEPSEEK_MODEL) ||
      (llmConfig.LLM === "google" && !llmConfig.GOOGLE_MODEL) ||
      (llmConfig.LLM === "vertex" && !llmConfig.VERTEX_MODEL) ||
      (llmConfig.LLM === "azure" && !llmConfig.AZURE_OPENAI_MODEL) ||
      (llmConfig.LLM === "bedrock" && !llmConfig.BEDROCK_MODEL) ||
      (llmConfig.LLM === "openrouter" && !llmConfig.OPENROUTER_MODEL) ||
      (llmConfig.LLM === "fireworks" && !llmConfig.FIREWORKS_MODEL) ||
      (llmConfig.LLM === "together" && !llmConfig.TOGETHER_MODEL) ||
      (llmConfig.LLM === "cerebras" && !llmConfig.CEREBRAS_MODEL) ||
      (llmConfig.LLM === "litellm" && !llmConfig.LITELLM_MODEL) ||
      (llmConfig.LLM === "lmstudio" && !llmConfig.LMSTUDIO_MODEL) ||
      (llmConfig.LLM === "anthropic" && !llmConfig.ANTHROPIC_MODEL) ||
      (llmConfig.LLM === "ollama" &&
        (!llmConfig.OLLAMA_URL?.trim() || !llmConfig.OLLAMA_MODEL)) ||
      (llmConfig.LLM === "custom" && !llmConfig.CUSTOM_MODEL)
    ) {
      const currentUrl = window.location.href;

      const handleBeforeUnload = (e: BeforeUnloadEvent) => {
        console.log("beforeunload");
        e.preventDefault();
        e.returnValue = "";
      };

      const handleClick = (e: MouseEvent) => {


        const target = e.target as HTMLElement | null;
        const link = target?.closest("a");

        if (!link) return;

        const href = link.getAttribute("href");
        const targetAttr = link.getAttribute("target");

        if (
          href &&
          href !== "#" &&
          !href.startsWith("javascript:") &&
          targetAttr !== "_blank"
        ) {

          // notify.error("Cannot save settings", "Please select a model for the selected provider");
          e.preventDefault();
          window.history.pushState(null, "", pathname);
        }
      };

      const handlePopState = () => {
        console.log("popstate");
        window.history.pushState(null, "", pathname);
      };

      window.addEventListener("beforeunload", handleBeforeUnload);
      window.addEventListener("popstate", handlePopState);
      document.addEventListener("click", handleClick, true);

      // keep current page in history
      window.history.pushState(null, "", currentUrl);

      return () => {
        window.removeEventListener("beforeunload", handleBeforeUnload);
        window.removeEventListener("popstate", handlePopState);
        document.removeEventListener("click", handleClick, true);
      };
    }

  }, [llmConfig, pathname]);



  return (
    <div className="h-screen font-syne flex flex-col overflow-hidden relative">
      <main className="w-full mx-auto gap-6   overflow-hidden flex ">
        <SettingSideBar
          selectedProvider={selectedProvider}
          setSelectedProvider={selectSettingsSection}
        />
        <div className="w-full">
          <div className="sticky top-0 end-0 z-50 py-[28px] backdrop-blur mb-4 ">
            <div className="flex  gap-3 items-center ">
              <h3 className=" text-[28px] tracking-[-0.84px] font-unbounded font-normal text-black flex items-center gap-2">
                {t("settings.title")}
              </h3>
              <p className="text-[10px] px-2.5 py-0.5 rounded-[50px] text-[#7A5AF8] border border-[#EDEEEF]  font-medium ">
                {textSummary} · {imageSummary} · {webSearchSummary}
              </p>
            </div>
          </div>

          {selectedProvider === 'text-provider' && <TextProvider
            onInputChange={handleTextProviderInputChange}
            llmConfig={llmConfig}
          />}
          {selectedProvider === 'image-provider' && <ImageProvider llmConfig={llmConfig} setLlmConfig={setLlmConfig} />}
          {selectedProvider === 'web-search-provider' && <WebSearchProvider llmConfig={llmConfig} setLlmConfig={setLlmConfig} />}
          {selectedProvider === 'provider-registry' && <ProviderRegistryPanel />}
          {selectedProvider === 'privacy' && <PrivacySettings />}
          {selectedProvider === "admin" && <AdminPanel embedded />}
          {selectedProvider === "session" && (
            <div className="w-full max-w-lg space-y-5 rounded-[20px] border border-[#EDEEEF] bg-white p-7">
              <div>
                <h4 className="font-unbounded text-lg font-normal text-black">{t("navigation.logout")}</h4>
                <p className="mt-2 font-syne text-sm leading-relaxed text-[#494A4D]">
                  {t("auth.sessionExpired")}
                </p>
              </div>
              <LogoutButton
                label={t("navigation.logout")}
                className="inline-flex w-full items-center justify-center gap-2 rounded-[58px] border border-[#EDEEEF] bg-[#7C51F8] px-5 py-3 font-syne text-xs font-semibold text-white transition hover:bg-[#6d46e6] disabled:cursor-not-allowed disabled:opacity-60"
              />
            </div>
          )}

        </div>
      </main>

      {/* Fixed Bottom Button — hidden on Sign out; nothing to save there */}
      {!['session', 'admin', 'provider-registry', 'privacy'].includes(selectedProvider) ? (
        <div className="mx-auto fixed bottom-20 end-5">
          <button
            onClick={handleSaveConfig}
            disabled={buttonState.isDisabled}
            style={{
              background:
                "linear-gradient(270deg, #D5CAFC 2.4%, #E3D2EB 27.88%, #F4DCD3 69.23%, #FDE4C2 100%)",
              color: "#101323",
            }}
            className={`w-full font-syne font-semibold flex items-center justify-center gap-2 py-3 px-5 rounded-[58px] transition-all duration-500 ${buttonState.isDisabled
              ? "bg-gray-400 cursor-not-allowed"
              : "bg-gradient-to-r from-blue-600 to-indigo-600 hover:from-blue-700 hover:to-indigo-700 focus:ring-4 focus:ring-blue-200"
              } text-white`}
          >
            {buttonState.isLoading ? (
              <div className="flex items-center justify-center gap-2">
                <Loader2 className="w-4 h-4 animate-spin" />
                {buttonState.text}
              </div>
            ) : (
              buttonState.text
            )}
            <ChevronRight className="w-4 h-4" />
          </button>
        </div>
      ) : null}

    </div>
  );
};

export default SettingsPage;
