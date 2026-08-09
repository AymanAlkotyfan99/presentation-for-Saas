"use client";

import * as DialogPrimitive from "@radix-ui/react-dialog";
import Image from "next/image";
import {
  ArrowUp,
  ChevronRight,
  Grid2X2,
  ImagePlus,
  Loader2,
  Minus,
  Plus,
  Search,
  Trash2,
  Upload,
  X,
} from "lucide-react";
import {
  useEffect,
  useMemo,
  useRef,
  useState,
  type ChangeEvent,
  type DragEvent,
} from "react";
import { useSelector } from "react-redux";
import { ImagesApi } from "@/app/(presentation-generator)/services/api/images";
import type { ImageAssetResponse } from "@/app/(presentation-generator)/services/api/types";
import { notify } from "@/components/ui/sonner";
import { cn } from "@/lib/utils";
import type { RootState } from "@/store/store";
import { resolveBackendAssetSource } from "@/utils/api";
import { IMAGE_PROVIDERS } from "@/utils/providerConstants";
import { useI18n } from "@/i18n/catalog";
import { formatNumber } from "@/lib/locale-format";

type PickerView = "discover" | "uploads";
type PickerImageSource = "generated" | "uploaded";
type PickerImage = {
  deletable?: boolean;
  id?: string;
  prompt?: string;
  source?: PickerImageSource;
  url: string;
};

const STOCK_IMAGE_PROVIDERS = new Set(["pexels", "pixabay"]);
const MAX_FILE_SIZE = 5 * 1024 * 1024;

function assetToPickerImage(
  asset: ImageAssetResponse,
  source: PickerImageSource,
): PickerImage | null {
  const url = resolveBackendAssetSource(asset);
  if (!url) return null;
  return {
    deletable: source === "uploaded",
    id: asset.id,
    prompt: asset.extras?.prompt,
    source,
    url,
  };
}

function dedupePickerImages(images: PickerImage[]) {
  const seen = new Set<string>();
  return images.filter((image) => {
    if (!image.url || seen.has(image.url)) return false;
    seen.add(image.url);
    return true;
  });
}

function normalizedProvider(value: string | null | undefined) {
  const provider = (value || "").trim().toLowerCase();
  if (provider === "pixels" || provider === "pixel" || provider === "pexel") {
    return "pexels";
  }
  return provider;
}

