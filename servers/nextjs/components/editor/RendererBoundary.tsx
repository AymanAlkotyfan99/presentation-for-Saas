import type { ReactNode } from "react";
import type { PresentationDocument } from "@/generated/presentation-document";
import { rendererFeatureFlags } from "@/renderers/shared/feature-flags";
import { CanonicalEditor, type CanonicalPersistenceConfig } from "./CanonicalEditor";

export function CanonicalEditorBoundary({
  document,
  onDocumentChange,
  assetUrls,
  legacyFallback,
  persistence,
}: {
  document: PresentationDocument;
  onDocumentChange?: (document: PresentationDocument) => void;
  assetUrls?: Readonly<Record<string, string | undefined>>;
  legacyFallback?: ReactNode;
  persistence?: CanonicalPersistenceConfig;
}) {
  const flags = rendererFeatureFlags();
  if (flags.canonicalKonvaRenderer && flags.unifiedEditorCommands) {
    return <CanonicalEditor document={document} onDocumentChange={onDocumentChange} assetUrls={assetUrls} persistence={persistence} />;
  }
  if (flags.legacyRendererFallback && legacyFallback) return legacyFallback;
  return <div role="status">Canonical editor rollout is disabled.</div>;
}
