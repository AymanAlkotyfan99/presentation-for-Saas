/**
 * Download presenton-export release into repo-root `presentation-export/`.
 * Same release host as Electron (`electron/scripts/sync-export-runtime.cjs`); Docker uses this at build time.
 *
 * Version resolution defaults to package.json → presentationExportVersion.
 * EXPORT_RUNTIME_VERSION is only honored with --allow-version-override so build
 * environments cannot accidentally replace the pinned runtime.
 *
 * CLI: --force  re-download even if valid runtime already exists
 *       --check-only  verify index.cjs + converter exist and exit 0/1
 *
 * `--check-only` is strictly read-only. Layout normalization and CommonJS alias
 * creation happen only during installation.
 */
const fs = require("fs");
const path = require("path");
const https = require("https");
const crypto = require("crypto");
const { execFileSync } = require("child_process");

const repoRoot = path.join(__dirname, "..");
const targetRoot = path.join(repoRoot, "presentation-export");
const targetPyDir = path.join(targetRoot, "py");
const targetIndexJs = path.join(targetRoot, "index.js");
const targetIndexCjs = path.join(targetRoot, "index.cjs");
const versionManifestPath = path.join(
  targetRoot,
  "presenton-export-version.json"
);
const packageJsonFile = path.join(repoRoot, "package.json");
const artifactIntegrityFile = path.join(
  repoRoot,
  "config",
  "artifact-integrity.json"
);
const cacheDir = path.join(repoRoot, ".cache", "presentation-export");
const exportRepoBase =
  "https://github.com/presenton/presenton-export/releases/download";

const cliArgs = new Set(process.argv.slice(2));
const forceDownload = cliArgs.has("--force");
const checkOnly = cliArgs.has("--check-only");
const allowVersionOverride = cliArgs.has("--allow-version-override");

function resolveLinuxAssetName() {
  const arch = (
    process.env.EXPORT_RUNTIME_ARCH ||
    process.env.TARGETARCH ||
    process.arch
  ).toLowerCase();

  if (arch === "amd64" || arch === "x64") {
    return "export-Linux-X64.zip";
  }
  if (arch === "arm64" || arch === "aarch64") {
    return "export-Linux-ARM64.zip";
  }

  throw new Error(`Unsupported Linux export arch: ${arch}`);
}

const linuxAssetName = resolveLinuxAssetName();

function readArtifactPolicy(version, assetName) {
  if (!fs.existsSync(artifactIntegrityFile)) {
    throw new Error("Missing config/artifact-integrity.json; refusing unverified export download.");
  }
  const policy = JSON.parse(fs.readFileSync(artifactIntegrityFile, "utf8"));
  if (policy.presentationExport?.version !== version) {
    throw new Error(
      `No integrity policy for presentation export ${version}. Update config/artifact-integrity.json first.`
    );
  }
  const sha256 = policy.presentationExport.assets?.[assetName];
  if (!/^[a-f0-9]{64}$/.test(sha256 || "")) {
    throw new Error(`No valid SHA-256 is pinned for ${assetName}; refusing download.`);
  }
  return { sha256 };
}

function sha256File(filePath) {
  const hash = crypto.createHash("sha256");
  hash.update(fs.readFileSync(filePath));
  return hash.digest("hex");
}

function verifySha256(filePath, expectedSha256) {
  const actual = sha256File(filePath);
  if (actual !== expectedSha256) {
    try {
      fs.rmSync(filePath, { force: true });
    } catch {
      // Best effort only; the mismatch still fails closed.
    }
    throw new Error(
      `SHA-256 mismatch for ${path.basename(filePath)}. Expected ${expectedSha256}; got ${actual}.`
    );
  }
}

function ensureDir(dirPath) {
  fs.mkdirSync(dirPath, { recursive: true });
}

function readPinnedVersion() {
  if (!fs.existsSync(packageJsonFile)) {
    throw new Error(
      `Missing ${path.relative(repoRoot, packageJsonFile)}. Add \"presentationExportVersion\": \"vX.Y.Z\".`
    );
  }
  const raw = JSON.parse(fs.readFileSync(packageJsonFile, "utf8"));
  const v = (raw.presentationExportVersion || "").trim();
  if (!v) {
    throw new Error(
      `${path.relative(repoRoot, packageJsonFile)} must set \"presentationExportVersion\" (e.g. \"v0.2.0\").`
    );
  }
  return v;
}

async function getTargetVersion() {
  const fromEnv = (process.env.EXPORT_RUNTIME_VERSION || "").trim();
  if (allowVersionOverride && fromEnv) {
    return fromEnv === "latest" ? await resolveLatestTag() : fromEnv;
  }
  const pinned = readPinnedVersion();
  if (pinned === "latest") {
    return await resolveLatestTag();
  }
  return pinned;
}

