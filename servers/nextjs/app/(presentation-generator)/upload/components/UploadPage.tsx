/**
 * UploadPage Component
 * 
 * This component handles the presentation generation upload process, allowing users to:
 * - Configure presentation settings (slides, language)
 * - Input prompts
 * - Upload supporting documents
 * 
 * @component
 */

"use client";
import React, { useEffect, useState } from "react";
import { useRouter, usePathname } from "next/navigation";
import { useDispatch, useSelector } from "react-redux";
import { clearOutlines, setPresentationId } from "@/store/slices/presentationGeneration";
import { PromptInput } from "./PromptInput";
import { LanguageType, PresentationConfig, ToneType, VerbosityType } from "../type";
import SupportingDoc from "./SupportingDoc";
import { Button } from "@/components/ui/button";
import { ChevronRight, Image as ImageIcon, LayoutTemplate, Palette, RectangleHorizontal, Sparkles } from "lucide-react";
import { notify } from "@/components/ui/sonner";
import { PresentationGenerationApi } from "../../services/api/presentation-generation";
import { OverlayLoader } from "@/components/ui/overlay-loader";
import { setPptGenUploadState } from "@/store/slices/presentationGenUpload";
import { trackEvent, MixpanelEvent } from "@/utils/mixpanel";
import { ConfigurationSelects } from "./ConfigurationSelects";
import { RootState } from "@/store/store";
import { ImagesApi } from "../../services/api/images";
import { LLMConfig } from "@/types/llm_config";
import {
  clampSlideCountValue,
  parseLimitedSlideCount,
} from "@/utils/presentationLimits";
import { useI18n } from "@/i18n/catalog";
import { localizePathname } from "@/i18n/routing";
import {
  ASPECT_RATIOS,
  COLOR_PALETTES,
  DEFAULT_PRODUCT_PREFERENCES,
  DESIGN_STYLES,
  IMAGE_PREFERENCES,
  loadProductPreferences,
  productPreferenceInstructions,
  saveProductPreferences,
  type ProductPreferences,
} from "@/lib/product-preferences";

const STOCK_IMAGE_PROVIDERS = new Set(["pexels", "pixabay"]);
const FILE_TYPE_WORD = new Set([".doc", ".docx", ".docm", ".odt", ".rtf"]);
const FILE_TYPE_PRESENTATION = new Set([".ppt", ".pptx", ".pptm", ".odp"]);
const FILE_TYPE_SPREADSHEET = new Set([".xls", ".xlsx", ".xlsm", ".ods", ".csv", ".tsv"]);
const FILE_TYPE_IMAGE = new Set([".jpg", ".jpeg", ".png", ".gif", ".bmp", ".tiff", ".webp"]);
const FILE_MIME_IMAGE = new Set(["image/jpeg", "image/png", "image/gif", "image/bmp", "image/tiff", "image/webp"]);
const FILE_TYPE_PDF = new Set([".pdf"]);
const FILE_TYPE_TEXT = new Set([".txt"]);

const PALETTE_COLORS: Record<ProductPreferences["colorPalette"], string[]> = {
  violet: ["#6F4EF6", "#B9A9FF", "#F0EDFF"],
  ocean: ["#126E82", "#5BB7C7", "#E8F7F8"],
  forest: ["#2E6F5E", "#75B798", "#ECF7F1"],
  sunset: ["#D65A4A", "#F4A261", "#FFF0E8"],
  mono: ["#20232D", "#858B98", "#F1F2F4"],
};

// Types for loading state
interface LoadingState {
  isLoading: boolean;
  message: string;
  duration?: number;
  showProgress?: boolean;
  extra_info?: string;
}

const getFileExtension = (fileName: string): string => {
  const index = fileName.lastIndexOf(".");
  if (index < 0) return "";
  return fileName.slice(index).toLowerCase();
};

