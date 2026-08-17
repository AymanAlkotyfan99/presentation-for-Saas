import assert from "node:assert/strict";
import { mkdtemp, readFile } from "node:fs/promises";
import os from "node:os";
import path from "node:path";
import test from "node:test";
import { fileURLToPath, pathToFileURL } from "node:url";
import { build } from "esbuild";

const projectRoot = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..");
const temporary = await mkdtemp(path.join(os.tmpdir(), "bayanly-product-experience-"));

async function importTypeScript(entryPoint, name) {
  const outfile = path.join(temporary, `${name}.mjs`);
  await build({
    absWorkingDir: projectRoot,
    bundle: true,
    entryPoints: [entryPoint],
    format: "esm",
    outfile,
    platform: "node",
    tsconfig: path.join(projectRoot, "tsconfig.json"),
  });
  return import(pathToFileURL(outfile).href);
}

const navigation = await importTypeScript("./lib/product-navigation.ts", "navigation");
const preferences = await importTypeScript("./lib/product-preferences.ts", "preferences");

test("consumer navigation is locale-aware and blocks unsafe return targets", () => {
  assert.equal(navigation.isProductRouteActive("/en/presentations/123", "/presentations"), true);
  assert.equal(navigation.isProductRouteActive("/ar/dashboard", "/dashboard"), true);
  assert.equal(navigation.isProductRouteActive("/ar/templates", "/dashboard"), false);
  assert.equal(navigation.safeReturnPath("/ar/presentation?id=123"), "/ar/presentation?id=123");
  assert.equal(navigation.safeReturnPath("//evil.example/path"), null);
  assert.equal(navigation.safeReturnPath("https://evil.example/path"), null);
  assert.equal(navigation.safeReturnPath("/api/v1/auth/status"), null);
});

test("product preferences normalize untrusted local values", () => {
  const normalized = preferences.normalizeProductPreferences({
    slideCount: "500",
    designStyle: "<script>",
    colorPalette: "ocean",
    aspectRatio: "4:3",
    imagePreference: "none",
    motion: "reduced",
  });
  assert.equal(normalized.slideCount, "10");
  assert.equal(normalized.designStyle, "modern");
  assert.equal(normalized.colorPalette, "ocean");
  assert.equal(normalized.aspectRatio, "4:3");
  assert.equal(normalized.imagePreference, "none");
  assert.equal(normalized.motion, "reduced");
});

test("generation instructions carry product choices without provider details", () => {
  const instructions = preferences.productPreferenceInstructions({
    ...preferences.DEFAULT_PRODUCT_PREFERENCES,
    designStyle: "academic",
    imagePreference: "none",
  }, "Use a concise tone.");
  assert.match(instructions, /Use a concise tone/);
  assert.match(instructions, /Design direction: academic/);
  assert.match(instructions, /typography, shapes, and charts/);
  assert.doesNotMatch(instructions, /OpenAI|ProviderExecutor|API key|Redis/i);
});

test("normal settings and the admin platform remain separate", async () => {
  const userSettings = await readFile(
    path.join(projectRoot, "app/(presentation-generator)/(dashboard)/settings/page.tsx"),
    "utf8",
  );
  const adminPlatform = await readFile(
    path.join(projectRoot, "app/(presentation-generator)/(dashboard)/admin/platform/page.tsx"),
    "utf8",
  );
  const appShell = await readFile(
    path.join(projectRoot, "components/product-shell/AppShell.tsx"),
    "utf8",
  );

  assert.match(userSettings, /UserPreferencesPage/);
  assert.doesNotMatch(userSettings, /SettingPage|Provider/);
  assert.match(adminPlatform, /requireAdminSession/);
  assert.match(adminPlatform, /SettingPage/);
  assert.match(appShell, /role === "admin"/);
  assert.doesNotMatch(appShell, /OpenAI|ProviderExecutor|API key|Redis/);
});
