import assert from "node:assert/strict";
import fs from "node:fs";
import os from "node:os";
import path from "node:path";
import test from "node:test";
import { createRequire } from "node:module";
import { fileURLToPath } from "node:url";

const require = createRequire(import.meta.url);
const testDir = path.dirname(fileURLToPath(import.meta.url));
const electronRoot = path.join(testDir, "..");
const packageJson = JSON.parse(
  fs.readFileSync(path.join(electronRoot, "package.json"), "utf8"),
);
const imageMagick = require("../scripts/prepare-imagemagick.cjs");

function temporaryDirectory(t) {
  const directory = fs.mkdtempSync(path.join(os.tmpdir(), "presenton-supply-chain-"));
  t.after(() => fs.rmSync(directory, { recursive: true, force: true }));
  return directory;
}

function writeManifest(directory, manifest) {
  fs.writeFileSync(
    path.join(directory, imageMagick.MANIFEST_NAME),
    `${JSON.stringify(manifest, null, 2)}\n`,
    "utf8",
  );
}

test("ImageMagick runtime integrity rejects a changed installed tree", (t) => {
  const runtime = temporaryDirectory(t);
  const binary = path.join(runtime, "magick.exe");
  const delegate = path.join(runtime, "delegates.xml");
  fs.writeFileSync(binary, "verified executable", "utf8");
  fs.writeFileSync(delegate, "verified delegates", "utf8");

  const asset = "ImageMagick-7.1.2-18-portable-Q16-x64.7z";
  const sourceSha256 = "a".repeat(64);
  writeManifest(runtime, {
    schemaVersion: 1,
    version: "7.1.2-18",
    platform: "win32",
    arch: "x64",
    kind: "windows-portable",
    binary: "magick.exe",
    asset,
    source: `https://example.invalid/${asset}`,
    sourceSha256,
    binarySha256: imageMagick.sha256File(binary),
    installedTreeSha256: imageMagick.sha256Tree(runtime),
  });

  const options = {
    version: "7.1.2-18",
    platform: "win32",
    arch: "x64",
    expectedBinarySha256: imageMagick.sha256File(binary),
    expectedInstalledTreeSha256: imageMagick.sha256Tree(runtime),
    expectedSha256(name) {
      assert.equal(name, asset);
      return sourceSha256;
    },
  };
  assert.equal(imageMagick.validateRuntimeIntegrity(runtime, options).ok, true);

  fs.writeFileSync(delegate, "tampered delegates", "utf8");
  const changed = imageMagick.validateRuntimeIntegrity(runtime, options);
  assert.equal(changed.ok, false);
  assert.match(changed.reason, /installed-tree SHA-256 validation failed/);

  fs.writeFileSync(binary, "attacker-controlled executable", "utf8");
  const forgedManifest = JSON.parse(
    fs.readFileSync(path.join(runtime, imageMagick.MANIFEST_NAME), "utf8"),
  );
  forgedManifest.binarySha256 = imageMagick.sha256File(binary);
  forgedManifest.installedTreeSha256 = imageMagick.sha256Tree(runtime);
  writeManifest(runtime, forgedManifest);
  const forged = imageMagick.validateRuntimeIntegrity(runtime, options);
  assert.equal(forged.ok, false);
  assert.match(forged.reason, /not bound to the current verified preparation/);
});

test("ImageMagick runtime integrity requires an exact identity and manifest", (t) => {
  const runtime = temporaryDirectory(t);
  assert.match(
    imageMagick.validateRuntimeIntegrity(runtime, {
      version: "7.1.2-18",
      platform: "win32",
      arch: "x64",
    }).reason,
    /manifest is missing or invalid/,
  );

  const binary = path.join(runtime, "magick.exe");
  fs.writeFileSync(binary, "executable", "utf8");
  writeManifest(runtime, {
    schemaVersion: 1,
    version: "7.1.2-17",
    platform: "win32",
    arch: "x64",
    kind: "windows-portable",
    binary: "magick.exe",
    binarySha256: imageMagick.sha256File(binary),
    installedTreeSha256: imageMagick.sha256Tree(runtime),
  });
  assert.match(
    imageMagick.validateRuntimeIntegrity(runtime, {
      version: "7.1.2-18",
      platform: "win32",
      arch: "x64",
    }).reason,
    /Runtime identity mismatch/,
  );
});