export function ImagePickerModal({
  currentImage,
  initialPrompt,
  open,
  onClose,
  onSelect,
}: {
  currentImage?: string | null;
  initialPrompt?: string | null;
  open: boolean;
  onClose: () => void;
  onSelect: (url: string, prompt?: string) => void;
}) {
  const { locale, t } = useI18n();
  const llmConfig = useSelector((state: RootState) => state.userConfig.llm_config);
  const provider = normalizedProvider(llmConfig?.IMAGE_PROVIDER);
  const stockProvider = STOCK_IMAGE_PROVIDERS.has(provider) ? provider : null;
  const providerLabel =
    IMAGE_PROVIDERS[provider]?.label ?? t("editor.aiImageProvider");
  const generationDisabled = Boolean(llmConfig?.DISABLE_IMAGE_GENERATION);
  const fileInputRef = useRef<HTMLInputElement | null>(null);
  const [view, setView] = useState<PickerView>("discover");
  const [query, setQuery] = useState(initialPrompt || "");
  const [variationCount, setVariationCount] = useState(4);
  const [discoverImages, setDiscoverImages] = useState<PickerImage[]>([]);
  const [uploadedImages, setUploadedImages] = useState<PickerImage[]>([]);
  const [isLoadingLibrary, setIsLoadingLibrary] = useState(false);
  const [isWorking, setIsWorking] = useState(false);
  const [isUploading, setIsUploading] = useState(false);
  const [isDragging, setIsDragging] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const currentSource = resolveBackendAssetSource(currentImage || "");
  const apiKey = useMemo(() => {
    if (stockProvider === "pexels") return llmConfig?.PEXELS_API_KEY;
    if (stockProvider === "pixabay") return llmConfig?.PIXABAY_API_KEY;
    return undefined;
  }, [llmConfig?.PEXELS_API_KEY, llmConfig?.PIXABAY_API_KEY, stockProvider]);

  useEffect(() => {
    if (!open) return;
    setView("discover");
    setQuery(initialPrompt || "");
    setDiscoverImages([]);
    setUploadedImages([]);
    setIsLoadingLibrary(false);
    setError(null);
    setIsDragging(false);
  }, [initialPrompt, open, provider]);

  useEffect(() => {
    if (!open || view !== "discover" || stockProvider) return;

    let cancelled = false;
    setIsLoadingLibrary(true);
    setError(null);
    ImagesApi.getGeneratedImages()
      .then((assets) => {
        if (cancelled) return;
        setDiscoverImages(
          dedupePickerImages(
            assets
              .map((asset) => assetToPickerImage(asset, "generated"))
              .filter((image): image is PickerImage => image !== null),
          ),
        );
      })
      .catch(() => {
        if (!cancelled) {
          setError(t("editor.loadGeneratedImagesFailed"));
        }
      })
      .finally(() => {
        if (!cancelled) setIsLoadingLibrary(false);
      });

    return () => {
      cancelled = true;
    };
  }, [open, stockProvider, t, view]);

  useEffect(() => {
    if (!open || view !== "discover" || !stockProvider) return;

    let cancelled = false;
    const starterQuery = (initialPrompt || "").trim() || "inspiration";
    setIsLoadingLibrary(true);
    setError(null);
    ImagesApi.searchStockImages(starterQuery, 24, {
      provider: stockProvider,
      apiKey,
    })
      .then((urls) => {
        if (cancelled) return;
        setDiscoverImages(
          urls.map((url) => ({ prompt: starterQuery, url })),
        );
        if (!urls.length) {
          setError(t("editor.noStarterImages"));
        }
      })
      .catch(() => {
        if (!cancelled) {
          setError(t("editor.loadStockImagesFailed"));
        }
      })
      .finally(() => {
        if (!cancelled) setIsLoadingLibrary(false);
      });

    return () => {
      cancelled = true;
    };
  }, [apiKey, initialPrompt, open, stockProvider, t, view]);

  useEffect(() => {
    if (!open || view !== "uploads" || isUploading) return;

    let cancelled = false;
    setIsLoadingLibrary(true);
    setError(null);
    ImagesApi.getUploadedImages()
      .then((assets) => {
        if (cancelled) return;
        setUploadedImages(
          dedupePickerImages(
            assets
              .map((asset) => assetToPickerImage(asset, "uploaded"))
              .filter((image): image is PickerImage => image !== null),
          ),
        );
      })
      .catch(() => {
        if (!cancelled) {
          setError(t("editor.loadUploadedImagesFailed"));
        }
      })
      .finally(() => {
        if (!cancelled) setIsLoadingLibrary(false);
      });

    return () => {
      cancelled = true;
    };
  }, [isUploading, open, t, view]);

  const chooseImage = (image: PickerImage) => {
    const prompt = image.prompt || (view === "discover" ? query.trim() : undefined);
    onSelect(image.url, prompt || undefined);
    onClose();
  };

  const searchStockImages = async () => {
    if (!stockProvider || !query.trim()) return;
    setIsWorking(true);
    setError(null);
    try {
      const urls = await ImagesApi.searchStockImages(query.trim(), 24, {
        provider: stockProvider,
        apiKey,
      });
      setDiscoverImages(
        urls.map((url) => ({ prompt: query.trim(), url })),
      );
      if (!urls.length) setError(t("editor.noImagesFound"));
    } catch {
      setDiscoverImages([]);
      setError(t("editor.stockSearchFailed"));
    } finally {
      setIsWorking(false);
    }
  };

  const generateImages = async () => {
    if (!query.trim() || generationDisabled) return;
    setIsWorking(true);
    setError(null);
    try {
      const responses = await Promise.allSettled(
        Array.from({ length: variationCount }, () =>
          ImagesApi.generateImage(query.trim()),
        ),
      );
      const images: PickerImage[] = responses.flatMap((response) => {
        if (response.status !== "fulfilled") return [];
        const url = resolveBackendAssetSource(response.value);
        return url
          ? [{ prompt: query.trim(), source: "generated" as const, url }]
          : [];
      });
      if (!images.length) {
        const failure = responses.find(
          (response): response is PromiseRejectedResult =>
            response.status === "rejected",
        );
        throw failure?.reason ?? new Error("IMAGE_GENERATION_EMPTY");
      }
      setDiscoverImages((previous) =>
        dedupePickerImages([...images, ...previous]),
      );
      if (images.length < variationCount) {
        notify.warning(
          t("editor.someVariantsFailed"),
          t("editor.generatedVariants", {
            created: formatNumber(images.length, locale),
            requested: formatNumber(variationCount, locale),
          }),
        );
      }
    } catch {
      const message = t("editor.imageGenerationNoResults");
      setError(message);
      notify.error(t("editor.imageGenerationFailed"), message);
    } finally {
      setIsWorking(false);
    }
  };

  const runDiscover = () => {
    if (!query.trim() || (generationDisabled && !stockProvider)) return;
    if (stockProvider) void searchStockImages();
    else void generateImages();
  };

  const uploadFile = async (file: File | undefined) => {
    if (!file) return;
    if (!file.type.startsWith("image/")) {
      setError(t("editor.validImageRequired"));
      return;
    }
    if (file.size > MAX_FILE_SIZE) {
      setError(t("editor.imageTooLarge", { size: "5 MB" }));
      return;
    }

    setView("uploads");
    setIsUploading(true);
    setError(null);
    try {
      const asset = await ImagesApi.uploadImage(file);
      const image = assetToPickerImage(asset, "uploaded");
      if (!image) throw new Error("UPLOAD_IMAGE_URL_MISSING");
      setUploadedImages((previous) => [
        image,
        ...previous.filter((item) => item.id !== image.id),
      ]);
      notify.success(
        t("editor.imageUploaded"),
        t("editor.selectFromLibrary"),
      );
    } catch {
      const message = t("editor.uploadMissingUrl");
      setError(message);
      notify.error(t("editor.uploadFailed"), message);
    } finally {
      setIsUploading(false);
      if (fileInputRef.current) fileInputRef.current.value = "";
    }
  };

  const handleFileInput = (event: ChangeEvent<HTMLInputElement>) => {
    void uploadFile(event.target.files?.[0]);
  };

  const handleDrop = (event: DragEvent<HTMLDivElement>) => {
    event.preventDefault();
    setIsDragging(false);
    void uploadFile(event.dataTransfer.files?.[0]);
  };

  const deleteUploadedImage = async (image: PickerImage) => {
    if (!image.deletable || !image.id) return;
    try {
      await ImagesApi.deleteImage(image.id);
      setUploadedImages((previous) =>
        previous.filter((candidate) => candidate.id !== image.id),
      );
      notify.success(
        t("editor.imageDeleted"),
        t("editor.imageDeletedDescription"),
      );
    } catch {
      notify.error(
        t("editor.imageDeleteFailed"),
        t("errors.generic"),
      );
    }
  };

  return (
    <DialogPrimitive.Root
      open={open}
      onOpenChange={(nextOpen) => {
        if (!nextOpen) onClose();
      }}
    >
      <DialogPrimitive.Portal>
        <DialogPrimitive.Overlay className="fixed inset-0 z-[10050] bg-black/80 data-[state=open]:animate-in data-[state=closed]:animate-out data-[state=closed]:fade-out-0 data-[state=open]:fade-in-0" />
        <DialogPrimitive.Content
          data-template-v2-floating-toolbar="true"
          data-inline-edit-ignore="true"
          className="fixed left-1/2 top-1/2 z-[10051] h-[calc(100dvh-24px)] w-[calc(100vw-24px)] -translate-x-1/2 -translate-y-1/2 font-syne text-[#191919] outline-none sm:h-[min(70vh,650px)] sm:min-h-[500px] sm:w-[min(calc(100vw-160px),977px)]"
          onPointerDown={(event) => event.stopPropagation()}
        >
          <div className="flex h-full min-h-0 flex-col overflow-hidden rounded-[20px] bg-[#F9FAFB] shadow-[0_28px_80px_rgba(0,0,0,0.34)]">
            <header className="flex h-[85px] flex-none items-center justify-between border-b border-[#EDEEEF] bg-white px-6 shadow-[0_4px_7px_rgba(0,0,0,0.04)]">
              <div>
                <DialogPrimitive.Title className="text-[18px] font-normal leading-normal">
                  {t("editor.changeImage")}
                </DialogPrimitive.Title>
                <DialogPrimitive.Description className="mt-0.5 text-[14px] font-normal tracking-[-0.42px] text-[#808080]">
                  {t("editor.changeImageDescription")}
                </DialogPrimitive.Description>
              </div>
              <button
                type="button"
                aria-label={t("editor.uploadImage")}
                title={t("editor.uploadImage")}
                onClick={() => fileInputRef.current?.click()}
                disabled={isUploading}
                className="flex h-9 w-[100px] items-center justify-center rounded-full border border-[#EDEEEF] bg-white transition hover:bg-[#F9FAFB] disabled:cursor-wait"
              >
                {isUploading ? (
                  <Loader2 className="me-1.5 size-4 animate-spin" aria-hidden="true" />
                ) : (
                  <Upload className="me-1.5 size-4" strokeWidth={1.8} aria-hidden="true" />
                )}
                {t("editor.uploadImage")}
              </button>
              <input
                ref={fileInputRef}
                className="sr-only"
                type="file"
                accept="image/*"
                onChange={handleFileInput}
              />
            </header>

            <div className="flex min-h-0 flex-1 flex-col sm:flex-row">
              <nav className="flex flex-none gap-1 border-b border-[#EDEEEF] bg-white p-3 sm:w-[270px] sm:flex-col sm:border-b-0 sm:border-e sm:p-5">
                <PickerNavButton
                  active={view === "discover"}
                  icon={<ImagePlus className="size-4" strokeWidth={1.7} />}
                  label={t("editor.discoverImage")}
                  onClick={() => {
                    setView("discover");
                    setIsLoadingLibrary(false);
                    setError(null);
                  }}
                />
                <PickerNavButton
                  active={view === "uploads"}
                  icon={<Grid2X2 className="size-4" strokeWidth={1.7} />}
                  label={t("editor.useYourImage")}
                  onClick={() => {
                    setView("uploads");
                    setError(null);
                  }}
                />
              </nav>

              <div
                className="relative flex min-h-0 min-w-0 flex-1 flex-col bg-white px-4 py-4 sm:pe-5"
                onDragEnter={(event) => {
                  event.preventDefault();
                  setIsDragging(true);
                }}
                onDragOver={(event) => event.preventDefault()}
                onDragLeave={(event) => {
                  if (!event.currentTarget.contains(event.relatedTarget as Node)) {
                    setIsDragging(false);
                  }
                }}
                onDrop={handleDrop}
              >
                {view === "discover" ? (
                  <DiscoverControls
                    disabled={generationDisabled && !stockProvider}
                    isStock={Boolean(stockProvider)}
                    isWorking={isWorking || isLoadingLibrary}
                    providerLabel={providerLabel}
                    query={query}
                    variationCount={variationCount}
                    onQueryChange={setQuery}
                    onRun={runDiscover}
                    onVariationChange={(delta) =>
                      setVariationCount((count) =>
                        Math.max(1, Math.min(4, count + delta)),
                      )
                    }
                  />
                ) : null}

                {error ? (
                  <div className="mt-3 rounded-[10px] border border-red-200 bg-red-50 px-3 py-2 text-[12px] text-red-700">
                    {error}
                  </div>
                ) : null}

                <div className="mt-3 min-h-0 flex-1 overflow-y-auto pr-1 [scrollbar-width:thin]">
                  {isLoadingLibrary || isWorking ? (
                    <ImageSkeletons compact={Boolean(stockProvider)} />
                  ) : view === "discover" ? (
                    <ImageResults
                      compact={Boolean(stockProvider)}
                      currentSource={currentSource}
                      images={discoverImages}
                      emptyMessage={
                        generationDisabled && !stockProvider
                          ? t("editor.generationDisabled")
                          : stockProvider
                            ? t("editor.searchProviderPrompt", {
                                provider: providerLabel,
                              })
                            : t("editor.generateImagesHint")
                      }
                      onSelect={chooseImage}
                    />
                  ) : (
                    <ImageResults
                      compact
                      currentSource={currentSource}
                      images={uploadedImages}
                      emptyMessage={t("editor.uploadLibraryHint")}
                      onDelete={deleteUploadedImage}
                      onSelect={chooseImage}
                    />
                  )}
                </div>

                {isDragging ? (
                  <div className="pointer-events-none absolute inset-4 z-20 flex items-center justify-center rounded-[16px] border-2 border-dashed border-[#191919] bg-white/95 text-center">
                    <div>
                      <Upload className="mx-auto mb-2 size-6" aria-hidden="true" />
                      <p className="text-[14px] font-medium">
                        {t("editor.dropImage")}
                      </p>
                      <p className="mt-1 text-[12px] text-[#808080]">
                        {t("editor.maximumFileSize", { size: "5 MB" })}
                      </p>
                    </div>
                  </div>
                ) : null}
              </div>
            </div>
          </div>

          <DialogPrimitive.Close
            aria-label={t("editor.closeImagePicker")}
            className="absolute end-3 top-3 flex size-11 items-center justify-center rounded-full bg-white text-[#191919] shadow-sm transition hover:bg-[#F6F6F9] sm:-end-[68px] sm:top-0 sm:size-[52px]"
          >
            <X className="size-5" strokeWidth={1.5} aria-hidden="true" />
          </DialogPrimitive.Close>
        </DialogPrimitive.Content>
      </DialogPrimitive.Portal>
    </DialogPrimitive.Root>
  );
}

