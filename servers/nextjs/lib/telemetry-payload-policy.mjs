const MAX_TELEMETRY_PROPERTIES = 64;
const MAX_CATEGORY_LENGTH = 64;
const MAX_ERROR_CLASSIFICATION_INPUT = 2048;

export const TELEMETRY_ERROR_CATEGORIES = Object.freeze([
  "authentication",
  "authorization",
  "cancelled",
  "client",
  "conflict",
  "network",
  "not_found",
  "payload_too_large",
  "rate_limited",
  "runtime",
  "server",
  "timeout",
  "unknown",
  "validation",
]);

const ERROR_CATEGORY_SET = new Set(TELEMETRY_ERROR_CATEGORIES);
const ERROR_INPUT_KEYS = new Set([
  "error",
  "error_detail",
  "error_message",
  "error_type",
  "exception",
  "validation_error",
]);
const ROUTE_KEYS = new Map([
  ["from", "from_route"],
  ["page_path", "route"],
  ["pathname", "route"],
  ["to", "to_route"],
  ["url", "route"],
]);
const ROUTE_CATEGORIES = new Set([
  "admin",
  "auth",
  "custom-template",
  "dashboard",
  "documents-preview",
  "external",
  "onboarding",
  "other",
  "outline",
  "pdf-maker",
  "presentation",
  "root",
  "settings",
  "template-preview",
  "templates",
  "theme",
  "upload",
]);
const SAFE_FILE_EXTENSIONS = new Map([
  ["bmp", "bmp"],
  ["csv", "csv"],
  ["doc", "doc"],
  ["docm", "doc"],
  ["docx", "docx"],
  ["eot", "eot"],
  ["gif", "gif"],
  ["jpeg", "jpeg"],
  ["jpg", "jpeg"],
  ["key", "keynote"],
  ["md", "text"],
  ["odp", "presentation"],
  ["ods", "spreadsheet"],
  ["odt", "document"],
  ["otf", "otf"],
  ["pdf", "pdf"],
  ["png", "png"],
  ["ppt", "ppt"],
  ["pptm", "ppt"],
  ["pptx", "pptx"],
  ["rtf", "document"],
  ["svg", "svg"],
  ["tif", "tiff"],
  ["tiff", "tiff"],
  ["tsv", "spreadsheet"],
  ["ttf", "ttf"],
  ["txt", "text"],
  ["webp", "webp"],
  ["woff", "woff"],
  ["woff2", "woff2"],
  ["xls", "xls"],
  ["xlsm", "xls"],
  ["xlsx", "xlsx"],
]);
const FILE_SIZE_BUCKETS = new Set([
  "0",
  "<100KB",
  "100KB-1MB",
  "1MB-5MB",
  "5MB-20MB",
  "20MB-100MB",
  "100MB+",
  "unknown",
]);
const MESSAGE_LENGTH_BUCKETS = new Set([
  "0",
  "<50",
  "50-199",
  "200-499",
  "500-999",
  "1000-1999",
  "2000+",
]);
const SAFE_CATEGORY_KEYS = new Set([
  "action",
  "app_version",
  "attachment_categories",
  "category",
  "change_type",
  "constraint",
  "conversation_scope",
  "density",
  "error_code",
  "export_runtime",
  "flow",
  "format",
  "from_section",
  "from_step",
  "generation_path",
  "image_provider",
  "image_quality",
  "item_id",
  "language",
  "method",
  "mode",
  "panel",
  "presentation_mode",
  "provider",
  "provider_group",
  "quality",
  "reason",
  "role",
  "section",
  "selection_source",
  "slides_mode",
  "source",
  "step",
  "step_name",
  "stream_mode",
  "tab",
  "target_kind",
  "target_role",
  "template_source",
  "template_version",
  "text_provider",
  "text_provider_tab",
  "theme_source",
  "to_section",
  "to_step",
  "tone",
  "trigger",
  "user_local_day_of_week",
  "variant",
  "verbosity",
  "web_search_provider",
]);
const SAFE_BOOLEAN_KEYS = new Set([
  "authenticated",
  "auto_retry",
  "blank_fallback",
  "configured",
  "decorative",
  "delete_saved_conversation",
  "embedded",
  "enabled",
  "from_cache",
  "load_failed",
  "prompt_present",
  "sessions_invalidated",
  "web_search",
]);
const SAFE_AGGREGATE_KEYS = new Set([
  "api_key_count",
  "api_key_count_after",
  "api_key_count_before",
  "has_prompt",
  "has_text",
  "message_length_bucket",
  "next_title_length",
  "previous_title_length",
  "prompt_char_count",
  "prompt_word_count",
  "title_length",
  "username_length",
]);
const SAFE_ATTACHMENT_CATEGORIES = new Set([
  "image",
  "other",
  "pdf",
  "presentation",
  "spreadsheet",
  "text",
  "word",
]);
const SENSITIVE_KEY_PATTERN =
  /(?:^|_)(?:api_key|authorization|body|company|content|cookie|credential|email|file_name|file_path|filename|font_name|font_url|header|label|message|model|name|password|path|private_key|prompt|query|request|response|secret|text|title|token|url|username)(?:_|$)/;
