import assert from "node:assert/strict";
import fs from "node:fs";
import path from "node:path";
import test from "node:test";
import { spawnSync } from "node:child_process";
import { validateProductIdentity } from "./generate-product-metadata.mjs";

const identity = JSON.parse(fs.readFileSync(path.resolve("config/product-identity.json"), "utf8"));

test("approved identity validates", () => {
  assert.equal(validateProductIdentity(identity).product.name, "Bayanly AI");
});

test("placeholder domain and compatibility app ID cannot become implicit production values", () => {
  assert.equal(identity.web.isPlaceholder, true);
  assert.equal(identity.web.operationalStatus, "REQUIRES_DOMAIN_CONFIGURATION");
  assert.equal(identity.desktop.activeAppId, "com.presenton.presenton");
  assert.notEqual(identity.desktop.requestedAppId, identity.desktop.activeAppId);
});

test("production brand gate fails closed while approvals are pending", () => {
  const result = spawnSync(process.execPath, ["scripts/check-brand-consistency.mjs", "--production"], {
    cwd: process.cwd(),
    encoding: "utf8",
  });
  assert.notEqual(result.status, 0);
  assert.match(result.stderr, /placeholder/);
  assert.match(result.stderr, /legal clearance/);
  assert.match(result.stderr, /update channel/);
});
