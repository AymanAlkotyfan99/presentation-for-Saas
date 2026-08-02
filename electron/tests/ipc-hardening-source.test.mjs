import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";
import test from "node:test";

const [main, readFileHandler, exportHandler] = await Promise.all([
  readFile(new URL("../app/main.ts", import.meta.url), "utf8"),
  readFile(new URL("../app/ipc/read_file.ts", import.meta.url), "utf8"),
  readFile(new URL("../app/ipc/export_handlers.ts", import.meta.url), "utf8"),
]);

test("the main renderer requests Chromium sandboxing", () => {
  assert.match(main, /contextIsolation:\s*true/);
  assert.match(main, /nodeIntegration:\s*false/);
  assert.match(main, /sandbox:\s*true/);
  assert.doesNotMatch(main, /appendSwitch\(["']no-sandbox["']\)/);
});

test("every exposed invoke handler checks the renderer origin", () => {
  assert.match(readFileHandler, /assertTrustedIpcSender\(event, trustedOrigin\)/);
  assert.match(exportHandler, /assertTrustedIpcSender\(event, trustedOrigin\)/);
  assert.match(exportHandler, /assertValidExportRequest\(request\)/);
});