const IDENTIFIER_KEY_PATTERN = /(?:^|_)(?:conversation|layout|presentation|resource|slide|template|theme|user)_id(?:_|$)/;
const SAFE_METRIC_KEY_PATTERN =
  /(?:^|_)(?:chars?|code|count|duration|hour|index|length|number|retry|slides?|words?)(?:_|$)|_ms$/;
const SAFE_BOOLEAN_KEY_PATTERN =
  /^(?:can|had|has|include|is|uses)_|_(?:cache|disabled|edit|enabled|failed|fallback|invalidated|present|skipped)$/;
const CATEGORY_VALUE_PATTERN = /^[A-Za-z0-9][A-Za-z0-9_.:-]{0,63}$/;
const SENSITIVE_CATEGORY_VALUE_PATTERN =
  /(?:bearer\s|private[_ -]?key|api[_ -]?key|access[_ -]?token|password|secret|token)|^(?:sk|pk)[-_][A-Za-z0-9]/i;
const FILE_LIKE_CATEGORY_VALUE_PATTERN =
  /\.(?:csv|docm?|docx|env|gif|jpe?g|json|key|md|odp|ods|odt|otf|pdf|pem|png|pptm?|pptx|svg|tiff?|tsv|ttf|txt|webp|woff2?|xlsm?|xlsx|ya?ml)$/i;

/** @param {unknown} value */
function safeErrorField(value) {
  try {
    return typeof value === "string" || typeof value === "number"
      ? String(value)
      : "";
  } catch {
    return "";
  }
}

/** @param {unknown} error @param {string} key */
function readErrorField(error, key) {
  if (!error || (typeof error !== "object" && typeof error !== "function")) {
    return "";
  }
  try {
    return safeErrorField(error[key]);
  } catch {
    return "";
  }
}

/** @param {unknown} error */
function errorStatus(error) {
  const candidates = [
    readErrorField(error, "status"),
    readErrorField(error, "statusCode"),
    readErrorField(error, "code"),
  ];
  try {
    candidates.push(readErrorField(error?.response, "status"));
  } catch {
    // Proxies and throwing getters fail closed.
  }
  for (const candidate of candidates) {
    if (/^[1-5]\d{2}$/.test(candidate)) return Number(candidate);
  }
  return null;
}

/**
 * Converts arbitrary provider/backend/user error text to a finite category.
 * No portion of the original text is returned.
 * @param {unknown} error
 * @param {unknown} fallback
 */
export function categorizeAnalyticsError(error, fallback = "unknown") {
  try {
    if (typeof error === "string" && ERROR_CATEGORY_SET.has(error)) {
      return error;
    }
    const status = errorStatus(error);
    if (status === 401) return "authentication";
    if (status === 403) return "authorization";
    if (status === 404) return "not_found";
    if (status === 408) return "timeout";
    if (status === 409) return "conflict";
    if (status === 413) return "payload_too_large";
    if (status === 422) return "validation";
    if (status === 429) return "rate_limited";
    if (status != null && status >= 500) return "server";
    if (status != null && status >= 400) return "client";

    const direct = safeErrorField(error);
    const name = readErrorField(error, "name");
    const message = readErrorField(error, "message");
    const fallbackText = safeErrorField(fallback);
    const text = `${name} ${message} ${direct} ${fallbackText}`
      .slice(0, MAX_ERROR_CLASSIFICATION_INPUT)
      .toLowerCase();

    if (/abort|cancel/.test(text)) return "cancelled";
    if (/timeout|timed out|deadline/.test(text)) return "timeout";
    if (/rate.?limit|too many requests|quota|\b429\b/.test(text)) {
      return "rate_limited";
    }
    if (/unauthenticated|unauthorized|sign.?in|log.?in|\b401\b/.test(text)) {
      return "authentication";
    }
    if (/forbidden|permission|not allowed|\b403\b/.test(text)) {
      return "authorization";
    }
    if (/not found|\b404\b/.test(text)) return "not_found";
    if (/conflict|already exists|\b409\b/.test(text)) return "conflict";
    if (/too large|payload|\b413\b/.test(text)) return "payload_too_large";
    if (/network|failed to fetch|connection|dns|offline|socket/.test(text)) {
      return "network";
    }
    if (/invalid|validation|required|unsupported|malformed|\b422\b/.test(text)) {
      return "validation";
    }
    if (/internal server|server error|service unavailable|\b5\d{2}\b/.test(text)) {
      return "server";
    }
    if (name === "TypeError" || name === "RangeError" || name === "ReferenceError") {
      return "runtime";
    }
  } catch {
    return "unknown";
  }
  return "unknown";
}

