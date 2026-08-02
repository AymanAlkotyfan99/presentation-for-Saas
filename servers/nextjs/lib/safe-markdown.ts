import { Marked, Renderer } from "marked";

type HtmlToken = Parameters<Renderer["html"]>[0];
type LinkToken = Parameters<Renderer["link"]>[0];
type ImageToken = Parameters<Renderer["image"]>[0];
type CodeToken = Parameters<Renderer["code"]>[0];
type RendererContext = Renderer;

const SAFE_LINK_PROTOCOLS = new Set(["http:", "https:", "mailto:", "tel:"]);
const safeMarked = new Marked();

export type SafeMarkdownOptions = {
  breaks?: boolean;
};

export function escapeMarkdownHtml(value: string): string {
  return value
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#39;");
}

/**
 * Returns a URL only when Markdown may safely place it in href/src.
 *
 * Raw HTML is never part of the Markdown policy. Links allow ordinary web,
 * email, phone, fragment, and relative URLs; images are intentionally limited
 * to HTTP(S) and application-relative paths. data:, blob:, file:, javascript:,
 * and their control/percent-encoded variants are rejected.
 */
export function sanitizeMarkdownUrl(
  value: string,
  kind: "link" | "image" = "link"
): string | null {
  const trimmed = String(value ?? "").trim();
  if (!trimmed || /[\u0000-\u001f\u007f]/.test(trimmed)) {
    return null;
  }

  let canonical = trimmed;
  for (let index = 0; index < 3; index += 1) {
    try {
      const decoded = decodeURIComponent(canonical);
      if (decoded === canonical) break;
      canonical = decoded;
    } catch {
      break;
    }
  }
  canonical = canonical
    .replace(/[\u0000-\u0020\u007f]+/g, "")
    .replaceAll("\\", "/")
    .toLowerCase();

  const protocol = canonical.match(/^[a-z][a-z0-9+.-]*:/)?.[0] ?? null;
  if (protocol) {
    if (!SAFE_LINK_PROTOCOLS.has(protocol)) return null;
    if (kind === "image" && protocol !== "http:" && protocol !== "https:") {
      return null;
    }
  }

  // Scheme-relative resources are permitted only for links. Images must have
  // an explicit HTTPS/HTTP origin or an application-relative path.
  if (canonical.startsWith("//") && kind === "image") {
    return null;
  }

  return trimmed;
}

function safeTitle(title: string | null | undefined): string {
  return title ? ` title="${escapeMarkdownHtml(title)}"` : "";
}

function createSafeRenderer() {
  // Marked expects a complete Renderer instance when supplied per parse. The
  // assigned methods below override only the security-sensitive boundaries.
  return Object.assign(new Renderer(), {
    html({ text }: HtmlToken): string {
      // Raw Markdown HTML is displayed as text, never interpreted.
      return escapeMarkdownHtml(text);
    },
    link(
      this: RendererContext,
      { href, title, tokens }: LinkToken
    ): string {
      const label = this.parser.parseInline(tokens);
      const safeHref = sanitizeMarkdownUrl(href, "link");
      if (!safeHref) return label;
      return `<a href="${escapeMarkdownHtml(safeHref)}"${safeTitle(
        title
      )} rel="nofollow noopener noreferrer">${label}</a>`;
    },
    image({ href, title, text }: ImageToken): string {
      const safeSrc = sanitizeMarkdownUrl(href, "image");
      const alt = escapeMarkdownHtml(text || "");
      if (!safeSrc) return alt;
      return `<img src="${escapeMarkdownHtml(safeSrc)}" alt="${alt}"${safeTitle(
        title
      )}>`;
    },
    code({ text, lang }: CodeToken): string {
      const language = (lang ?? "")
        .trim()
        .split(/\s+/, 1)[0]
        .replace(/[^a-z0-9_-]/gi, "");
      const languageClass = language
        ? ` class="language-${escapeMarkdownHtml(language)}"`
        : "";
      return `<pre><code${languageClass}>${escapeMarkdownHtml(text)}</code></pre>\n`;
    },
  });
}

function parseSafeMarkdown(
  content: string,
  inline: boolean,
  options: SafeMarkdownOptions
): string {
  const value = typeof content === "string" ? content : "";
  try {
    const markedOptions = {
      async: false,
      breaks: options.breaks ?? false,
      gfm: true,
      renderer: createSafeRenderer(),
    };
    const parsed = inline
      ? safeMarked.parseInline(value, markedOptions as never)
      : safeMarked.parse(value, markedOptions as never);
    return typeof parsed === "string" ? parsed : escapeMarkdownHtml(value);
  } catch {
    return escapeMarkdownHtml(value);
  }
}

/** Render block Markdown under the single application-wide safe policy. */
export function renderSafeMarkdown(
  content: string,
  options: SafeMarkdownOptions = {}
): string {
  return parseSafeMarkdown(content, false, options);
}

/** Render inline Markdown under the same policy, without paragraph wrappers. */
export function renderSafeInlineMarkdown(content: string): string {
  return parseSafeMarkdown(content, true, {});
}
