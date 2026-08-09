import assert from "node:assert/strict";
import path from "node:path";
import test from "node:test";
import { fileURLToPath } from "node:url";

import { checkLocalization } from "../../../scripts/check-localization.mjs";

const projectRoot = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..");

test("English and Arabic catalogs are complete, plain-text, and interpolation-safe", async () => {
  const report = await checkLocalization();
  assert.ok(report.keyCount >= 150, `expected launch catalog, received ${report.keyCount} keys`);
  assert.equal(report.missing, 0);
  assert.ok(report.unused.length < report.keyCount);
  assert.ok(projectRoot.endsWith(path.join("servers", "nextjs")));
});

