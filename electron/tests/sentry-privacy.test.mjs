import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";
import test from "node:test";

const [mainSource, rendererSource] = await Promise.all([
  readFile(new URL("../app/sentry/main.ts", import.meta.url), "utf8"),
  readFile(new URL("../app/preloads/sentry.ts", import.meta.url), "utf8"),
]);

test("Electron error reporting and tracing are opt-in", () => {
  for (const source of [mainSource, rendererSource]) {
    assert.match(source, /SENTRY_ENABLED, false/);
    assert.match(source, /SENTRY_ENABLE_TRACING, false/);
    assert.match(source, /SENTRY_SEND_DEFAULT_PII, false/);
    assert.match(source, /SENTRY_ENABLE_LOGS, false/);
  }
});

test("Electron error reporting requires an explicit DSN and has no compiled destination", () => {
  for (const source of [mainSource, rendererSource]) {
    assert.match(source, /process\.env\.SENTRY_DSN\?\.trim\(\)/);
    assert.match(source, /if \(!isEnabled \|\| !dsn\)/);
    assert.doesNotMatch(source, /const\s+dsn\s*=\s*["']https?:\/\//i);
    assert.doesNotMatch(source, /https?:\/\/[^"']+@[^"']+/i);
  }
});

test("opt-in Electron tracing and replay use low-volume defaults", () => {
  assert.match(mainSource, /SENTRY_TRACES_SAMPLE_RATE, 0\.1/);
  assert.match(rendererSource, /SENTRY_TRACES_SAMPLE_RATE, 0\.1/);
  assert.match(rendererSource, /SENTRY_REPLAYS_SESSION_SAMPLE_RATE, 0/);
  assert.match(rendererSource, /SENTRY_REPLAYS_ON_ERROR_SAMPLE_RATE, 0\.1/);
});
