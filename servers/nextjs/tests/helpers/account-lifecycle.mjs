import { readFileSync } from "node:fs";

export const ACCOUNT_LIFECYCLE_REDACTED_VALUE = "[REDACTED]";
export const ACCOUNT_LIFECYCLE_REDACTED_EMAIL = "[REDACTED_EMAIL]";

export const ACCOUNT_LIFECYCLE_ARTIFACT_DEFAULTS = Object.freeze({
  screenshotOnRunFailure: false,
  video: false,
  trace: false,
  redactSelectors: Object.freeze([
    "[data-account-email]",
    "[data-account-secret]",
    "[data-account-token]",
    'input[type="password"]',
    'input[autocomplete="one-time-code"]',
  ]),
});

const RESERVED_EMAIL = /^[a-z0-9._%+-]+@example\.test$/i;
const SECRET_KEY = /(token|secret|password|cookie)/i;
const EMAIL_KEY = /(email|recipient|address)/i;

export function loadAccountLifecycleFixture(locale) {
  if (locale !== "en" && locale !== "ar") {
    throw new TypeError("account lifecycle fixture locale must be en or ar");
  }
  return JSON.parse(
    readFileSync(
      new URL(`../../cypress/fixtures/account-lifecycle/${locale}.json`, import.meta.url),
      "utf8",
    ),
  );
}

export function assertSecretSafeAccountLifecycleFixture(value, path = "fixture") {
  if (Array.isArray(value)) {
    value.forEach((entry, index) =>
      assertSecretSafeAccountLifecycleFixture(entry, `${path}[${index}]`),
    );
    return;
  }
  if (!value || typeof value !== "object") return;

  for (const [key, entry] of Object.entries(value)) {
    const entryPath = `${path}.${key}`;
    if (typeof entry === "string" && EMAIL_KEY.test(key)) {
      if (!RESERVED_EMAIL.test(entry)) {
        throw new Error(`${entryPath} must use the reserved example.test domain`);
      }
    }
    if (typeof entry === "string" && SECRET_KEY.test(key)) {
      if (entry !== ACCOUNT_LIFECYCLE_REDACTED_VALUE) {
        throw new Error(`${entryPath} must be redacted`);
      }
    }
    if (key === "actionUrl" && typeof entry === "string") {
      if (!entry.endsWith(`#token=${ACCOUNT_LIFECYCLE_REDACTED_VALUE}`)) {
        throw new Error(`${entryPath} must contain only a redacted fragment token`);
      }
    }
    assertSecretSafeAccountLifecycleFixture(entry, entryPath);
  }
}

export function redactAccountLifecycleArtifact(value, key = "") {
  if (Array.isArray(value)) {
    return value.map((entry) => redactAccountLifecycleArtifact(entry, key));
  }
  if (value && typeof value === "object") {
    return Object.fromEntries(
      Object.entries(value).map(([entryKey, entry]) => [
        entryKey,
        redactAccountLifecycleArtifact(entry, entryKey),
      ]),
    );
  }
  if (typeof value === "string" && EMAIL_KEY.test(key)) {
    return ACCOUNT_LIFECYCLE_REDACTED_EMAIL;
  }
  if (typeof value === "string" && (SECRET_KEY.test(key) || key === "actionUrl")) {
    return ACCOUNT_LIFECYCLE_REDACTED_VALUE;
  }
  return value;
}
