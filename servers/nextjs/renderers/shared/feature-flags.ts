export type RendererFeatureFlags = Readonly<{
  canonicalKonvaRenderer: boolean;
  canonicalBrowserRenderer: boolean;
  unifiedEditorCommands: boolean;
  legacyRendererFallback: boolean;
}>;

function enabled(value: string | undefined, fallback: boolean) {
  if (value === undefined || value === "") return fallback;
  return value.toLowerCase() === "true" || value === "1";
}

const RUNTIME_FLAG_ENV = {
  NEXT_PUBLIC_CANONICAL_KONVA_RENDERER_ENABLED: process.env.NEXT_PUBLIC_CANONICAL_KONVA_RENDERER_ENABLED,
  CANONICAL_KONVA_RENDERER_ENABLED: process.env.CANONICAL_KONVA_RENDERER_ENABLED,
  NEXT_PUBLIC_CANONICAL_BROWSER_RENDERER_ENABLED: process.env.NEXT_PUBLIC_CANONICAL_BROWSER_RENDERER_ENABLED,
  CANONICAL_BROWSER_RENDERER_ENABLED: process.env.CANONICAL_BROWSER_RENDERER_ENABLED,
  NEXT_PUBLIC_UNIFIED_EDITOR_COMMANDS_ENABLED: process.env.NEXT_PUBLIC_UNIFIED_EDITOR_COMMANDS_ENABLED,
  UNIFIED_EDITOR_COMMANDS_ENABLED: process.env.UNIFIED_EDITOR_COMMANDS_ENABLED,
  NEXT_PUBLIC_LEGACY_RENDERER_FALLBACK_ENABLED: process.env.NEXT_PUBLIC_LEGACY_RENDERER_FALLBACK_ENABLED,
  LEGACY_RENDERER_FALLBACK_ENABLED: process.env.LEGACY_RENDERER_FALLBACK_ENABLED,
} satisfies Record<string, string | undefined>;

export function rendererFeatureFlags(
  env: Record<string, string | undefined> = RUNTIME_FLAG_ENV,
): RendererFeatureFlags {
  return Object.freeze({
    canonicalKonvaRenderer: enabled(
      env.NEXT_PUBLIC_CANONICAL_KONVA_RENDERER_ENABLED ?? env.CANONICAL_KONVA_RENDERER_ENABLED,
      false,
    ),
    canonicalBrowserRenderer: enabled(
      env.NEXT_PUBLIC_CANONICAL_BROWSER_RENDERER_ENABLED ?? env.CANONICAL_BROWSER_RENDERER_ENABLED,
      false,
    ),
    unifiedEditorCommands: enabled(
      env.NEXT_PUBLIC_UNIFIED_EDITOR_COMMANDS_ENABLED ?? env.UNIFIED_EDITOR_COMMANDS_ENABLED,
      false,
    ),
    legacyRendererFallback: enabled(
      env.NEXT_PUBLIC_LEGACY_RENDERER_FALLBACK_ENABLED ?? env.LEGACY_RENDERER_FALLBACK_ENABLED,
      true,
    ),
  });
}
