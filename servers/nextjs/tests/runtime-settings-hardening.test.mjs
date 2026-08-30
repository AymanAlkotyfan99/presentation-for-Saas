import assert from "node:assert/strict";
import { mkdtemp, readFile, rm } from "node:fs/promises";
import os from "node:os";
import path from "node:path";
import test, { after, before } from "node:test";
import { fileURLToPath, pathToFileURL } from "node:url";
import { build } from "esbuild";

const nextRoot = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..");
const repositoryRoot = path.resolve(nextRoot, "../..");
const source = (relative) => readFile(path.join(repositoryRoot, relative), "utf8");
let temporary;
let helpers;

before(async () => {
  temporary = await mkdtemp(path.join(os.tmpdir(), "bayanly-runtime-settings-"));
  const outfile = path.join(temporary, "store-helpers.mjs");
  await build({
    absWorkingDir: nextRoot,
    entryPoints: ["./utils/storeHelpers.ts"],
    bundle: true,
    platform: "node",
    format: "esm",
    outfile,
    tsconfig: path.join(nextRoot, "tsconfig.json"),
    logLevel: "silent",
  });
  helpers = await import(pathToFileURL(outfile).href);
});

after(async () => {
  if (temporary) await rm(temporary, { recursive: true, force: true });
});

test("Settings validation and persistence patches are section scoped", () => {
  const config = {
    LLM: "openrouter",
    OPENROUTER_API_KEY: "configured",
    OPENROUTER_MODEL: "provider/model",
    IMAGE_PROVIDER: "pexels",
    PEXELS_API_KEY: "",
    DISABLE_IMAGE_GENERATION: false,
    WEB_GROUNDING: false,
  };

  assert.equal(helpers.getTextProviderConfigValidationError(config), null);
  assert.match(helpers.getImageProviderConfigValidationError(config), /Pexels/);
  assert.match(helpers.getLLMConfigValidationError(config), /Pexels/);

  const textPatch = helpers.providerConfigPatchForSection(config, "text");
  assert.equal(textPatch.LLM, "openrouter");
  assert.equal("IMAGE_PROVIDER" in textPatch, false);
  assert.equal("PEXELS_API_KEY" in textPatch, false);

  const imagePatch = helpers.providerConfigPatchForSection(config, "image");
  assert.equal(imagePatch.IMAGE_PROVIDER, "pexels");
  assert.equal("LLM" in imagePatch, false);
  assert.equal("OPENROUTER_API_KEY" in imagePatch, false);
});

test("startup navigation is server-authoritative and provider-independent", async () => {
  const [initializer, rootPage] = await Promise.all([
    source("servers/nextjs/app/ConfigurationInitializer.tsx"),
    source("servers/nextjs/app/page.tsx"),
  ]);

  assert.doesNotMatch(initializer, /NAVIGATION_TIMEOUT|setInterval|router\.push/);
  assert.doesNotMatch(initializer, /models\/available|isOllamaModelAvailable|generationUnavailable/);
  assert.match(rootPage, /redirect\(localizePathname\("\/dashboard"/);
  assert.match(rootPage, /await requestLocale\(\)/);
});

test("workspace discovery checks runtime capability before workspace endpoints", async () => {
  const [provider, api] = await Promise.all([
    source("servers/nextjs/features/workspaces/WorkspaceProvider.tsx"),
    source("servers/nextjs/features/workspaces/api.ts"),
  ]);
  assert.match(api, /\/api\/v1\/runtime\/capabilities/);
  assert.ok(provider.indexOf("getRuntimeCapabilities()") < provider.indexOf("workspaceApi.current()"));
  assert.match(provider, /if \(!runtimeCapabilities\.workspaces\)/);
});

test("model discovery aborts stale requests and preserves explicit models on failure", async () => {
  const textProvider = await source(
    "servers/nextjs/app/(presentation-generator)/(dashboard)/settings/TextProvider.tsx",
  );
  assert.match(textProvider, /new AbortController\(\)/);
  assert.match(textProvider, /requestId !== modelRequestId\.current/);
  assert.match(textProvider, /currentModelField && !currentModel/);
  assert.doesNotMatch(textProvider, /onInputChange\("", currentModelField\)/);
  assert.match(textProvider, /Preserve the configured model and last successful list/);
});

test("dev mounts keep Next dependency and build churn off the Windows bind", async () => {
  const [compose, startup] = await Promise.all([
    source("docker-compose.yml"),
    source("start.js"),
  ]);
  assert.equal((compose.match(/presenton_nextjs_node_modules:\/app\/servers\/nextjs\/node_modules/g) || []).length, 2);
  assert.equal((compose.match(/presenton_nextjs_build_cache:\/app\/servers\/nextjs\/\.next-build/g) || []).length, 2);
  assert.match(startup, /presenton-lock-sha256/);
  assert.match(startup, /package lock unchanged/);
  assert.match(startup, /isDev \? \["--webpack"\]/);
});

test("new provider errors have matching English and Arabic catalog keys", async () => {
  const [english, arabic] = await Promise.all([
    readFile(path.join(nextRoot, "messages/en.json"), "utf8").then(JSON.parse),
    readFile(path.join(nextRoot, "messages/ar.json"), "utf8").then(JSON.parse),
  ]);
  const keys = [
    "textValidationFailed",
    "imageValidationFailed",
    "webSearchValidationFailed",
    "imageProviderDnsUnavailable",
    "imageProviderCredentialsRejected",
    "imageProviderResponseInvalid",
  ];
  for (const key of keys) {
    assert.equal(typeof english.settings[key], "string");
    assert.equal(typeof arabic.settings[key], "string");
  }
});
