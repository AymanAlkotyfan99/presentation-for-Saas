import assert from "node:assert/strict";
import { mkdtemp } from "node:fs/promises";
import os from "node:os";
import path from "node:path";
import test from "node:test";
import { fileURLToPath, pathToFileURL } from "node:url";
import { build } from "esbuild";

const projectRoot = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..");
const temporary = await mkdtemp(path.join(os.tmpdir(), "bayanly-i18n-observability-"));
const outfile = path.join(temporary, "observability.mjs");
await build({
  absWorkingDir: projectRoot,
  bundle: true,
  entryPoints: ["./i18n/observability.ts"],
  format: "esm",
  outfile,
  platform: "node",
  tsconfig: path.join(projectRoot, "tsconfig.json"),
});
const { localizationSignalPayload } = await import(pathToFileURL(outfile).href);

test("localization telemetry keeps only controlled non-content values", () => {
  assert.deepEqual(
    localizationSignalPayload("locale_selected", {
      locale: "ar",
      source: "locale_switcher",
      namespace: "auth",
      reason: "unknown_code",
      prompt: "must never appear",
    }),
    {
      signal: "locale_selected",
      locale: "ar",
      source: "locale_switcher",
      namespace: "auth",
      reason: "unknown_code",
    },
  );
  assert.deepEqual(
    localizationSignalPayload("missing_key", {
      namespace: "user-entered-value",
      source: "untrusted",
      reason: "raw failure details",
    }),
    { signal: "missing_key" },
  );
});