test("macOS ImageMagick integrity requires the explicit source-tree digest", (t) => {
  const runtime = temporaryDirectory(t);
  const binDirectory = path.join(runtime, "bin");
  fs.mkdirSync(binDirectory);
  const binary = path.join(binDirectory, "magick");
  fs.writeFileSync(binary, "mach-o placeholder", "utf8");
  const sourceTreeSha256 = "b".repeat(64);
  writeManifest(runtime, {
    schemaVersion: 1,
    version: "7.1.2-18",
    platform: "darwin",
    arch: "arm64",
    kind: "macos-vendored",
    binary: "bin/magick",
    source: "explicit-vendor-tree",
    sourceTreeSha256,
    binarySha256: imageMagick.sha256File(binary),
    installedTreeSha256: imageMagick.sha256Tree(runtime),
  });

  const valid = imageMagick.validateRuntimeIntegrity(runtime, {
    version: "7.1.2-18",
    platform: "darwin",
    arch: "arm64",
    macSourceTreeSha256: sourceTreeSha256,
    expectedBinarySha256: imageMagick.sha256File(binary),
    expectedInstalledTreeSha256: imageMagick.sha256Tree(runtime),
  });
  assert.equal(valid.ok, true);

  const mismatch = imageMagick.validateRuntimeIntegrity(runtime, {
    version: "7.1.2-18",
    platform: "darwin",
    arch: "arm64",
    macSourceTreeSha256: "c".repeat(64),
    expectedBinarySha256: imageMagick.sha256File(binary),
    expectedInstalledTreeSha256: imageMagick.sha256Tree(runtime),
  });
  assert.equal(mismatch.ok, false);
  assert.match(mismatch.reason, /does not match the explicit policy digest/);
});

test("every distribution entrypoint uses the common secure preparation path", () => {
  const distributionScripts = Object.entries(packageJson.scripts)
    .filter(([name]) => name === "dist" || name.startsWith("dist:"));
  assert.ok(distributionScripts.length > 0);
  for (const [name, command] of distributionScripts) {
    assert.match(command, /^npm run prepare:package && /, name);
  }

  const preparation = packageJson.scripts["prepare:package"];
  for (const requiredStep of [
    "build:export-runtime",
    "prepare:export-chromium",
    "prepare:imagemagick",
    "typecheck",
    "build:ts",
    "check:main-no-undef",
  ]) {
    assert.match(preparation, new RegExp(`npm run ${requiredStep.replace(":", "\\:")}`));
  }
});

test("mutable model and PyInstaller acquisition commands are absent", () => {
  const spacyScript = fs.readFileSync(
    path.join(electronRoot, "scripts", "ensure-spacy-model.cjs"),
    "utf8",
  );
  assert.doesNotMatch(spacyScript, /["']download["']\s*,\s*requiredModel/);
  assert.doesNotMatch(spacyScript, /spacy["']?\s*,\s*["']download/);
  assert.match(spacyScript, /artifact-integrity\.json/);
  assert.match(spacyScript, /spaCy model SHA-256 mismatch/);
  assert.match(spacyScript, /"--no-deps"/);

  const fastapiBuild = packageJson.scripts["build:fastapi"];
  assert.match(fastapiBuild, /uv run --locked --with pyinstaller==6\.16\.0/);
  assert.doesNotMatch(fastapiBuild, /--with pyinstaller(?:\s|$)/);
});

test("mutable macOS package-manager acquisition is absent", () => {
  const source = fs.readFileSync(
    path.join(electronRoot, "scripts", "prepare-imagemagick.cjs"),
    "utf8",
  );
  assert.doesNotMatch(source, /brew["']?\s*,\s*["']install/);
  assert.doesNotMatch(source, /spawnSync\([^\n]+["']install["']/);
  assert.doesNotMatch(source, /validateRuntime\(TARGET_DIR/);
  assert.match(source, /IMAGEMAGICK_MAC_SOURCE_TREE_SHA256/);
  assert.match(source, /PREPARED_RUNTIME_TOKEN/);
  assert.match(source, /macOS runtime safe-disabled/);
});

test("Chromium preparation removes stale artifacts when unverified acquisition is disabled", () => {
  const source = fs.readFileSync(
    path.join(electronRoot, "scripts", "prepare-export-chromium.cjs"),
    "utf8",
  );
  assert.match(source, /if \(!allowUnverifiedDownload\)/);
  assert.match(source, /fs\.rmSync\(cacheDir, \{ recursive: true, force: true \}\)/);
  assert.match(source, /Bundling disabled: no source archive SHA-256 is pinned/);
});
