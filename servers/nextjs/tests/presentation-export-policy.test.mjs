import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { dirname, resolve } from "node:path";
import test from "node:test";
import { fileURLToPath } from "node:url";

const root = resolve(dirname(fileURLToPath(import.meta.url)), "..");
const read = (path) => readFileSync(resolve(root, path), "utf8");

test("the unverified exporter is disabled by default at every execution boundary", () => {
  const policy = read("lib/presentation-export-policy.ts");
  assert.match(policy, /ENABLE_UNVERIFIED_PRESENTATION_EXPORT === "true"/);

  const nextRoute = read("app/api/export-presentation/route.ts");
  assert.match(nextRoute, /UNVERIFIED_PRESENTATION_EXPORT_ERROR_CODE/);
  assert.match(nextRoute, /status: 503/);

  const backend = read("../fastapi/utils/export_utils.py");
  assert.match(backend, /ensure_unverified_export_enabled/);
  const backendService = read("../fastapi/services/export_task_service.py");
  assert.match(backendService, /ENABLE_UNVERIFIED_PRESENTATION_EXPORT/);
  assert.match(backendService, /UNVERIFIED_PRESENTATION_EXPORT_DISABLED/);
  assert.match(
    backendService,
    /_run_task_locked[\s\S]*?ensure_unverified_export_enabled\(\)/,
  );

  const electron = read("../../electron/app/ipc/export_handlers.ts");
  assert.match(electron, /ENABLE_UNVERIFIED_PRESENTATION_EXPORT/);
  assert.match(electron, /UNVERIFIED_PRESENTATION_EXPORT_DISABLED/);
});