const getFileCategory = (file: File): string => {
  const extension = getFileExtension(file.name || "");
  if (FILE_TYPE_WORD.has(extension)) return "word";
  if (FILE_TYPE_PRESENTATION.has(extension)) return "presentation";
  if (FILE_TYPE_SPREADSHEET.has(extension)) return "spreadsheet";
  if (FILE_TYPE_IMAGE.has(extension) || FILE_MIME_IMAGE.has((file.type || "").toLowerCase())) return "image";
  if (FILE_TYPE_PDF.has(extension) || file.type === "application/pdf") return "pdf";
  if (FILE_TYPE_TEXT.has(extension) || file.type === "text/plain") return "text";
  return "other";
};

const getSelectedTextModel = (config?: LLMConfig): string => {
  if (!config) return "";
  switch (config.LLM) {
    case "openai":
      return config.OPENAI_MODEL || "";
    case "deepseek":
      return config.DEEPSEEK_MODEL || "";
    case "google":
      return config.GOOGLE_MODEL || "";
    case "vertex":
      return config.VERTEX_MODEL || "";
    case "azure":
      return config.AZURE_OPENAI_MODEL || "";
    case "bedrock":
      return config.BEDROCK_MODEL || "";
    case "openrouter":
      return config.OPENROUTER_MODEL || "";
    case "fireworks":
      return config.FIREWORKS_MODEL || "";
    case "together":
      return config.TOGETHER_MODEL || "";
    case "cerebras":
      return config.CEREBRAS_MODEL || "";
    case "litellm":
      return config.LITELLM_MODEL || "";
    case "lmstudio":
      return config.LMSTUDIO_MODEL || "";
    case "anthropic":
      return config.ANTHROPIC_MODEL || "";
    case "ollama":
      return config.OLLAMA_MODEL || "";
    case "custom":
      return config.CUSTOM_MODEL || "";
    case "codex":
      return config.CODEX_MODEL || "";
    default:
      return "";
  }
};

const getSelectedImageQuality = (config?: LLMConfig): string => {
  if (!config) return "";
  if (config.IMAGE_PROVIDER === "dall-e-3") return config.DALL_E_3_QUALITY || "";
  if (config.IMAGE_PROVIDER === "gpt-image-1.5") return config.GPT_IMAGE_1_5_QUALITY || "";
  return "";
};

const getDocumentPaths = (files: unknown): string[] => {
  if (!Array.isArray(files)) {
    return [];
  }

  return files
    .flat()
    .map((file) =>
      file && typeof file === "object" && "file_path" in file
        ? (file as { file_path?: unknown }).file_path
        : null
    )
    .filter((filePath): filePath is string => typeof filePath === "string");
};