/** Backwards-compatible name; output is now a category, never error text. */
export const sanitizeAnalyticsError = categorizeAnalyticsError;

/** @param {number | null | undefined} bytes */
export function bucketFileSize(bytes) {
  if (typeof bytes !== "number" || Number.isNaN(bytes) || bytes < 0) {
    return "unknown";
  }
  if (bytes === 0) return "0";
  if (bytes < 100 * 1024) return "<100KB";
  if (bytes < 1024 * 1024) return "100KB-1MB";
  if (bytes < 5 * 1024 * 1024) return "1MB-5MB";
  if (bytes < 20 * 1024 * 1024) return "5MB-20MB";
  if (bytes < 100 * 1024 * 1024) return "20MB-100MB";
  return "100MB+";
}

/** @param {number} length */
export function bucketMessageLength(length) {
  if (!Number.isFinite(length) || length <= 0) return "0";
  if (length < 50) return "<50";
  if (length < 200) return "50-199";
  if (length < 500) return "200-499";
  if (length < 1000) return "500-999";
  if (length < 2000) return "1000-1999";
  return "2000+";
}

/** @param {unknown} fileName */
export function categorizeFileExtension(fileName) {
  if (typeof fileName !== "string") return "unknown";
  const normalized = fileName.trim().toLowerCase();
  const separator = Math.max(normalized.lastIndexOf("/"), normalized.lastIndexOf("\\"));
  const basename = normalized.slice(separator + 1);
  const dot = basename.lastIndexOf(".");
  if (dot < 0 || dot === basename.length - 1) return "none";
  return SAFE_FILE_EXTENSIONS.get(basename.slice(dot + 1)) ?? "other";
}

/** @param {unknown} value */
function sanitizeCategory(value) {
  if (typeof value !== "string") return null;
  const normalized = value.trim();
  if (!normalized) return "unknown";
  if (
    normalized.length > MAX_CATEGORY_LENGTH ||
    /[\u0000-\u001f\u007f-\u009f\u2028\u2029\u202a-\u202e\u2066-\u2069]/u.test(
      normalized,
    ) ||
    /[/\\@]/.test(normalized) ||
    SENSITIVE_CATEGORY_VALUE_PATTERN.test(normalized) ||
    FILE_LIKE_CATEGORY_VALUE_PATTERN.test(normalized) ||
    /^[A-Za-z0-9]{24,}$/.test(normalized)
  ) {
    return "redacted";
  }
  return CATEGORY_VALUE_PATTERN.test(normalized) ? normalized : "other";
}

/** @param {unknown} value */
function sanitizeMetric(value) {
  if (typeof value !== "number" || !Number.isFinite(value)) return null;
  const bounded = Math.max(-1_000_000_000, Math.min(1_000_000_000, value));
  return Number.isInteger(bounded) ? bounded : Number(bounded.toFixed(3));
}

/** @param {unknown} value */
function sanitizeAttachmentCategories(value) {
  if (typeof value !== "string") return null;
  const categories = [...new Set(value.split(",").map((item) => item.trim()))]
    .filter((item) => SAFE_ATTACHMENT_CATEGORIES.has(item))
    .sort();
  return categories.length ? categories.join(",") : "other";
}

