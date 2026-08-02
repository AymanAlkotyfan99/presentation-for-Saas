const GOOGLE_FONTS_STYLESHEET_HOST = "fonts.googleapis.com";
const GOOGLE_FONTS_STYLESHEET_PATHS = new Set(["/css", "/css2"]);
const FONT_FILE_PATTERN = /\.(?:eot|otf|ttf|woff2?)$/i;
const TRUSTED_BACKEND_ASSET_PREFIXES = ["/app_data/", "/static/"];
const MAX_FONT_FAMILY_LENGTH = 160;
const MAX_FONT_URL_LENGTH = 4096;
const MAX_FONT_RESOURCES = 128;

/**
 * @typedef {{ family: string, kind: "font" | "stylesheet", url: string }} SafeFontResource
 * @typedef {{ documentOrigin: string, trustedAssetOrigins?: Iterable<string>, preserveRelativeUrls?: boolean }} FontResourcePolicy
 */

/** @param {string} value */
function normalizeHttpOrigin(value) {
  try {
    const parsed = new URL(value);
    if (parsed.protocol !== "http:" && parsed.protocol !== "https:") {
      return null;
    }
    if (parsed.username || parsed.password) return null;
    return parsed.origin;
  } catch {
    return null;
  }
}

/** @param {unknown} value */
function normalizeFontFamily(value) {
  if (typeof value !== "string") return null;
  const family = value.trim().normalize("NFC");
  if (!family || family.length > MAX_FONT_FAMILY_LENGTH) return null;
  if (
    /[\u0000-\u001f\u007f-\u009f\u2028\u2029\u202a-\u202e\u2066-\u2069\ud800-\udfff]/u.test(
      family,
    )
  ) {
    return null;
  }
  return family;
}

/** @param {FontResourcePolicy} policy */
function trustedOrigins(policy) {
  const documentOrigin = normalizeHttpOrigin(policy.documentOrigin);
  if (!documentOrigin) return null;

  const origins = new Set([documentOrigin]);
  for (const candidate of policy.trustedAssetOrigins ?? []) {
    const origin = normalizeHttpOrigin(candidate);
    if (origin) origins.add(origin);
  }
  return { documentOrigin, origins };
}

/**
 * @param {unknown} familyValue
 * @param {unknown} urlValue
 * @param {FontResourcePolicy} policy
 * @returns {SafeFontResource | null}
 */
