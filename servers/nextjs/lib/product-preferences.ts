export const PRODUCT_PREFERENCES_STORAGE_KEY = "bayanly:product-preferences:v1";
export const ONBOARDING_STORAGE_KEY = "bayanly:onboarding-complete:v1";

export const DESIGN_STYLES = [
  "minimal",
  "modern",
  "academic",
  "business",
  "creative",
] as const;
export const COLOR_PALETTES = ["violet", "ocean", "forest", "sunset", "mono"] as const;
export const ASPECT_RATIOS = ["16:9", "4:3"] as const;
export const IMAGE_PREFERENCES = ["ai", "stock", "none"] as const;
export const MOTION_PREFERENCES = ["system", "reduced"] as const;

export type DesignStyle = (typeof DESIGN_STYLES)[number];
export type ColorPalette = (typeof COLOR_PALETTES)[number];
export type AspectRatio = (typeof ASPECT_RATIOS)[number];
export type ImagePreference = (typeof IMAGE_PREFERENCES)[number];
export type MotionPreference = (typeof MOTION_PREFERENCES)[number];

export type ProductPreferences = {
  presentationLanguage: string;
  slideCount: string;
  designStyle: DesignStyle;
  colorPalette: ColorPalette;
  aspectRatio: AspectRatio;
  imagePreference: ImagePreference;
  motion: MotionPreference;
};

export const DEFAULT_PRODUCT_PREFERENCES: ProductPreferences = {
  presentationLanguage: "Auto (English)",
  slideCount: "10",
  designStyle: "modern",
  colorPalette: "violet",
  aspectRatio: "16:9",
  imagePreference: "stock",
  motion: "system",
};

function oneOf<T extends readonly string[]>(
  value: unknown,
  allowed: T,
  fallback: T[number],
): T[number] {
  return typeof value === "string" && allowed.includes(value as T[number])
    ? (value as T[number])
    : fallback;
}

export function normalizeProductPreferences(value: unknown): ProductPreferences {
  const input = value && typeof value === "object"
    ? (value as Record<string, unknown>)
    : {};
  const slideCount = typeof input.slideCount === "string" && /^([1-9]|[1-4][0-9]|50)$/.test(input.slideCount)
    ? input.slideCount
    : DEFAULT_PRODUCT_PREFERENCES.slideCount;
  const presentationLanguage =
    typeof input.presentationLanguage === "string" && input.presentationLanguage.trim().length > 0
      ? input.presentationLanguage.trim().slice(0, 120)
      : DEFAULT_PRODUCT_PREFERENCES.presentationLanguage;

  return {
    presentationLanguage,
    slideCount,
    designStyle: oneOf(input.designStyle, DESIGN_STYLES, DEFAULT_PRODUCT_PREFERENCES.designStyle),
    colorPalette: oneOf(input.colorPalette, COLOR_PALETTES, DEFAULT_PRODUCT_PREFERENCES.colorPalette),
    aspectRatio: oneOf(input.aspectRatio, ASPECT_RATIOS, DEFAULT_PRODUCT_PREFERENCES.aspectRatio),
    imagePreference: oneOf(input.imagePreference, IMAGE_PREFERENCES, DEFAULT_PRODUCT_PREFERENCES.imagePreference),
    motion: oneOf(input.motion, MOTION_PREFERENCES, DEFAULT_PRODUCT_PREFERENCES.motion),
  };
}

export function loadProductPreferences(): ProductPreferences {
  if (typeof window === "undefined") return DEFAULT_PRODUCT_PREFERENCES;
  try {
    return normalizeProductPreferences(
      JSON.parse(window.localStorage.getItem(PRODUCT_PREFERENCES_STORAGE_KEY) || "null"),
    );
  } catch {
    return DEFAULT_PRODUCT_PREFERENCES;
  }
}

export function saveProductPreferences(preferences: ProductPreferences): ProductPreferences {
  const normalized = normalizeProductPreferences(preferences);
  if (typeof window !== "undefined") {
    window.localStorage.setItem(PRODUCT_PREFERENCES_STORAGE_KEY, JSON.stringify(normalized));
    document.documentElement.dataset.motion = normalized.motion;
  }
  return normalized;
}

export function productPreferenceInstructions(
  preferences: ProductPreferences,
  userInstructions = "",
): string {
  const visualDirection = preferences.imagePreference === "none"
    ? "Use typography, shapes, and charts instead of decorative imagery."
    : preferences.imagePreference === "stock"
      ? "Prefer natural editorial photography when visuals are useful."
      : "Prefer original illustrative visuals when visuals are useful.";
  const productDirection = [
    `Design direction: ${preferences.designStyle}.`,
    `Color direction: ${preferences.colorPalette}.`,
    `Canvas preference: ${preferences.aspectRatio}.`,
    visualDirection,
  ].join(" ");
  return [userInstructions.trim(), productDirection].filter(Boolean).join("\n\n");
}