/** @param {unknown} value */
export function categorizeTelemetryRoute(value) {
  if (typeof value !== "string" || !value.trim()) return "unknown";
  const candidate = value.trim();
  if (
    candidate.length > 2048 ||
    /[\u0000-\u001f\u007f-\u009f\\]/u.test(candidate)
  ) {
    return "other";
  }
  try {
    const base = "https://presenton.invalid";
    const parsed = new URL(candidate, base);
    if (parsed.protocol !== "http:" && parsed.protocol !== "https:") return "other";
    if (parsed.origin !== base) return "external";
    const segment = parsed.pathname.split("/").filter(Boolean)[0]?.toLowerCase();
    if (!segment) return "root";
    return ROUTE_CATEGORIES.has(segment) ? segment : "other";
  } catch {
    return "other";
  }
}

/** @param {string} key */
function isSafeBooleanKey(key) {
  return SAFE_BOOLEAN_KEYS.has(key) || SAFE_BOOLEAN_KEY_PATTERN.test(key);
}

/**
 * Fail-closed analytics boundary. Unknown keys, identifiers, raw names/paths,
 * nested structures, and arrays are omitted rather than forwarded.
 * @param {unknown} properties
 * @returns {Record<string, string | number | boolean> | undefined}
 */
export function sanitizeTelemetryProperties(properties) {
  if (!properties || typeof properties !== "object" || Array.isArray(properties)) {
    return undefined;
  }

  let keys;
  try {
    keys = Object.keys(properties).slice(0, MAX_TELEMETRY_PROPERTIES);
  } catch {
    return undefined;
  }

  /** @type {Record<string, string | number | boolean>} */
  const safe = {};
  for (const key of keys) {
    if (!/^[a-z][a-z0-9_]{0,63}$/.test(key)) continue;
    let value;
    try {
      value = properties[key];
    } catch {
      continue;
    }

    if (ERROR_INPUT_KEYS.has(key)) {
      safe.error_category = categorizeAnalyticsError(value);
      continue;
    }
    if (key === "error_category") {
      safe.error_category =
        typeof value === "string" && ERROR_CATEGORY_SET.has(value)
          ? value
          : "unknown";
      continue;
    }
    if (ROUTE_KEYS.has(key)) {
      safe[ROUTE_KEYS.get(key)] = categorizeTelemetryRoute(value);
      continue;
    }
    if (key.endsWith("_size_bytes")) {
      const metric = sanitizeMetric(value);
      if (metric != null) {
        safe[key.replace(/_size_bytes$/, "_size_bucket")] = bucketFileSize(metric);
      }
      continue;
    }
    if (key === "file_size_bucket") {
      safe.file_size_bucket =
        typeof value === "string" && FILE_SIZE_BUCKETS.has(value)
          ? value
          : "unknown";
      continue;
    }
    if (key === "file_extension") {
      const raw = typeof value === "string" ? value.replace(/^\./, "") : "";
      safe.file_extension = SAFE_FILE_EXTENSIONS.get(raw.toLowerCase()) ??
        (value === "none" || value === "unknown" || value === "other"
          ? value
          : "other");
      continue;
    }
    if (key === "attachment_categories") {
      const categories = sanitizeAttachmentCategories(value);
      if (categories) safe.attachment_categories = categories;
      continue;
    }
    if (key === "destination") {
      safe.destination_route = categorizeTelemetryRoute(value);
      continue;
    }
    if (SAFE_AGGREGATE_KEYS.has(key)) {
      if (typeof value === "number") {
        const metric = sanitizeMetric(value);
        if (metric != null) safe[key] = metric;
      } else if (typeof value === "boolean") {
        safe[key] = value;
      } else if (key === "message_length_bucket") {
        safe[key] =
          typeof value === "string" && MESSAGE_LENGTH_BUCKETS.has(value)
            ? value
            : "unknown";
      }
      continue;
    }
    if (SAFE_CATEGORY_KEYS.has(key)) {
      const category = sanitizeCategory(value);
      if (category) safe[key] = category;
      continue;
    }
    if (SENSITIVE_KEY_PATTERN.test(key) || IDENTIFIER_KEY_PATTERN.test(key)) {
      continue;
    }
    if (typeof value === "boolean" && isSafeBooleanKey(key)) {
      safe[key] = value;
      continue;
    }
    if (SAFE_METRIC_KEY_PATTERN.test(key)) {
      const metric = sanitizeMetric(value);
      if (metric != null) safe[key] = metric;
      continue;
    }
  }

  return Object.keys(safe).length ? safe : undefined;
}