function readInstalledVersion() {
  if (!fs.existsSync(versionManifestPath)) {
    return {
      ok: false,
      reason: `Missing export version manifest: ${versionManifestPath}`,
    };
  }

  try {
    const manifest = JSON.parse(fs.readFileSync(versionManifestPath, "utf8"));
    return { ok: true, manifest };
  } catch (err) {
    return {
      ok: false,
      reason: `Invalid export version manifest ${versionManifestPath}: ${err.message}`,
    };
  }
}

function writeInstalledVersion(version, sourceSha256, entrypointPath, converterPath) {
  fs.writeFileSync(
    versionManifestPath,
    `${JSON.stringify({
      version,
      asset: linuxAssetName,
      sourceSha256,
      files: {
        entrypoint: {
          path: path.relative(targetRoot, entrypointPath),
          sha256: sha256File(entrypointPath),
        },
        converter: {
          path: path.relative(targetRoot, converterPath),
          sha256: sha256File(converterPath),
        },
      },
    }, null, 2)}\n`,
    "utf8"
  );
}

function requestJson(url, redirects = 5) {
  return new Promise((resolve, reject) => {
    if (!url.startsWith("https:")) {
      reject(new Error(`Refusing non-HTTPS JSON request: ${url}`));
      return;
    }
    const req = https.get(
      url,
      {
        headers: {
          "User-Agent": "presenton-presentation-export-sync",
          Accept: "application/vnd.github+json",
        },
      },
      (res) => {
        if ([301, 302, 303, 307, 308].includes(res.statusCode) && res.headers.location) {
          if (redirects <= 0) {
            reject(new Error(`Too many redirects for JSON request: ${url}`));
            return;
          }
          requestJson(res.headers.location, redirects - 1).then(resolve).catch(reject);
          return;
        }
        if (res.statusCode < 200 || res.statusCode >= 300) {
          reject(new Error(`Failed to fetch ${url}. HTTP ${res.statusCode}`));
          return;
        }
        let payload = "";
        res.setEncoding("utf8");
        res.on("data", (chunk) => {
          payload += chunk;
        });
        res.on("end", () => {
          try {
            resolve(JSON.parse(payload));
          } catch (e) {
            reject(new Error(`Invalid JSON from ${url}: ${e.message}`));
          }
        });
      }
    );
    req.on("error", reject);
  });
}

async function resolveLatestTag() {
  const apiUrl =
    "https://api.github.com/repos/presenton/presenton-export/releases/latest";
  const latest = await requestJson(apiUrl);
  if (!latest.tag_name) {
    throw new Error(`Could not resolve latest tag from ${apiUrl}`);
  }
  return latest.tag_name;
}

function chmodIfPossible(filePath) {
  if (process.platform !== "win32") {
    fs.chmodSync(filePath, 0o755);
  }
}

function ensureCurrentConverterLink(converterPath) {
  const currentPath = path.join(targetPyDir, "convert-linux-current");
  fs.rmSync(currentPath, { force: true });

  if (process.platform === "win32") {
    fs.copyFileSync(converterPath, currentPath);
    return currentPath;
  }

  fs.symlinkSync(path.basename(converterPath), currentPath);
  return currentPath;
}

function getConverterCandidates(baseDir = targetPyDir) {
  if (linuxAssetName === "export-Linux-ARM64.zip") {
    return [
      path.join(baseDir, "convert-linux-arm64"),
      path.join(baseDir, "convert"),
    ];
  }

  return [
    path.join(baseDir, "convert-linux-x64"),
    path.join(baseDir, "convert-linux-amd64"),
    path.join(baseDir, "convert"),
  ];
}

function hasRuntimeBundle(baseDir) {
  const indexPath = path.join(baseDir, "index.js");
  if (!fs.existsSync(indexPath)) {
    return false;
  }

  const pyCandidates = getConverterCandidates(path.join(baseDir, "py"));
  const rootCandidates = getConverterCandidates(baseDir);
  return [...pyCandidates, ...rootCandidates].some((candidate) =>
    fs.existsSync(candidate)
  );
}

function moveFileAtomic(src, dest) {
  try {
    fs.renameSync(src, dest);
  } catch {
    fs.copyFileSync(src, dest);
    fs.rmSync(src, { force: true });
  }
}

function normalizeRuntimeLayout() {
  if (!fs.existsSync(targetRoot)) {
    return;
  }

  ensureDir(targetPyDir);

  const rootCandidates = getConverterCandidates(targetRoot);
  for (const sourcePath of rootCandidates) {
    if (!fs.existsSync(sourcePath)) {
      continue;
    }

    const destinationPath = path.join(targetPyDir, path.basename(sourcePath));
    if (!fs.existsSync(destinationPath)) {
      moveFileAtomic(sourcePath, destinationPath);
    }
  }
}

