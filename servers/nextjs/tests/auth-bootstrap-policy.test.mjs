import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { dirname, resolve } from "node:path";
import test from "node:test";
import { fileURLToPath } from "node:url";

const nextRoot = resolve(dirname(fileURLToPath(import.meta.url)), "..");

test("the browser offers sign-in only and cannot call a public setup endpoint", () => {
  const authGate = readFileSync(
    resolve(nextRoot, "components", "Auth", "AuthGate.tsx"),
    "utf8",
  );

  assert.doesNotMatch(authGate, /\/api\/v1\/auth\/setup/);
  assert.doesNotMatch(authGate, /Create your admin login/);
  assert.match(authGate, /\/api\/v1\/auth\/login/);
});
