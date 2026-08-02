import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { dirname, resolve } from "node:path";
import test from "node:test";
import { fileURLToPath } from "node:url";

const root = resolve(dirname(fileURLToPath(import.meta.url)), "..");
const source = (path) => readFileSync(resolve(root, path), "utf8");

test("legacy custom layout execution is opt-in on every execution boundary", () => {
  assert.match(
    source("app/hooks/compileLayout.ts"),
    /if \(!isUnsafeCustomLayoutClientEnabled\(\)\)[\s\S]*new Function/,
  );
  assert.match(
    source("lib/server-template-layouts.ts"),
    /if \(!isUnsafeCustomLayoutServerEnabled\(\)\)[\s\S]*compileTemplateSchema\(layout\.layout_code\)/,
  );
  for (const route of [
    "app/api/template/custom/route.ts",
    "app/api/validate-layout-code/route.ts",
  ]) {
    assert.match(source(route), /UNSAFE_CUSTOM_LAYOUTS_ERROR_CODE/);
    assert.match(source(route), /status: 503/);
  }
});

test("server and browser opt-ins are deliberately separate", () => {
  const policy = source("lib/unsafe-custom-layouts.ts");
  assert.match(policy, /ENABLE_UNSAFE_CUSTOM_LAYOUTS/);
  assert.match(policy, /NEXT_PUBLIC_ENABLE_UNSAFE_CUSTOM_LAYOUTS/);
  assert.match(policy, /=== "true"/);
});

test("FastAPI refuses database-backed executable layouts by default", () => {
  const backend = source("../fastapi/templates/custom_layout_from_db.py");
  assert.match(backend, /ENABLE_UNSAFE_CUSTOM_LAYOUTS/);
  assert.match(backend, /UNSAFE_CUSTOM_LAYOUTS_DISABLED/);
  assert.match(backend, /status_code=503/);
});