function PickerNavButton({
  active,
  icon,
  label,
  onClick,
}: {
  active: boolean;
  icon: React.ReactNode;
  label: string;
  onClick: () => void;
}) {
  return (
    <button
      type="button"
      aria-pressed={active}
      onClick={onClick}
      className={cn(
        "flex min-w-0 flex-1 items-center gap-2.5 rounded-[12px] px-2.5 py-3 text-start text-[14px] font-normal outline-none transition hover:bg-[#F4F4F4] focus-visible:ring-2 focus-visible:ring-[#E1E1E5] sm:w-full sm:flex-none",
        active && "bg-[#F4F4F4]",
      )}
    >
      <span className="flex-none" aria-hidden="true">{icon}</span>
      <span className="truncate">{label}</span>
      <ChevronRight className="ms-auto size-3.5 flex-none rtl:rotate-180" strokeWidth={1.8} aria-hidden="true" />
    </button>
  );
}

function DiscoverControls({
  disabled,
  isStock,
  isWorking,
  providerLabel,
  query,
  variationCount,
  onQueryChange,
  onRun,
  onVariationChange,
}: {
  disabled: boolean;
  isStock: boolean;
  isWorking: boolean;
  providerLabel: string;
  query: string;
  variationCount: number;
  onQueryChange: (value: string) => void;
  onRun: () => void;
  onVariationChange: (delta: number) => void;
}) {
  const { locale, t } = useI18n();
  const canRun = query.trim().length > 0 && !isWorking && !disabled;

  if (isStock) {
    return (
      <div
        className="flex h-[41px] flex-none gap-2.5"
        aria-label={t("editor.searchProvider", { provider: providerLabel })}
      >
        <label className="flex min-w-0 flex-1 items-center gap-2.5 rounded-[8px] border border-[rgba(219,219,219,0.6)] bg-white px-2.5">
          <Search className="size-3.5 flex-none" strokeWidth={1.8} aria-hidden="true" />
          <textarea
            autoFocus
            value={query}
            onChange={(event) => onQueryChange(event.target.value)}
            onKeyDown={(event) => {
              if (event.key === "Enter" && canRun) onRun();
            }}
            placeholder={t("editor.searchImage")}
            className="h-full min-w-0 flex-1 bg-transparent text-[14px] font-normal outline-none placeholder:text-[#999]"
          />
        </label>
        <button
          type="button"
          aria-label={t("editor.searchProvider", { provider: providerLabel })}
          onClick={onRun}
          disabled={!canRun}
          className="flex w-[132px] items-center justify-center rounded-[38.4px] bg-[#EDEEEF] px-[12.8px] py-2 text-[#191919] transition hover:bg-[#E1E1E5] disabled:cursor-not-allowed disabled:text-[#999]"
        >
          {isWorking ? <Loader2 className="size-4 animate-spin" /> : <ArrowUp className="size-4" />}
        </button>
      </div>
    );
  }

  return (
    <div
      className="flex h-[76px] flex-none gap-2.5"
      aria-label={t("editor.generateWith", { provider: providerLabel })}
    >
      <textarea
        autoFocus
        value={query}
        onChange={(event) => onQueryChange(event.target.value)}
        onKeyDown={(event) => {
          if ((event.metaKey || event.ctrlKey) && event.key === "Enter" && canRun) {
            onRun();
          }
        }}
        placeholder={t("editor.describeImage")}
        className="min-w-0 flex-1 resize-none rounded-[8px] border border-[rgba(219,219,219,0.6)] bg-white px-2.5 py-3 text-[14px] font-normal outline-none shadow-[0_4px_7px_rgba(0,0,0,0.04)] placeholder:text-[#999] focus:border-[#B9BBC1]"
      />
      <div className="flex w-[150px] flex-none flex-col gap-2.5">
        <div className="flex h-[34px] items-center rounded-full border border-[#EDEEEF] bg-white">
          <button
            type="button"
            aria-label={t("editor.fewerVariations")}
            disabled={variationCount <= 1 || isWorking}
            onClick={() => onVariationChange(-1)}
            className="flex h-full w-9 items-center justify-center rounded-s-full hover:bg-[#F9FAFB] disabled:opacity-35"
          >
            <Minus className="size-3.5" />
          </button>
          <span className="flex h-4 flex-1 items-center justify-center border-x border-[#EDEEEF] text-[12px] font-semibold">
            {variationCount === 1
              ? t("editor.oneVariation")
              : t("editor.variations", {
                  count: formatNumber(variationCount, locale),
                })}
          </span>
          <button
            type="button"
            aria-label={t("editor.moreVariations")}
            disabled={variationCount >= 4 || isWorking}
            onClick={() => onVariationChange(1)}
            className="flex h-full w-9 items-center justify-center rounded-e-full hover:bg-[#F9FAFB] disabled:opacity-35"
          >
            <Plus className="size-3.5" />
          </button>
        </div>
        <button
          type="button"
          aria-label={t("editor.generateVariations", {
            count: formatNumber(variationCount, locale),
            provider: providerLabel,
          })}
          onClick={onRun}
          disabled={!canRun}
          className="flex h-8 items-center justify-center rounded-[38.4px] bg-[#EDEEEF] px-[12.8px] py-2 text-[#191919] transition hover:bg-[#E1E1E5] disabled:cursor-not-allowed disabled:text-[#999]"
        >
          {isWorking ? <Loader2 className="size-4 animate-spin" /> : <ArrowUp className="size-4" />}
        </button>
      </div>
    </div>
  );
}

