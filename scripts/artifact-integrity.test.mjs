import assert from "node:assert/strict";
import { createRequire } from "node:module";
import { mkdtempSync, writeFileSync, existsSync, readFileSync } from "node:fs";
import { tmpdir } from "node:os";
import { join } from "node:path";
import test from "node:test";

const require = createRequire(import.meta.url);
const rootVerifier = require("./sync-presentation-export.cjs");
const electronVerifier = require("../electron/scripts/sync-export-runtime.cjs");

for (const [name, verifier] of [
  ["container export sync", rootVerifier],
  ["Electron export sync", electronVerifier],
]) {
  test(`${name} deletes and rejects a checksum mismatch`, () => {
    const directory = mkdtempSync(join(tmpdir(), "presenton-integrity-"));
    const artifact = join(directory, "runtime.zip");
    writeFileSync(artifact, "deterministic fake archive");
    const incorrectDigest = "0".repeat(64);

    assert.throws(
      () => verifier.verifySha256(artifact, incorrectDigest),
      /SHA-256 mismatch/,
    );
    assert.equal(existsSync(artifact), false);
  });
}

test("container export sync has a non-shell Windows archive extractor", () => {
  const source = readFileSync(
    new URL("./sync-presentation-export.cjs", import.meta.url),
    "utf8",
  );
  assert.match(source, /process\.platform\s*===\s*["']win32["']/);
  assert.match(source, /Expand-Archive\s+-LiteralPath/);
  assert.match(source, /PRESENTON_EXPORT_ARCHIVE_PATH/);
  assert.doesNotMatch(source, /execSync\s*\(/);
});