const UploadPage = () => {
  const { locale, t } = useI18n();
  const router = useRouter();
  const pathname = usePathname();
  const dispatch = useDispatch();
  const llmConfig = useSelector((state: RootState) => state.userConfig.llm_config);

  const [files, setFiles] = useState<File[]>([]);
  const [preferences, setPreferences] = useState<ProductPreferences>(DEFAULT_PRODUCT_PREFERENCES);
  const [config, setConfig] = useState<PresentationConfig>({
    slides: null,
    language: LanguageType.Auto,
    prompt: "",
    tone: ToneType.Default,
    verbosity: VerbosityType.Standard,
    instructions: "",
    includeTableOfContents: false,
    includeTitleSlide: false,
    webSearch: false,
  });

  useEffect(() => {
    const stored = loadProductPreferences();
    setPreferences(stored);
    setConfig((current) => ({
      ...current,
      slides: stored.slideCount,
      language: stored.presentationLanguage as LanguageType,
    }));
  }, []);

  useEffect(() => {
    if (llmConfig?.WEB_GROUNDING !== undefined) {
      setConfig((current) => ({
        ...current,
        webSearch: !!llmConfig.WEB_GROUNDING,
      }));
    }
  }, [llmConfig?.WEB_GROUNDING]);

  const [loadingState, setLoadingState] = useState<LoadingState>({
    isLoading: false,
    message: "",
    duration: 4,
    showProgress: false,
    extra_info: "",
  });

  const getUploadSnapshotProps = () => {
    const trimmedPrompt = config.prompt.trim();
    const trimmedInstructions = (config.instructions || "").trim();
    const attachmentCategories = Array.from(new Set(files.map(getFileCategory))).sort();
    const imageGenerationEnabled = !llmConfig?.DISABLE_IMAGE_GENERATION;
    const parsedSlides = parseLimitedSlideCount(config.slides);

    return {
      pathname,
      generation_path: files.length > 0 ? "documents" : "prompt_only",
      slides_selected: parsedSlides,
      slides_mode: config.slides ? "selected" : "auto",
      language: config.language || "",
      tone: config.tone,
      verbosity: config.verbosity,
      include_table_of_contents: !!config.includeTableOfContents,
      include_title_slide: !!config.includeTitleSlide,
      web_search: !!config.webSearch,
      has_prompt: Boolean(trimmedPrompt),
      prompt_char_count: trimmedPrompt.length,
      prompt_word_count: trimmedPrompt ? trimmedPrompt.split(/\s+/).filter(Boolean).length : 0,
      has_instructions: Boolean(trimmedInstructions),
      instructions_char_count: trimmedInstructions.length,
      has_attachments: files.length > 0,
      attachments_count: files.length,
      attachment_categories: attachmentCategories.join(","),
      text_provider: llmConfig?.LLM || "",
      text_model: getSelectedTextModel(llmConfig),
      image_generation_enabled: imageGenerationEnabled,
      image_provider: imageGenerationEnabled ? (llmConfig?.IMAGE_PROVIDER || "") : "disabled",
      image_quality: imageGenerationEnabled ? getSelectedImageQuality(llmConfig) : "",
    };
  };

  const trackUploadValidationFailure = (reason: string) => {
    trackEvent(MixpanelEvent.Upload_Configuration_Invalid, {
      ...getUploadSnapshotProps(),
      reason,
    });
  };

  const handleConfigChange = (key: keyof PresentationConfig, value: unknown) => {
    const nextValue =
      key === "slides" && typeof value === "string"
        ? clampSlideCountValue(value)
        : value;
    setConfig((prev) => ({ ...prev, [key]: nextValue } as PresentationConfig));
    if (key === "slides" && typeof nextValue === "string") {
      setPreferences((current) => ({ ...current, slideCount: nextValue }));
    }
    if (key === "language" && typeof nextValue === "string") {
      setPreferences((current) => ({ ...current, presentationLanguage: nextValue }));
    }
  };

  const updatePreference = <K extends keyof ProductPreferences>(
    key: K,
    value: ProductPreferences[K],
  ) => setPreferences((current) => ({ ...current, [key]: value }));

  const ensureStockImageProviderReady = async (): Promise<boolean> => {
    if (llmConfig?.DISABLE_IMAGE_GENERATION) {
      return true;
    }

    const selectedProvider = (llmConfig?.IMAGE_PROVIDER || "").toLowerCase();
    if (!STOCK_IMAGE_PROVIDERS.has(selectedProvider)) {
      return true;
    }

    try {
      const providerApiKey =
        selectedProvider === "pexels"
          ? llmConfig?.PEXELS_API_KEY
          : llmConfig?.PIXABAY_API_KEY;
      await ImagesApi.searchStockImages("business", 1, {
        provider: selectedProvider,
        apiKey: providerApiKey,
        strictApiKey: true,
      });
      return true;
    } catch {
      notify.error(
        t("errors.network"),
        t("errors.network")
      );
      return false;
    }
  };

  /**
   * Validates the current configuration and files
   * @returns boolean indicating if the configuration is valid
   */
  const validateConfiguration = (): boolean => {
    if (!config.language) {
      trackUploadValidationFailure("language_missing");
      notify.warning(t("validation.invalidLocale"), t("validation.invalidLocale"));
      return false;
    }

    if (files.length > 0 && config.language === LanguageType.Auto) {
      trackUploadValidationFailure("language_auto_with_documents");
      notify.warning(t("validation.invalidLocale"), t("generation.presentationLanguageHelp"));
      return false;
    }

    if (!config.prompt.trim() && files.length === 0) {
      trackUploadValidationFailure("prompt_or_document_missing");
      notify.warning(t("validation.required"), t("generation.topicPlaceholder"));
      return false;
    }
    return true;
  };

  /**
   * Handles the presentation generation process
   */
  const handleGeneratePresentation = async () => {
    if (!validateConfiguration()) return;
    saveProductPreferences({
      ...preferences,
      slideCount: config.slides || preferences.slideCount,
      presentationLanguage: config.language || preferences.presentationLanguage,
    });
    trackEvent(MixpanelEvent.Upload_Generation_Started, getUploadSnapshotProps());


    const isStockProviderReady = await ensureStockImageProviderReady();
    if (!isStockProviderReady) {
      trackUploadValidationFailure("stock_image_provider_unreachable");
      return;
    }

    try {
      const hasUploadedAssets = files.length > 0;

      if (hasUploadedAssets) {
        await handleDocumentProcessing();
      } else {
        await handleDirectPresentationGeneration();
      }
    } catch (error) {
      handleGenerationError(error);
    }
  };

  /**
   * Handles document processing
   */
  const handleDocumentProcessing = async () => {
    setLoadingState({
      isLoading: true,
      message: t("generation.processingDocuments"),
      showProgress: true,
      duration: 90,
      extra_info: files.length > 0 ? t("generation.largeDocumentsTakeTime") : "",
    });

    let documents = [];

    if (files.length > 0) {
      const uploadResponse = await PresentationGenerationApi.uploadDoc(files);
      documents = uploadResponse;
    }

    const selectedLanguage = config?.language ?? "";

    const promises: Promise<any>[] = [];

    if (documents.length > 0) {
      promises.push(
        PresentationGenerationApi.decomposeDocuments(
          documents,
          selectedLanguage
        )
      );
    }
    const responses = await Promise.all(promises);
    const documentPaths = getDocumentPaths(responses);

    setLoadingState({
      isLoading: true,
      message: t("generation.generatingOutline"),
      showProgress: true,
      duration: 40,
      extra_info: "",
    });

    const createResponse = await PresentationGenerationApi.createPresentation({
      content: config?.prompt ?? "",
      version: "v2-standard",
      n_slides: parseLimitedSlideCount(config?.slides),
      file_paths: documentPaths,
      language: selectedLanguage,
      tone: config?.tone,
      verbosity: config?.verbosity,
      instructions: productPreferenceInstructions(preferences, config?.instructions || ""),
      include_table_of_contents: !!config?.includeTableOfContents,
      include_title_slide: !!config?.includeTitleSlide,
      web_search: !!config?.webSearch,
    });

    dispatch(setPptGenUploadState({
      config,
      files: responses,
    }));
    dispatch(clearOutlines());
    dispatch(setPresentationId(createResponse.id));
    trackEvent(MixpanelEvent.Upload_Documents_Processed, {
      ...getUploadSnapshotProps(),
      uploaded_documents_count: documents.length,
      decompose_job_count: responses.length,
      extracted_document_count: documentPaths.length,
      destination: "/outline",
    });
    trackEvent(MixpanelEvent.Upload_Outline_Generation_Requested, {
      ...getUploadSnapshotProps(),
      presentation_id: createResponse.id,
      uploaded_documents_count: documents.length,
      extracted_document_count: documentPaths.length,
      destination: "/outline",
    });
    trackEvent(MixpanelEvent.Navigation, { from: pathname, to: "/outline" });
    router.push(localizePathname("/outline", locale));
  };

  /**
   * Handles direct presentation generation without documents
   */
  const handleDirectPresentationGeneration = async () => {
    setLoadingState({
      isLoading: true,
      message: t("generation.preparingOutline"),
      showProgress: true,
      duration: 30,
    });

    const selectedLanguage = config?.language ?? "";

    // Start the outline job; template selection happens on the outline page.
    const createResponse = await PresentationGenerationApi.createPresentation({
      content: config?.prompt ?? "",

      n_slides: parseLimitedSlideCount(config?.slides),
      file_paths: [],
      language: selectedLanguage,
      tone: config?.tone,
      verbosity: config?.verbosity,
      instructions: productPreferenceInstructions(preferences, config?.instructions || ""),
      include_table_of_contents: !!config?.includeTableOfContents,
      include_title_slide: !!config?.includeTitleSlide,
      web_search: !!config?.webSearch,
    });

    dispatch(setPptGenUploadState({
      config,
      files: [],
    }));
    dispatch(clearOutlines());
    dispatch(setPresentationId(createResponse.id));
    trackEvent(MixpanelEvent.Upload_Outline_Generation_Requested, {
      ...getUploadSnapshotProps(),
      presentation_id: createResponse.id,
      destination: "/outline",
    });
    trackEvent(MixpanelEvent.Navigation, { from: pathname, to: "/outline" });
    router.push(localizePathname("/outline", locale));
  };

  /**
   * Handles errors during presentation generation
   */
  const handleGenerationError = (error: unknown) => {
    console.error("Error in upload page", error);
    setLoadingState({
      isLoading: false,
      message: "",
      duration: 0,
      showProgress: false,
    });
    notify.error(
      t("generation.failed"),
      t("generation.failed")
    );
  };

  return (
    <div className="mx-auto w-full max-w-6xl pb-10">
      <OverlayLoader
        show={loadingState.isLoading}
        text={loadingState.message}
        showProgress={loadingState.showProgress}
        duration={loadingState.duration}
        extra_info={loadingState.extra_info}
      />
      <header className="mb-8 max-w-3xl">
        <p className="inline-flex items-center gap-2 text-xs font-bold uppercase tracking-[0.12em] text-[#6F4EF6]">
          <Sparkles className="h-4 w-4" aria-hidden="true" /> {t("createExperience.eyebrow")}
        </p>
        <h2 className="mt-3 text-3xl font-semibold leading-tight tracking-[-0.04em] text-[#171A24] sm:text-4xl lg:text-[44px]">
          {t("createExperience.title")}
        </h2>
        <p className="mt-3 max-w-2xl text-sm leading-6 text-[#667085] sm:text-base">{t("createExperience.description")}</p>
      </header>

      <div className="grid gap-6 lg:grid-cols-[minmax(0,1.45fr)_minmax(320px,0.75fr)]">
        <div className="space-y-6">
          <section className="rounded-2xl border border-[#E7E7ED] bg-white p-4 shadow-[0_10px_35px_rgba(36,31,65,0.05)] sm:p-6" aria-labelledby="create-content-heading">
            <div className="mb-5 flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
              <h3 id="create-content-heading" className="text-base font-semibold text-[#20232D]">{t("createExperience.content")}</h3>
              <ConfigurationSelects config={config} onConfigChange={handleConfigChange} compact />
            </div>
            <PromptInput value={config.prompt} onChange={(value) => handleConfigChange("prompt", value)} />
            {!config.prompt && (
              <button
                type="button"
                onClick={() => handleConfigChange("prompt", t("createExperience.examplePrompt"))}
                className="mt-3 inline-flex min-h-10 items-center gap-2 rounded-lg px-2 text-start text-xs font-medium text-[#6344E8] transition hover:bg-[#F5F2FF] focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[#6F4EF6]"
              >
                <Sparkles className="h-3.5 w-3.5" aria-hidden="true" />
                <span><strong>{t("createExperience.exampleLabel")}:</strong> {t("createExperience.examplePrompt")}</span>
              </button>
            )}
            <p className="mt-3 text-xs text-[#858B98]">{t("createExperience.interfaceLanguageNote")}</p>
          </section>

          <section className="rounded-2xl border border-[#E7E7ED] bg-white p-4 shadow-[0_10px_35px_rgba(36,31,65,0.05)] sm:p-6" aria-labelledby="create-design-heading">
            <div className="mb-5 flex items-start gap-3">
              <span className="flex h-10 w-10 shrink-0 items-center justify-center rounded-xl bg-[#F0EDFF] text-[#6344E8]"><LayoutTemplate className="h-4 w-4" aria-hidden="true" /></span>
              <div>
                <h3 id="create-design-heading" className="text-base font-semibold text-[#20232D]">{t("createExperience.design")}</h3>
                <p className="mt-1 text-xs leading-5 text-[#667085]">{t("createExperience.designDescription")}</p>
              </div>
            </div>
            <div className="grid grid-cols-2 gap-3 sm:grid-cols-5" role="radiogroup" aria-label={t("preferences.designStyle")}>
              {DESIGN_STYLES.map((style) => (
                <button
                  key={style}
                  type="button"
                  role="radio"
                  aria-checked={preferences.designStyle === style}
                  onClick={() => updatePreference("designStyle", style)}
                  className={`group min-h-[88px] rounded-xl border p-3 text-start transition duration-200 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[#6F4EF6] ${preferences.designStyle === style ? "border-[#8D79F6] bg-[#F5F2FF] shadow-[0_6px_18px_rgba(111,78,246,0.12)]" : "border-[#E7E7ED] hover:-translate-y-0.5 hover:border-[#CFC7F8]"}`}
                >
                  <span className={`mb-3 block h-7 rounded-md ${style === "minimal" ? "bg-[#F1F2F4]" : style === "modern" ? "bg-gradient-to-r from-[#6F4EF6] to-[#B9A9FF]" : style === "academic" ? "bg-[#24516B]" : style === "business" ? "bg-[#273447]" : "bg-gradient-to-r from-[#E76F51] to-[#F4A261]"}`} aria-hidden="true" />
                  <span className="text-xs font-semibold text-[#303442]">{t(`preferences.design.${style}`)}</span>
                </button>
              ))}
            </div>
            <div className="mt-6">
              <p className="mb-3 flex items-center gap-2 text-sm font-semibold text-[#303442]"><Palette className="h-4 w-4 text-[#6F4EF6]" aria-hidden="true" />{t("createExperience.colors")}</p>
              <div className="flex flex-wrap gap-2" role="radiogroup" aria-label={t("preferences.colorPalette")}>
                {COLOR_PALETTES.map((palette) => (
                  <button
                    key={palette}
                    type="button"
                    role="radio"
                    aria-checked={preferences.colorPalette === palette}
                    aria-label={t(`preferences.palette.${palette}`)}
                    title={t(`preferences.palette.${palette}`)}
                    onClick={() => updatePreference("colorPalette", palette)}
                    className={`flex h-11 items-center gap-1 rounded-full border bg-white px-2.5 transition focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[#6F4EF6] ${preferences.colorPalette === palette ? "border-[#6F4EF6] ring-2 ring-[#6F4EF6]/15" : "border-[#E1E3E8] hover:border-[#BBB5E8]"}`}
                  >
                    {PALETTE_COLORS[palette].map((color) => <span key={color} className="h-5 w-5 rounded-full border border-black/5" style={{ backgroundColor: color }} />)}
                  </button>
                ))}
              </div>
            </div>
          </section>

          <section className="rounded-2xl border border-[#E7E7ED] bg-white p-4 shadow-[0_10px_35px_rgba(36,31,65,0.05)] sm:p-6" aria-labelledby="attachments-heading">
            <h3 id="attachments-heading" className="mb-4 text-base font-semibold text-[#20232D]">{t("createExperience.attachmentsOptional")}</h3>
            <SupportingDoc files={[...files]} onFilesChange={setFiles} />
          </section>
        </div>

        <aside className="h-fit space-y-6 lg:sticky lg:top-[104px]">
          <section className="rounded-2xl border border-[#E7E7ED] bg-white p-5 shadow-[0_10px_35px_rgba(36,31,65,0.05)]" aria-labelledby="visuals-heading">
            <div className="mb-5 flex items-start gap-3">
              <span className="flex h-10 w-10 shrink-0 items-center justify-center rounded-xl bg-[#EAF8F6] text-[#187A6D]"><ImageIcon className="h-4 w-4" aria-hidden="true" /></span>
              <div><h3 id="visuals-heading" className="text-base font-semibold text-[#20232D]">{t("createExperience.visuals")}</h3><p className="mt-1 text-xs leading-5 text-[#667085]">{t("createExperience.imagesDescription")}</p></div>
            </div>
            <div className="space-y-2" role="radiogroup" aria-label={t("createExperience.images")}>
              {IMAGE_PREFERENCES.map((imagePreference) => (
                <button
                  key={imagePreference}
                  type="button"
                  role="radio"
                  aria-checked={preferences.imagePreference === imagePreference}
                  onClick={() => updatePreference("imagePreference", imagePreference)}
                  className={`flex min-h-11 w-full items-center gap-3 rounded-xl border px-3 py-2.5 text-start text-sm font-medium transition focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[#6F4EF6] ${preferences.imagePreference === imagePreference ? "border-[#8D79F6] bg-[#F5F2FF] text-[#5538D7]" : "border-[#E7E7ED] text-[#4B5565] hover:border-[#CFC7F8]"}`}
                >
                  <span className={`h-3 w-3 rounded-full border-2 ${preferences.imagePreference === imagePreference ? "border-[#6F4EF6] bg-[#6F4EF6] shadow-[inset_0_0_0_2px_white]" : "border-[#A9AEB8]"}`} />
                  {t(`preferences.images.${imagePreference}`)}
                </button>
              ))}
            </div>
            <div className="mt-6 border-t border-[#EEEEF2] pt-5">
              <p className="mb-3 flex items-center gap-2 text-sm font-semibold text-[#303442]"><RectangleHorizontal className="h-4 w-4 text-[#6F4EF6]" aria-hidden="true" />{t("createExperience.aspectRatio")}</p>
              <div className="grid grid-cols-2 gap-2" role="radiogroup" aria-label={t("createExperience.aspectRatio")}>
                {ASPECT_RATIOS.map((ratio) => (
                  <button key={ratio} type="button" role="radio" aria-checked={preferences.aspectRatio === ratio} onClick={() => updatePreference("aspectRatio", ratio)} className={`min-h-11 rounded-xl border text-sm font-semibold transition focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[#6F4EF6] ${preferences.aspectRatio === ratio ? "border-[#8D79F6] bg-[#F5F2FF] text-[#5538D7]" : "border-[#E7E7ED] text-[#4B5565] hover:border-[#CFC7F8]"}`}>{ratio}</button>
                ))}
              </div>
            </div>
          </section>

          <Button
            onClick={handleGeneratePresentation}
            disabled={loadingState.isLoading}
            className="flex min-h-[52px] w-full items-center justify-center gap-2 rounded-xl bg-[#6F4EF6] px-5 py-3.5 text-sm font-semibold text-white shadow-[0_10px_28px_rgba(111,78,246,0.23)] transition hover:-translate-y-0.5 hover:bg-[#6242E8] focus-visible:ring-2 focus-visible:ring-[#6F4EF6] focus-visible:ring-offset-2 disabled:opacity-60 motion-reduce:transform-none"
          >
            <span>{t("createExperience.outlineAction")}</span>
            <ChevronRight className="rtl-flip !h-5 !w-5 min-[1800px]:!h-6 min-[1800px]:!w-6" />
          </Button>
        </aside>
      </div>
    </div>
  );
};

export default UploadPage;
