import type { Asset, PresentationDocument } from "@/generated/presentation-document";

export type AssetAuthorizationContext = Readonly<{
  presentationId: string;
  sessionScope?: string;
}>;

export type AssetResolution =
  | { status: "loading"; assetId: string }
  | { status: "ready"; assetId: string; url: string; expiresAt?: number }
  | { status: "fallback"; assetId: string; reason: "missing" | "unauthorized" | "expired" | "unsafe-url" | "unsupported" | "failed" };

export type ScopedAssetUrlProvider = (
  asset: Asset,
  context: AssetAuthorizationContext,
  signal?: AbortSignal,
) => Promise<{ url: string; expiresAt?: number }>;

const FORBIDDEN_PROTOCOL = /^(?:file|javascript|data):/i;

export function isSafeScopedAssetUrl(url: string): boolean {
  if (FORBIDDEN_PROTOCOL.test(url.trim())) return false;
  try {
    const parsed = new URL(url, "http://bayanly.invalid");
    if (parsed.origin === "http://bayanly.invalid") return url.startsWith("/") && !url.startsWith("//");
    if (parsed.protocol === "blob:") return true;
    return parsed.protocol === "https:" && !parsed.username && !parsed.password;
  } catch {
    return false;
  }
}

export class CanonicalAssetResolver {
  private readonly cache = new Map<string, AssetResolution>();

  constructor(
    private readonly provider: ScopedAssetUrlProvider,
    private readonly now: () => number = Date.now,
  ) {}

  peek(assetId: string, context: AssetAuthorizationContext): AssetResolution | undefined {
    const key = cacheKey(assetId, context);
    const cached = this.cache.get(key);
    if (cached?.status === "ready" && cached.expiresAt && cached.expiresAt <= this.now()) {
      this.cache.delete(key);
      return { status: "fallback", assetId, reason: "expired" };
    }
    return cached;
  }

  async resolve(
    document: PresentationDocument,
    assetId: string,
    context: AssetAuthorizationContext,
    signal?: AbortSignal,
  ): Promise<AssetResolution> {
    if (context.presentationId !== document.presentationId) {
      return { status: "fallback", assetId, reason: "unauthorized" };
    }
    const key = cacheKey(assetId, context);
    const cached = this.peek(assetId, context);
    if (cached?.status === "ready") return cached;
    const asset = document.assets.find((candidate) => candidate.assetId === assetId);
    if (!asset) return { status: "fallback", assetId, reason: "missing" };
    this.cache.set(key, { status: "loading", assetId });
    try {
      const resolved = await this.provider(asset, context, signal);
      if (!isSafeScopedAssetUrl(resolved.url)) {
        const fallback = { status: "fallback", assetId, reason: "unsafe-url" } as const;
        this.cache.set(key, fallback);
        return fallback;
      }
      if (resolved.expiresAt && resolved.expiresAt <= this.now()) {
        const fallback = { status: "fallback", assetId, reason: "expired" } as const;
        this.cache.set(key, fallback);
        return fallback;
      }
      const ready = { status: "ready", assetId, ...resolved } as const;
      this.cache.set(key, ready);
      return ready;
    } catch {
      const fallback = { status: "fallback", assetId, reason: "failed" } as const;
      this.cache.set(key, fallback);
      return fallback;
    }
  }

  invalidate(assetId?: string, context?: AssetAuthorizationContext) {
    for (const [key, cached] of this.cache) {
      if (assetId && cached.assetId !== assetId) continue;
      if (context && key !== cacheKey(cached.assetId, context)) continue;
      if (cached.status === "ready") revokeObjectAssetUrl(cached.url);
      this.cache.delete(key);
    }
  }
}

function cacheKey(assetId: string, context: AssetAuthorizationContext) {
  return `${context.presentationId}\u0000${context.sessionScope ?? ""}\u0000${assetId}`;
}

export function revokeObjectAssetUrl(url: string) {
  if (url.startsWith("blob:") && typeof URL.revokeObjectURL === "function") URL.revokeObjectURL(url);
}
