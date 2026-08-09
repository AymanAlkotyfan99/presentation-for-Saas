import assert from "node:assert/strict";
import { mkdtemp } from "node:fs/promises";
import os from "node:os";
import path from "node:path";
import test from "node:test";
import { fileURLToPath, pathToFileURL } from "node:url";
import { build } from "esbuild";

const projectRoot = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..");
const temporary = await mkdtemp(path.join(os.tmpdir(), "bayanly-i18n-routing-"));
const outfile = path.join(temporary, "routing.mjs");
await build({
  absWorkingDir: projectRoot,
  bundle: true,
  entryPoints: ["./i18n/routing.ts"],
  format: "esm",
  outfile,
  platform: "node",
  tsconfig: path.join(projectRoot, "tsconfig.json"),
});
const routing = await import(pathToFileURL(outfile).href);

test("locale routing preserves deep paths and has no prefix loop", () => {
  assert.equal(routing.localizePathname("/presentation", "ar"), "/ar/presentation");
  assert.equal(routing.localizePathname("/en/presentation", "ar"), "/ar/presentation");
  assert.equal(routing.stripLocalePrefix("/ar/presentation"), "/presentation");
  assert.equal(routing.localeFromPathname("/ar/presentation"), "ar");
});

test("locale negotiation follows explicit, saved, cookie, browser, default priority", () => {
  assert.equal(routing.negotiateLocale({ pathname: "/ar/dashboard", savedLocale: "en" }), "ar");
  assert.equal(routing.negotiateLocale({ pathname: "/dashboard", savedLocale: "ar", cookieLocale: "en" }), "ar");
  assert.equal(routing.negotiateLocale({ pathname: "/dashboard", cookieLocale: "ar" }), "ar");
  assert.equal(routing.negotiateLocale({ pathname: "/dashboard", acceptLanguage: "fr;q=0.5, ar;q=0.9" }), "ar");
  assert.equal(routing.negotiateLocale({ pathname: "/dashboard", savedLocale: "fr", cookieLocale: "ar" }), "ar");
  assert.equal(routing.negotiateLocale({ pathname: "/dashboard", acceptLanguage: "fr;q=1, ar;q=0.9" }), "ar");
  assert.equal(routing.negotiateLocale({ pathname: "/dashboard", acceptLanguage: "ar;q=0, en;q=0.8" }), "en");
  assert.equal(routing.negotiateLocale({ pathname: "/dashboard" }), "en");
});

test("API, assets, callbacks and non-idempotent requests bypass locale routing", () => {
  assert.equal(routing.shouldBypassLocaleRouting("/api/v1/auth/status"), true);
  assert.equal(routing.shouldBypassLocaleRouting("/_next/static/chunk.js"), true);
  assert.equal(routing.shouldBypassLocaleRouting("/brand/v1/logo.png"), true);
  assert.equal(routing.shouldBypassLocaleRouting("/dashboard", "POST"), true);
  assert.equal(routing.shouldBypassLocaleRouting("/dashboard", "GET"), false);
});