function ImageSkeletons({ compact = false }: { compact?: boolean }) {
  return (
    <div className={cn("grid grid-cols-2 gap-2.5", compact && "sm:grid-cols-3 lg:grid-cols-4")}>
      {Array.from({ length: compact ? 12 : 6 }, (_, index) => (
        <div
          key={index}
          className="aspect-square animate-pulse rounded-[10px] bg-[#F6F6F9]"
        />
      ))}
    </div>
  );
}

function ImageResults({
  compact = false,
  currentSource,
  emptyMessage,
  images,
  onDelete,
  onSelect,
}: {
  compact?: boolean;
  currentSource: string;
  emptyMessage: string;
  images: PickerImage[];
  onDelete?: (image: PickerImage) => void;
  onSelect: (image: PickerImage) => void;
}) {
  const t = useI18n().t;
  if (!images.length) {
    return (
      <div className="flex h-full min-h-[220px] items-center justify-center rounded-[14px] border border-dashed border-[#E1E1E5] bg-[#F9FAFB] px-6 text-center">
        <p className="max-w-[330px] text-[13px] leading-5 text-[#808080]">{emptyMessage}</p>
      </div>
    );
  }

  return (
    <div className={cn("grid grid-cols-2 gap-2.5", compact && "sm:grid-cols-3 lg:grid-cols-4")}>
      {images.map((image, index) => (
        <div
          key={`${image.id || image.url}-${index}`}
          className={cn(
            "group relative aspect-square overflow-hidden rounded-[10px] border border-[#EDEEEF] bg-[#F6F6F9] text-start outline-none ring-offset-2 focus-visible:ring-2 focus-visible:ring-[#191919]",
            image.url === currentSource && "ring-2 ring-[#191919]",
          )}
        >
          <button
            type="button"
            aria-label={t("editor.useImage")}
            onClick={() => onSelect(image)}
            className="absolute inset-0 h-full w-full overflow-hidden rounded-[10px] outline-none focus-visible:ring-2 focus-visible:ring-inset focus-visible:ring-[#191919]"
          >
            <Image
              fill
              unoptimized
              src={image.url}
              alt={image.prompt || ""}
              sizes={compact ? "(min-width: 1024px) 160px, 25vw" : "(min-width: 640px) 330px, 50vw"}
              className="object-cover transition duration-300 group-hover:scale-[1.025]"
            />
            <span className="absolute inset-0 flex items-end justify-center bg-gradient-to-t from-black/45 via-transparent to-transparent p-2 opacity-0 transition group-hover:opacity-100 group-focus-within:opacity-100">
              <span className="rounded-full bg-white/95 px-3 py-1 text-[11px] font-medium text-[#191919]">
                {t("editor.useImage")}
              </span>
            </span>
          </button>
          {onDelete && image.deletable && image.id ? (
            <button
              type="button"
              aria-label={t("editor.deleteUploadedImage")}
              onClick={(event) => {
                event.stopPropagation();
                onDelete(image);
              }}
              className="absolute end-2 top-2 flex size-7 items-center justify-center rounded-full bg-white/95 text-red-600 opacity-0 shadow-sm transition hover:bg-white group-hover:opacity-100 group-focus-within:opacity-100"
            >
              <Trash2 className="size-3.5" strokeWidth={1.8} />
            </button>
          ) : null}
        </div>
      ))}
    </div>
  );
}