function ensureCommonJsEntrypoint(create = false) {
  if (!fs.existsSync(targetIndexJs)) {
    return { ok: false, reason: `Missing runtime bundle: ${targetIndexJs}` };
  }

  try {
    if (create) {
      fs.copyFileSync(targetIndexJs, targetIndexCjs);
    } else if (!fs.existsSync(targetIndexCjs)) {
      return { ok: false, reason: `Missing CommonJS runtime bundle: ${targetIndexCjs}` };
    }
    return { ok: true, entrypointPath: targetIndexCjs };
  } catch (err) {
    return {
      ok: false,
      reason: `Failed to create CommonJS entrypoint ${targetIndexCjs}: ${err.message}`,
    };
  }
}

function validateExistingRuntime(expectedVersion, expectedSha256) {
  const installedVersion = readInstalledVersion();
  if (!installedVersion.ok) {
    return installedVersion;
  }
  if (
    installedVersion.manifest.version !== expectedVersion ||
    installedVersion.manifest.asset !== linuxAssetName
  ) {
    return {
      ok: false,
      reason: [
        "Installed export runtime does not match package.json.",
        `Expected: ${expectedVersion} (${linuxAssetName})`,
        `Installed: ${installedVersion.manifest.version || "unknown"} (${installedVersion.manifest.asset || "unknown"})`,
      ].join("\n"),
    };
  }
  if (installedVersion.manifest.sourceSha256 !== expectedSha256) {
    return {
      ok: false,
      reason: "Installed export runtime was not created from the currently pinned SHA-256 artifact.",
    };
  }

  const entrypoint = ensureCommonJsEntrypoint(false);
  if (!entrypoint.ok) {
    return { ok: false, reason: entrypoint.reason };
  }

  const candidates = getConverterCandidates();
  const converterPath = candidates.find((c) => fs.existsSync(c));
  if (!converterPath) {
    return {
      ok: false,
      reason: `No Linux converter binary under ${targetPyDir} or ${targetRoot}.`,
    };
  }
  const currentConverterPath = path.join(targetPyDir, "convert-linux-current");
  if (!fs.existsSync(currentConverterPath)) {
    return {
      ok: false,
      reason: `Missing verified converter alias: ${currentConverterPath}`,
    };
  }

  const installedFiles = installedVersion.manifest.files || {};
  const expectedEntrypointHash = installedFiles.entrypoint?.sha256;
  const expectedConverterHash = installedFiles.converter?.sha256;
  if (
    !/^[a-f0-9]{64}$/.test(expectedEntrypointHash || "") ||
    !/^[a-f0-9]{64}$/.test(expectedConverterHash || "") ||
    sha256File(entrypoint.entrypointPath) !== expectedEntrypointHash ||
    sha256File(converterPath) !== expectedConverterHash ||
    sha256File(currentConverterPath) !== expectedConverterHash
  ) {
    return {
      ok: false,
      reason: "Installed export runtime file-integrity validation failed.",
    };
  }
  return {
    ok: true,
    entrypointPath: entrypoint.entrypointPath,
    converterPath,
    currentConverterPath,
  };
}

function downloadFile(url, outputPath, redirects = 5) {
  return new Promise((resolve, reject) => {
    if (!url.startsWith("https:")) {
      reject(new Error(`Refusing non-HTTPS export download: ${url}`));
      return;
    }
    const req = https.get(
      url,
      {
        headers: {
          "User-Agent": "presenton-presentation-export-sync",
          Accept: "application/octet-stream",
        },
      },
      (res) => {
        if ([301, 302, 303, 307, 308].includes(res.statusCode) && res.headers.location) {
          if (redirects <= 0) {
            reject(new Error(`Too many redirects while downloading ${url}`));
            return;
          }
          downloadFile(res.headers.location, outputPath, redirects - 1)
            .then(resolve)
            .catch(reject);
          return;
        }
        if (res.statusCode < 200 || res.statusCode >= 300) {
          reject(new Error(`Failed to download ${url}. HTTP ${res.statusCode}`));
          return;
        }
        ensureDir(path.dirname(outputPath));
        const fileStream = fs.createWriteStream(outputPath);
        res.pipe(fileStream);
        fileStream.on("finish", () => {
          fileStream.close(resolve);
        });
        fileStream.on("error", reject);
      }
    );
    req.on("error", reject);
  });
}

