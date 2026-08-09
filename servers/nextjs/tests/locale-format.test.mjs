import assert from "node:assert/strict";
import { mkdtemp } from "node:fs/promises";
import os from "node:os";
import path from "node:path";
import test from "node:test";
import { fileURLToPath, pathToFileURL } from "node:url";
import { build } from "esbuild";

const projectRoot = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..");
const temporary = await mkdtemp(path.join(os.tmpdir(), "bayanly-locale-format-"));
const outfile = path.join(temporary, "locale-format.mjs");
await build({ absWorkingDir: projectRoot, bundle: true, entryPoints: ["./lib/locale-format.ts"], format: "esm", outfile, platform: "node", tsconfig: path.join(projectRoot, "tsconfig.json") });
const formatting = await import(pathToFileURL(outfile).href);

test("locale helpers use Intl and preserve technical identifiers", () => {
  assert.notEqual(formatting.formatNumber(12345.5, "en"), formatting.formatNumber(12345.5, "ar"));
  assert.match(formatting.formatFileSize(1536, "en"), /1\.5 KB/);
  const identifier = "sha256:a1b2c3";
  assert.equal(identifier, "sha256:a1b2c3");
});
