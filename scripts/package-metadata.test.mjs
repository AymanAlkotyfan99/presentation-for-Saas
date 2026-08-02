import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";
import path from "node:path";
import test from "node:test";
import { fileURLToPath } from "node:url";

const repoRoot = path.resolve(
  path.dirname(fileURLToPath(import.meta.url)),
  "..",
);

async function readJson(relativePath) {
  return JSON.parse(await readFile(path.join(repoRoot, relativePath), "utf8"));
}

test("application versions stay aligned", async () => {
  const [rootPackage, rootLock, electronPackage, electronLock, legacyTable] =
    await Promise.all([
      readJson("package.json"),
      readJson("package-lock.json"),
      readJson("electron/package.json"),
      readJson("electron/package-lock.json"),
      readFile(
        path.join(
          repoRoot,
          "servers/nextjs/app/(presentation-generator)/(dashboard)/dashboard/components/LegacyPresentationsTable.tsx",
        ),
        "utf8",
      ),
    ]);

  assert.match(
    rootPackage.version,
    /^\d+\.\d+\.\d+(?:-[0-9A-Za-z.-]+)?$/,
    "package.json is the application-version source of truth and must contain a valid SemVer version",
  );
  assert.equal(electronPackage.version, rootPackage.version);
  assert.equal(rootLock.version, rootPackage.version);
  assert.equal(rootLock.packages[""].version, rootPackage.version);
  assert.equal(electronLock.version, electronPackage.version);
  assert.equal(electronLock.packages[""].version, electronPackage.version);
  assert.match(legacyTable, new RegExp(`Presenton ${rootPackage.version.replaceAll(".", "\\.")}`));
});

test("Docker and Electron use the same pinned presentation export", async () => {
  const [rootPackage, electronPackage, dockerfile, dockerfileDev] =
    await Promise.all([
      readJson("package.json"),
      readJson("electron/package.json"),
      readFile(path.join(repoRoot, "Dockerfile"), "utf8"),
      readFile(path.join(repoRoot, "Dockerfile.dev"), "utf8"),
    ]);

  assert.equal(
    electronPackage.exportVersion,
    rootPackage.presentationExportVersion,
  );
  assert.match(dockerfile, /COPY package\.json package-lock\.json \/app\//);
  assert.match(
    dockerfile,
    /sync-presentation-export\.cjs --force/,
  );
  assert.match(dockerfileDev, /COPY package\.json package-lock\.json \/app\//);
  assert.match(
    dockerfileDev,
    /sync-presentation-export\.cjs --force/,
  );
});

test("artifact policy pins every presentation-export archive", async () => {
  const [rootPackage, electronPackage, integrity] = await Promise.all([
    readJson("package.json"),
    readJson("electron/package.json"),
    readJson("config/artifact-integrity.json"),
  ]);

  assert.equal(integrity.schemaVersion, 1);
  assert.equal(
    integrity.presentationExport.version,
    rootPackage.presentationExportVersion,
  );
  assert.equal(electronPackage.exportVersion, integrity.presentationExport.version);
  assert.notEqual(integrity.presentationExport.version, "latest");

  const requiredAssets = [
    "export-Linux-ARM64.zip",
    "export-Linux-X64.zip",
    "export-macOS-ARM64.zip",
    "export-macOS-X64.zip",
    "export-Windows-X64.zip",
  ];
  for (const asset of requiredAssets) {
    assert.match(
      integrity.presentationExport.assets[asset] ?? "",
      /^[a-f0-9]{64}$/,
      `${asset} must have a pinned SHA-256 digest`,
    );
  }
});
