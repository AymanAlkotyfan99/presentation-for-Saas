import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import test from "node:test";

const panel = readFileSync(new URL("../features/providers/ProviderRegistryPanel.tsx", import.meta.url), "utf8");
const api = readFileSync(new URL("../features/providers/api.ts", import.meta.url), "utf8");
const types = readFileSync(new URL("../features/providers/types.ts", import.meta.url), "utf8");
const en = JSON.parse(readFileSync(new URL("../messages/en.json", import.meta.url), "utf8"));
const ar = JSON.parse(readFileSync(new URL("../messages/ar.json", import.meta.url), "utf8"));

test("provider registry UI exposes complete workspace configuration controls", () => {
  for (const contract of [
    "capabilityModels",
    "safeConfig",
    "priorityAccountIds",
    "pinnedAccountId",
    "setCapability",
    "simulate",
    "emergencyDisabled",
    "connection-tests",
  ]) {
    assert.match(`${panel}\n${api}`, new RegExp(contract.replace(/[.*+?^${}()|[\]\\]/g, "\\$&")));
  }
  assert.match(panel, /type="password"/);
  assert.match(panel, /placeholder=\{account\.maskedSecret/);
  assert.doesNotMatch(panel, /value=\{account\.maskedSecret/);
  assert.match(panel, /dir="auto"/);
});

test("provider client stays authenticated and models never expose secret material", () => {
  assert.match(api, /credentials:\s*"include"/);
  assert.match(api, /\/accounts\/\$\{encodeURIComponent\(id\)\}\/secret/);
  assert.match(types, /hasSecret:\s*boolean/);
  assert.match(types, /maskedSecret:\s*string \| null/);
  assert.doesNotMatch(types, /\bsecret:\s*string/);
});

test("provider configuration controls are localized in English and Arabic", () => {
  for (const key of [
    "defaultModel",
    "capabilityModels",
    "safeConfig",
    "regionPolicy",
    "priorityOrder",
    "pinnedAccount",
    "simulate",
    "saveAccount",
  ]) {
    assert.equal(typeof en.providers[key], "string", `missing English providers.${key}`);
    assert.equal(typeof ar.providers[key], "string", `missing Arabic providers.${key}`);
    assert.ok(en.providers[key].length > 2);
    assert.ok(ar.providers[key].length > 2);
  }
});