function unzipArchive(zipPath, destDir) {
  ensureDir(destDir);
  if (process.platform === "win32") {
    execFileSync(
      "powershell.exe",
      [
        "-NoLogo",
        "-NoProfile",
        "-NonInteractive",
        "-Command",
        "Expand-Archive -LiteralPath $env:PRESENTON_EXPORT_ARCHIVE_PATH -DestinationPath $env:PRESENTON_EXPORT_EXTRACT_PATH -Force",
      ],
      {
        env: {
          ...process.env,
          PRESENTON_EXPORT_ARCHIVE_PATH: zipPath,
          PRESENTON_EXPORT_EXTRACT_PATH: destDir,
        },
        stdio: "inherit",
      }
    );
    return;
  }
  execFileSync("unzip", ["-o", zipPath, "-d", destDir], { stdio: "inherit" });
}

function resolveExtractedRoot(extractDir) {
  if (hasRuntimeBundle(extractDir)) {
    return extractDir;
  }

  const children = fs.readdirSync(extractDir, { withFileTypes: true });
  for (const entry of children) {
    if (!entry.isDirectory()) continue;
    const candidate = path.join(extractDir, entry.name);
    if (hasRuntimeBundle(candidate)) {
      return candidate;
    }
  }
  throw new Error(`Unable to locate export runtime root under ${extractDir}`);
}

async function downloadAndInstallRuntime(tag, expectedSha256) {
  const downloadUrl = `${exportRepoBase}/${tag}/${linuxAssetName}`;

  ensureDir(cacheDir);
  const cacheKey = tag.replace(/[^a-zA-Z0-9._-]/g, "_");
  const zipPath = path.join(cacheDir, `${cacheKey}-${linuxAssetName}`);
  const extractDir = path.join(cacheDir, `extract-${Date.now()}`);

  console.log(`[presentation-export] Downloading ${downloadUrl}`);
  await downloadFile(downloadUrl, zipPath);
  verifySha256(zipPath, expectedSha256);

  console.log(`[presentation-export] Extracting ${zipPath}`);
  unzipArchive(zipPath, extractDir);

  const sourceRoot = resolveExtractedRoot(extractDir);
  fs.rmSync(targetRoot, { recursive: true, force: true });
  ensureDir(targetRoot);
  fs.cpSync(sourceRoot, targetRoot, { recursive: true, force: true });

  normalizeRuntimeLayout();
  const entrypoint = ensureCommonJsEntrypoint(true);
  if (!entrypoint.ok) {
    throw new Error(entrypoint.reason);
  }
  const converterPath = getConverterCandidates().find((candidate) =>
    fs.existsSync(candidate)
  );
  if (!converterPath) {
    throw new Error(`Downloaded runtime does not include a converter for ${linuxAssetName}.`);
  }
  chmodIfPossible(converterPath);
  ensureCurrentConverterLink(converterPath);
  writeInstalledVersion(tag, expectedSha256, entrypoint.entrypointPath, converterPath);

  fs.rmSync(extractDir, { recursive: true, force: true });

  return { tag, downloadUrl };
}

async function main() {
  const targetVersion = await getTargetVersion();
  const { sha256: expectedSha256 } = readArtifactPolicy(
    targetVersion,
    linuxAssetName
  );
  const existing = validateExistingRuntime(targetVersion, expectedSha256);

  if (checkOnly) {
    if (!existing.ok) {
      throw new Error(existing.reason);
    }
    console.log("[presentation-export] OK");
    console.log(`  - ${existing.entrypointPath}`);
    console.log(`  - ${existing.converterPath}`);
    console.log(`  - ${existing.currentConverterPath}`);
    console.log(`  - release: ${targetVersion}`);
    return;
  }

  if (existing.ok && !forceDownload) {
    console.log("[presentation-export] Using existing runtime:");
    console.log(`  - ${existing.entrypointPath}`);
    console.log(`  - ${existing.converterPath}`);
    console.log(`  - ${existing.currentConverterPath}`);
    console.log(`  - release: ${targetVersion}`);
    return;
  }

  const { tag, downloadUrl } = await downloadAndInstallRuntime(
    targetVersion,
    expectedSha256
  );
  const installed = validateExistingRuntime(targetVersion, expectedSha256);
  if (!installed.ok) {
    throw new Error(installed.reason);
  }

  console.log("[presentation-export] Synced successfully:");
  console.log(`  - release: ${tag}`);
  console.log(`  - url: ${downloadUrl}`);
  console.log(`  - ${installed.entrypointPath}`);
  console.log(`  - ${installed.converterPath}`);
  console.log(`  - ${installed.currentConverterPath}`);
}

if (require.main === module) {
  main().catch((err) => {
    console.error(`[presentation-export] ${err.message}`);
    process.exit(1);
  });
}

module.exports = { readArtifactPolicy, sha256File, verifySha256 };