export function normalizeFontResource(familyValue, urlValue, policy) {
  const family = normalizeFontFamily(familyValue);
  if (!family || typeof urlValue !== "string") return null;

  const rawUrl = urlValue.trim();
  if (
    !rawUrl ||
    rawUrl.length > MAX_FONT_URL_LENGTH ||
    /[\u0000-\u0020\u007f-\u009f\u2028\u2029\u202a-\u202e\u2066-\u2069\ud800-\udfff\\]/u.test(
      rawUrl,
    ) ||
    rawUrl.startsWith("//")
  ) {
    return null;
  }

  const allowed = trustedOrigins(policy);
  if (!allowed) return null;

  const explicitScheme = /^[a-z][a-z0-9+.-]*:/i.exec(rawUrl)?.[0] ?? null;
  if (explicitScheme && !/^https?:\/\//i.test(rawUrl)) return null;

  let parsed;
  try {
    parsed = new URL(rawUrl, `${allowed.documentOrigin}/`);
  } catch {
    return null;
  }
  if (
    (parsed.protocol !== "http:" && parsed.protocol !== "https:") ||
    parsed.username ||
    parsed.password ||
    parsed.hash ||
    /%(?:2f|5c)/i.test(parsed.pathname)
  ) {
    return null;
  }

  const normalizedUrl =
    policy.preserveRelativeUrls && !explicitScheme
      ? `${parsed.pathname}${parsed.search}`
      : parsed.toString();

  if (parsed.hostname === GOOGLE_FONTS_STYLESHEET_HOST) {
    if (
      parsed.protocol !== "https:" ||
      parsed.port ||
      !GOOGLE_FONTS_STYLESHEET_PATHS.has(parsed.pathname)
    ) {
      return null;
    }
    return { family, kind: "stylesheet", url: normalizedUrl };
  }

  if (!allowed.origins.has(parsed.origin)) return null;

  const isDocumentOrigin = parsed.origin === allowed.documentOrigin;
  if (!FONT_FILE_PATTERN.test(parsed.pathname)) return null;
  if (
    !isDocumentOrigin &&
    !TRUSTED_BACKEND_ASSET_PREFIXES.some((prefix) =>
      parsed.pathname.startsWith(prefix),
    )
  ) {
    return null;
  }
  return { family, kind: "font", url: normalizedUrl };
}

/**
 * @param {unknown} fonts
 * @param {FontResourcePolicy} policy
 * @returns {SafeFontResource[]}
 */
export function normalizeFontResources(fonts, policy) {
  if (!fonts || typeof fonts !== "object" || Array.isArray(fonts)) return [];

  let names;
  try {
    names = Object.keys(fonts).slice(0, MAX_FONT_RESOURCES);
  } catch {
    return [];
  }

  /** @type {SafeFontResource[]} */
  const resources = [];
  const seen = new Set();
  for (const name of names) {
    let url;
    try {
      url = fonts[name];
    } catch {
      continue;
    }
    const resource = normalizeFontResource(name, url, policy);
    if (!resource) continue;
    const key = `${resource.kind}\u0000${resource.family}\u0000${resource.url}`;
    if (seen.has(key)) continue;
    seen.add(key);
    resources.push(resource);
  }
  return resources;
}

/** @param {string} character */
function cssHexEscape(character) {
  return `\\${character.codePointAt(0)?.toString(16).toUpperCase()} `;
}

/** @param {string} value */
export function escapeCssString(value) {
  let escaped = "";
  for (const character of value) {
    const codePoint = character.codePointAt(0) ?? 0;
    if (
      codePoint === 0 ||
      codePoint <= 0x1f ||
      (codePoint >= 0x7f && codePoint <= 0x9f) ||
      codePoint === 0x2028 ||
      codePoint === 0x2029 ||
      (codePoint >= 0xd800 && codePoint <= 0xdfff) ||
      character === '"' ||
      character === "'" ||
      character === "\\" ||
      character === "<" ||
      character === ">"
    ) {
      escaped += cssHexEscape(character);
    } else {
      escaped += character;
    }
  }
  return escaped;
}

/** @param {SafeFontResource} resource */
export function buildFontFaceCss(resource) {
  if (resource.kind !== "font") return null;
  return `@font-face {
  font-family: "${escapeCssString(resource.family)}";
  src: url("${escapeCssString(resource.url)}");
  font-style: normal;
  font-display: swap;
}`;
}

/** @param {Document} documentObject @param {string} url */
function hasStylesheet(documentObject, url) {
  return Array.from(
    documentObject.querySelectorAll('link[rel="stylesheet"]'),
  ).some(
    (link) =>
      link.href === url ||
      link.getAttribute("href") === url ||
      link.getAttribute("data-font-url") === url,
  );
}

/** @param {Document} documentObject @param {SafeFontResource} resource */
function hasFontFace(documentObject, resource) {
  return Array.from(
    documentObject.querySelectorAll("style[data-presenton-font-face]"),
  ).some(
    (style) =>
      style.getAttribute("data-font-url") === resource.url &&
      style.getAttribute("data-font-family") === resource.family,
  );
}

/**
 * @param {unknown} fonts
 * @param {FontResourcePolicy} policy
 * @param {Document} documentObject
 */
export function injectFontResources(fonts, policy, documentObject) {
  if (!documentObject?.head) return 0;
  let injected = 0;

  for (const resource of normalizeFontResources(fonts, policy)) {
    if (resource.kind === "stylesheet") {
      if (hasStylesheet(documentObject, resource.url)) continue;
      const link = documentObject.createElement("link");
      link.rel = "stylesheet";
      link.setAttribute("data-font-url", resource.url);
      link.href = resource.url;
      documentObject.head.appendChild(link);
      injected += 1;
      continue;
    }

    if (hasFontFace(documentObject, resource)) continue;
    const css = buildFontFaceCss(resource);
    if (!css) continue;
    const style = documentObject.createElement("style");
    style.setAttribute("data-presenton-font-face", "true");
    style.setAttribute("data-font-url", resource.url);
    style.setAttribute("data-font-family", resource.family);
    style.textContent = css;
    documentObject.head.appendChild(style);
    injected += 1;
  }
  return injected;
}
