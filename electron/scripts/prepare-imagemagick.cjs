#!/usr/bin/env node
const fs = require("fs");
const https = require("https");
const os = require("os");
const path = require("path");
const crypto = require("crypto");
const { spawnSync } = require("child_process");
const { path7za } = require("7zip-bin");

const VERSION = process.env.IMAGEMAGICK_VERSION || "7.1.2-18";
const PLATFORM = process.platform;
const ARCH = process.arch;
const TARGET_DIR = path.join(__dirname, "..", "resources", "imagemagick", `${PLATFORM}-${ARCH}`);
const CACHE_DIR = path.join(__dirname, "..", ".cache", "imagemagick", VERSION);
const MANIFEST_NAME = "presenton-runtime.json";
const MANIFEST_SCHEMA_VERSION = 1;
const PREPARED_RUNTIME_TOKEN = Symbol("prepared-runtime-token");
const EXPORT_ENABLED =
  process.env.ENABLE_UNVERIFIED_PRESENTATION_EXPORT === "true";
const MAC_SOURCE_TREE_SHA256 =
  process.env.IMAGEMAGICK_MAC_SOURCE_TREE_SHA256?.trim().toLowerCase() || "";
const INTEGRITY_FILE = path.join(
  __dirname,
  "..",
  "..",
  "config",
  "artifact-integrity.json",
);

function sha256File(filePath) {
  const hash = crypto.createHash("sha256");
  hash.update(fs.readFileSync(filePath));
  return hash.digest("hex");
}

function isSha256(value) {
  return /^[a-f0-9]{64}$/.test(value || "");
}

function readImageMagickPolicy() {
  if (!fs.existsSync(INTEGRITY_FILE)) {
    throw new Error("Missing config/artifact-integrity.json; refusing unverified ImageMagick download.");
  }
  const policy = JSON.parse(fs.readFileSync(INTEGRITY_FILE, "utf8"));
  if (policy.imageMagick?.version !== VERSION) {
    throw new Error(`No integrity policy is pinned for ImageMagick ${VERSION}.`);
  }
  if (!policy.imageMagick.assets || typeof policy.imageMagick.assets !== "object") {
    throw new Error(`ImageMagick ${VERSION} integrity policy has no asset map.`);
  }
  return policy.imageMagick;
}

function expectedSha256(assetName) {
  const digest = readImageMagickPolicy().assets[assetName];
  if (!isSha256(digest)) {
    throw new Error(`No SHA-256 is pinned for ImageMagick asset ${assetName}.`);
  }
  return digest;
}

function sha256Tree(rootDir, options = {}) {
  const excludeManifest = options.excludeManifest !== false;
  const resolvedRoot = path.resolve(rootDir);
  if (!fs.existsSync(resolvedRoot)) {
    throw new Error(`Cannot hash missing runtime directory: ${resolvedRoot}`);
  }
  const rootStat = fs.lstatSync(resolvedRoot);
  if (rootStat.isSymbolicLink() || !rootStat.isDirectory()) {
    throw new Error(`Runtime tree root must be a real directory: ${resolvedRoot}`);
  }

  const hash = crypto.createHash("sha256");
  const walk = (currentDir, relativeDir = "") => {
    const entries = fs
      .readdirSync(currentDir, { withFileTypes: true })
      .sort((left, right) => left.name.localeCompare(right.name, "en"));

    for (const entry of entries) {
      const relativePath = relativeDir
        ? `${relativeDir}/${entry.name}`
        : entry.name;
      if (excludeManifest && relativePath === MANIFEST_NAME) {
        continue;
      }

      const fullPath = path.join(currentDir, entry.name);
      const stat = fs.lstatSync(fullPath);
      if (stat.isSymbolicLink()) {
        throw new Error(`Runtime tree contains a symbolic link: ${relativePath}`);
      }
      if (stat.isDirectory()) {
        hash.update(`directory\0${relativePath}\0`);
        walk(fullPath, relativePath);
        continue;
      }
      if (!stat.isFile()) {
        throw new Error(`Runtime tree contains an unsupported entry: ${relativePath}`);
      }
      hash.update(`file\0${relativePath}\0${sha256File(fullPath)}\0`);
    }
  };

  walk(resolvedRoot);
  return hash.digest("hex");
}

function verifyArtifact(filePath, expected) {
  const actual = sha256File(filePath);
  if (actual !== expected) {
    fs.rmSync(filePath, { force: true });
    throw new Error(
      `SHA-256 mismatch for ${path.basename(filePath)}. Expected ${expected}; got ${actual}.`,
    );
  }
}

function log(message) {
  console.log(`[imagemagick] ${message}`);
}

function fail(message) {
  console.error(`[imagemagick] ${message}`);
  process.exit(1);
}

function run(command, args, options = {}) {
  const result = spawnSync(command, args, {
    stdio: "inherit",
    windowsHide: true,
    ...options,
  });
  if (result.status !== 0) {
    throw new Error(`${command} ${args.join(" ")} failed with code ${result.status}`);
  }
  return result;
}

function capture(command, args, options = {}) {
  return spawnSync(command, args, {
    stdio: ["ignore", "pipe", "pipe"],
    encoding: "utf8",
    windowsHide: true,
    ...options,
  });
}

function runtimeEnv(binaryPath) {
  const homeDir = fs.statSync(binaryPath).isFile()
    ? path.dirname(binaryPath)
    : binaryPath;
  const tempDir = process.env.TEMP || process.env.TMPDIR || os.tmpdir() || homeDir;
  return {
    ...process.env,
    MAGICK_HOME: path.basename(homeDir).toLowerCase() === "bin"
      ? path.dirname(homeDir)
      : homeDir,
    MAGICK_CONFIGURE_PATH: path.basename(homeDir).toLowerCase() === "bin"
      ? path.dirname(homeDir)
      : homeDir,
    MAGICK_TEMPORARY_PATH: tempDir,
    MAGICK_OCL_DEVICE: "OFF",
    APPIMAGE_EXTRACT_AND_RUN: "1",
  };
}

function versionOutput(binaryPath) {
  const result = spawnSync(binaryPath, ["-version"], {
    stdio: ["ignore", "pipe", "pipe"],
    encoding: "utf8",
    timeout: 120000,
    env: runtimeEnv(binaryPath),
    windowsHide: true,
  });
  if (result.status !== 0 || result.signal) {
    const reason = result.error?.message
      || (result.stderr || "").trim()
      || (result.signal ? `terminated by signal ${result.signal}` : `exit ${result.status}`);
    return { ok: false, reason };
  }
  const output = `${result.stdout || ""}\n${result.stderr || ""}`.trim();
  const escapedVersion = VERSION.replace(/[.*+?^${}()|[\]\\]/g, "\\$&");
  const exactVersion = new RegExp(`\\bImageMagick\\s+${escapedVersion}(?:\\s|$)`, "i");
  return {
    ok: exactVersion.test(output),
    output,
    reason: exactVersion.test(output)
      ? undefined
      : `expected ImageMagick ${VERSION}, but the version probe returned: ${output || "no output"}`,
  };
}

function readManifest(targetDir) {
  const manifestPath = path.join(targetDir, MANIFEST_NAME);
  if (!fs.existsSync(manifestPath)) {
    return null;
  }
  try {
    return JSON.parse(fs.readFileSync(manifestPath, "utf8"));
  } catch {
    return null;
  }
}

function writeManifest(targetDir, manifest) {
  const manifestPath = path.join(targetDir, MANIFEST_NAME);
  fs.rmSync(manifestPath, { force: true });
  const binaryPath = resolveRuntimePath(targetDir, manifest.binary);
  if (!fs.existsSync(binaryPath) || !fs.statSync(binaryPath).isFile()) {
    throw new Error(`Cannot finalize ImageMagick manifest; missing binary ${manifest.binary}.`);
  }
  const completeManifest = {
    ...manifest,
    schemaVersion: MANIFEST_SCHEMA_VERSION,
    version: VERSION,
    platform: PLATFORM,
    arch: ARCH,
    createdAt: new Date().toISOString(),
    binarySha256: sha256File(binaryPath),
    installedTreeSha256: sha256Tree(targetDir),
  };
  fs.writeFileSync(
    manifestPath,
    `${JSON.stringify(completeManifest, null, 2)}\n`,
    "utf8",
  );
  return Object.freeze({
    token: PREPARED_RUNTIME_TOKEN,
    binarySha256: completeManifest.binarySha256,
    installedTreeSha256: completeManifest.installedTreeSha256,
  });
}

function resolveRuntimePath(targetDir, relativePath) {
  if (
    typeof relativePath !== "string" ||
    !relativePath ||
    path.isAbsolute(relativePath)
  ) {
    throw new Error("Runtime manifest contains an invalid relative path.");
  }
  const resolvedRoot = path.resolve(targetDir);
  const resolvedPath = path.resolve(resolvedRoot, relativePath);
  if (!resolvedPath.startsWith(`${resolvedRoot}${path.sep}`)) {
    throw new Error(`Runtime manifest path escapes its root: ${relativePath}`);
  }
  return resolvedPath;
}

function expectedRuntimeLayout(platform) {
  if (platform === "win32") {
    return { kind: "windows-portable", binary: "magick.exe" };
  }
  if (platform === "linux") {
    return { kind: "linux-appimage", binary: "bin/magick" };
  }
  if (platform === "darwin") {
    return { kind: "macos-vendored", binary: "bin/magick" };
  }
  throw new Error(`Unsupported platform for bundled ImageMagick: ${platform}`);
}

function validateRuntimeIntegrity(targetDir, options = {}) {
  try {
    const platform = options.platform || PLATFORM;
    const arch = options.arch || ARCH;
    const version = options.version || VERSION;
    const sourceDigestResolver = options.expectedSha256 || expectedSha256;
    const expectedBinarySha256 = options.expectedBinarySha256;
    const expectedInstalledTreeSha256 = options.expectedInstalledTreeSha256;
    const macSourceTreeSha256 =
      options.macSourceTreeSha256 === undefined
        ? MAC_SOURCE_TREE_SHA256
        : options.macSourceTreeSha256;
    const manifest = readManifest(targetDir);
    if (!manifest || typeof manifest !== "object" || Array.isArray(manifest)) {
      throw new Error("ImageMagick runtime manifest is missing or invalid.");
    }
    if (manifest.schemaVersion !== MANIFEST_SCHEMA_VERSION) {
      throw new Error(`Unsupported ImageMagick runtime manifest schema: ${manifest.schemaVersion}.`);
    }
    if (
      manifest.version !== version ||
      manifest.platform !== platform ||
      manifest.arch !== arch
    ) {
      throw new Error(
        `Runtime identity mismatch; expected ImageMagick ${version} for ${platform}-${arch}.`,
      );
    }

    const layout = expectedRuntimeLayout(platform);
    if (manifest.kind !== layout.kind || manifest.binary !== layout.binary) {
      throw new Error(`Runtime layout does not match ${platform}-${arch}.`);
    }

    const binaryPath = resolveRuntimePath(targetDir, manifest.binary);
    if (!fs.existsSync(binaryPath) || !fs.statSync(binaryPath).isFile()) {
      throw new Error(`Runtime binary is missing: ${manifest.binary}`);
    }
    if (
      !isSha256(expectedBinarySha256) ||
      manifest.binarySha256 !== expectedBinarySha256
    ) {
      throw new Error("Runtime binary SHA-256 is not bound to the current verified preparation.");
    }
    if (sha256File(binaryPath) !== expectedBinarySha256) {
      throw new Error("Runtime binary SHA-256 validation failed.");
    }

    if (
      !isSha256(expectedInstalledTreeSha256) ||
      manifest.installedTreeSha256 !== expectedInstalledTreeSha256
    ) {
      throw new Error("Runtime tree SHA-256 is not bound to the current verified preparation.");
    }
    if (sha256Tree(targetDir) !== expectedInstalledTreeSha256) {
      throw new Error("Runtime installed-tree SHA-256 validation failed.");
    }

    if (platform === "darwin") {
      if (manifest.source !== "explicit-vendor-tree") {
        throw new Error("macOS runtime manifest does not identify an explicit vendor tree.");
      }
      if (!isSha256(macSourceTreeSha256)) {
        throw new Error(
          "IMAGEMAGICK_MAC_SOURCE_TREE_SHA256 is required to validate a macOS runtime.",
        );
      }
      if (manifest.sourceTreeSha256 !== macSourceTreeSha256) {
        throw new Error("macOS runtime source-tree SHA-256 does not match the explicit policy digest.");
      }
    } else {
      if (typeof manifest.asset !== "string" || !manifest.asset) {
        throw new Error("Runtime manifest does not identify its pinned source asset.");
      }
      if (
        platform === "win32" &&
        manifest.asset !== windowsArchiveName(platform, arch, version)
      ) {
        throw new Error(`Windows runtime source asset does not match ${platform}-${arch}.`);
      }
      if (
        platform === "linux" &&
        (arch !== "x64" || !manifest.asset.endsWith("-x86_64.AppImage"))
      ) {
        throw new Error(`Linux runtime source asset does not match ${platform}-${arch}.`);
      }
      const expectedSourceSha256 = sourceDigestResolver(manifest.asset);
      if (manifest.sourceSha256 !== expectedSourceSha256) {
        throw new Error("Runtime source SHA-256 does not match artifact-integrity policy.");
      }
      if (typeof manifest.source !== "string" || !manifest.source.startsWith("https://")) {
        throw new Error("Runtime manifest source must be HTTPS.");
      }
      if (platform === "linux") {
        if (manifest.appImage !== manifest.asset) {
          throw new Error("Linux runtime AppImage does not match its pinned source asset.");
        }
        const appImagePath = resolveRuntimePath(targetDir, manifest.appImage);
        if (!fs.existsSync(appImagePath) || !fs.statSync(appImagePath).isFile()) {
          throw new Error(`Linux runtime AppImage is missing: ${manifest.appImage}`);
        }
        if (sha256File(appImagePath) !== expectedSourceSha256) {
          throw new Error("Linux runtime AppImage SHA-256 does not match artifact-integrity policy.");
        }
      }
    }

    return { ok: true, binaryPath, manifest };
  } catch (error) {
    return { ok: false, reason: error?.message || String(error) };
  }
}

function validateRuntime(targetDir, preparationProof) {
  if (preparationProof?.token !== PREPARED_RUNTIME_TOKEN) {
    log("Refusing to execute an ImageMagick runtime not derived during this verified preparation.");
    return null;
  }
  const integrity = validateRuntimeIntegrity(targetDir, {
    expectedBinarySha256: preparationProof.binarySha256,
    expectedInstalledTreeSha256: preparationProof.installedTreeSha256,
  });
  if (!integrity.ok) {
    if (fs.existsSync(targetDir)) {
      log(`Runtime integrity validation failed for ${targetDir}: ${integrity.reason}`);
    }
    return null;
  }
  const { binaryPath } = integrity;
  if (PLATFORM !== "win32") {
    try {
      fs.chmodSync(binaryPath, 0o755);
    } catch {
      return null;
    }
  }
  const result = versionOutput(binaryPath);
  if (!result.ok) {
    log(`Runtime version validation failed for ${binaryPath}: ${result.reason}`);
    return null;
  }
  return { binaryPath, output: result.output };
}

function windowsArchiveName(platform = PLATFORM, arch = ARCH, version = VERSION) {
  if (platform !== "win32") {
    return null;
  }
  const archName = arch === "x64" ? "x64" : arch === "arm64" ? "arm64" : arch === "ia32" ? "x86" : null;
  if (!archName) {
    throw new Error(`No bundled ImageMagick Windows asset configured for ${platform}-${arch}`);
  }
  return `ImageMagick-${version}-portable-Q16-${archName}.7z`;
}

function archiveName() {
  return windowsArchiveName();
}

function linuxAppImageArch() {
  if (PLATFORM !== "linux") {
    return null;
  }
  if (ARCH !== "x64") {
    fail(`No bundled ImageMagick Linux AppImage asset configured for ${PLATFORM}-${ARCH}`);
  }
  return "x86_64";
}

function linuxDefaultAppImageName() {
  return `ImageMagick-${VERSION}-gcc-${linuxAppImageArch()}.AppImage`;
}

function parseAssetNameFromUrl(urlValue) {
  try {
    const pathname = new URL(urlValue).pathname;
    const name = pathname.split("/").filter(Boolean).pop();
    return name || null;
  } catch {
    return null;
  }
}

function downloadUrl(assetName) {
  if (process.env.IMAGEMAGICK_DOWNLOAD_URL) {
    return process.env.IMAGEMAGICK_DOWNLOAD_URL;
  }
  return `https://github.com/ImageMagick/ImageMagick/releases/download/${VERSION}/${assetName}`;
}

function downloadFile(url, destination, redirects = 5) {
  return new Promise((resolve, reject) => {
    if (!url.startsWith("https:")) {
      reject(new Error(`Refusing non-HTTPS ImageMagick download: ${url}`));
      return;
    }
    const request = https.get(
      url,
      { headers: { "User-Agent": "Presenton ImageMagick runtime fetcher" } },
      (response) => {
        if ([301, 302, 303, 307, 308].includes(response.statusCode || 0)) {
          if (redirects <= 0) {
            reject(new Error(`Too many redirects while downloading ${url}`));
            return;
          }
          const location = response.headers.location;
          if (!location) {
            reject(new Error(`Redirect from ${url} did not include Location`));
            return;
          }
          response.resume();
          downloadFile(new URL(location, url).toString(), destination, redirects - 1).then(resolve, reject);
          return;
        }
        if (response.statusCode !== 200) {
          reject(new Error(`Download failed with HTTP ${response.statusCode}: ${url}`));
          response.resume();
          return;
        }
        fs.mkdirSync(path.dirname(destination), { recursive: true });
        const temporaryPath = `${destination}.part-${process.pid}`;
        fs.rmSync(temporaryPath, { force: true });
        const file = fs.createWriteStream(temporaryPath, { flags: "wx", mode: 0o600 });
        response.pipe(file);
        file.on("finish", () => {
          file.close(() => {
            try {
              fs.rmSync(destination, { force: true });
              fs.renameSync(temporaryPath, destination);
              resolve();
            } catch (error) {
              fs.rmSync(temporaryPath, { force: true });
              reject(error);
            }
          });
        });
        file.on("error", (error) => {
          fs.rmSync(temporaryPath, { force: true });
          reject(error);
        });
        response.on("error", (error) => {
          file.destroy();
          fs.rmSync(temporaryPath, { force: true });
          reject(error);
        });
      },
    );
    request.setTimeout(120000, () => request.destroy(new Error(`Download timed out: ${url}`)));
    request.on("error", reject);
  });
}

function uniqueNonEmpty(values) {
  return values.filter(Boolean).filter((value, index, all) => all.indexOf(value) === index);
}

async function linuxAppImageCandidates() {
  const configuredAsset = process.env.IMAGEMAGICK_LINUX_ASSET_NAME?.trim();
  if (configuredAsset) {
    return [configuredAsset];
  }

  const arch = linuxAppImageArch();
  const downloadOverride = process.env.IMAGEMAGICK_DOWNLOAD_URL?.trim();
  if (downloadOverride) {
    return [parseAssetNameFromUrl(downloadOverride) || linuxDefaultAppImageName()];
  }

  const fallbackName = linuxDefaultAppImageName();
  const pinnedAssets = Object.keys(readImageMagickPolicy().assets)
    .filter((name) => name.endsWith(`-${arch}.AppImage`))
    .sort((left, right) => {
      const score = (name) => name === fallbackName
        ? 100
        : name.includes(`-gcc-${arch}.AppImage`)
          ? 90
          : name.includes(`-clang-${arch}.AppImage`)
            ? 80
            : 70;
      return score(right) - score(left) || left.localeCompare(right, "en");
    });
  if (pinnedAssets.length === 0) {
    throw new Error(`No Linux ${arch} AppImage is pinned in artifact-integrity policy.`);
  }
  return uniqueNonEmpty(pinnedAssets);
}

function findMagickDir(root) {
  const stack = [root];
  while (stack.length) {
    const current = stack.pop();
    const entries = fs.readdirSync(current, { withFileTypes: true });
    if (entries.some((entry) => entry.isFile() && entry.name.toLowerCase() === "magick.exe")) {
      return current;
    }
    for (const entry of entries) {
      if (entry.isDirectory()) {
        stack.push(path.join(current, entry.name));
      }
    }
  }
  return null;
}

async function prepareWindows() {
  if (!path7za || !fs.existsSync(path7za)) {
    fail("7zip-bin is unavailable; run npm install before preparing ImageMagick.");
  }

  const assetName = archiveName();
  const expected = expectedSha256(assetName);
  const archivePath = path.join(CACHE_DIR, assetName);
  const verifiedArchivePath = `${archivePath}.verified-${process.pid}`;
  const extractDir = path.join(CACHE_DIR, "extract");
  const tempTarget = `${TARGET_DIR}.tmp`;

  if (!fs.existsSync(archivePath)) {
    const url = downloadUrl(assetName);
    log(`Downloading ${url}`);
    await downloadFile(url, archivePath);
  } else {
    log(`Using cached archive: ${archivePath}`);
  }
  verifyArtifact(archivePath, expected);
  fs.rmSync(verifiedArchivePath, { force: true });
  fs.copyFileSync(archivePath, verifiedArchivePath);
  verifyArtifact(verifiedArchivePath, expected);

  fs.rmSync(extractDir, { recursive: true, force: true });
  fs.mkdirSync(extractDir, { recursive: true });
  log(`Extracting verified source snapshot: ${archivePath}`);
  try {
    run(path7za, ["x", verifiedArchivePath, `-o${extractDir}`, "-y"]);
  } finally {
    fs.rmSync(verifiedArchivePath, { force: true });
  }

  const magickDir = findMagickDir(extractDir);
  if (!magickDir) {
    fail("Extracted archive did not contain magick.exe");
  }

  fs.rmSync(tempTarget, { recursive: true, force: true });
  fs.mkdirSync(path.dirname(tempTarget), { recursive: true });
  fs.cpSync(magickDir, tempTarget, { recursive: true });
  const preparationProof = writeManifest(tempTarget, {
    kind: "windows-portable",
    binary: "magick.exe",
    asset: assetName,
    source: downloadUrl(assetName),
    sourceSha256: expected,
  });

  if (!validateRuntime(tempTarget, preparationProof)) {
    fail(`Prepared runtime failed validation at ${tempTarget}`);
  }

  fs.rmSync(TARGET_DIR, { recursive: true, force: true });
  fs.renameSync(tempTarget, TARGET_DIR);
  log(`Prepared ${path.join(TARGET_DIR, "magick.exe")}`);
}

async function prepareLinux() {
  const candidates = await linuxAppImageCandidates();
  const tempTarget = `${TARGET_DIR}.tmp`;
  let assetName = null;
  let appImagePath = null;
  let lastDownloadError = null;

  for (const candidate of candidates) {
    const candidatePath = path.join(CACHE_DIR, candidate);
    let expected;
    try {
      expected = expectedSha256(candidate);
    } catch {
      continue;
    }
    if (fs.existsSync(candidatePath)) {
      verifyArtifact(candidatePath, expected);
      log(`Using cached AppImage: ${candidatePath}`);
      assetName = candidate;
      appImagePath = candidatePath;
      break;
    }

    const url = downloadUrl(candidate);
    log(`Downloading ${url}`);
    try {
      await downloadFile(url, candidatePath);
      verifyArtifact(candidatePath, expected);
      assetName = candidate;
      appImagePath = candidatePath;
      break;
    } catch (error) {
      lastDownloadError = error;
      const message = String(error?.message || error);
      if (message.includes("HTTP 404")) {
        log(`ImageMagick asset not found (${candidate}); trying next candidate.`);
        continue;
      }
      throw error;
    }
  }

  if (!assetName || !appImagePath) {
    const reason = lastDownloadError?.message || lastDownloadError || "no candidate succeeded";
    fail(`Could not fetch Linux ImageMagick AppImage: ${reason}`);
  }

  fs.rmSync(tempTarget, { recursive: true, force: true });
  fs.mkdirSync(path.join(tempTarget, "bin"), { recursive: true });

  const runtimeAppImage = path.join(tempTarget, assetName);
  fs.copyFileSync(appImagePath, runtimeAppImage);
  fs.chmodSync(runtimeAppImage, 0o755);

  const wrapperPath = path.join(tempTarget, "bin", "magick");
  fs.writeFileSync(
    wrapperPath,
    [
      "#!/usr/bin/env sh",
      "set -eu",
      'DIR="$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)"',
      "export APPIMAGE_EXTRACT_AND_RUN=${APPIMAGE_EXTRACT_AND_RUN:-1}",
      'exec "$DIR/' + assetName + '" "$@"',
      "",
    ].join("\n"),
  );
  fs.chmodSync(wrapperPath, 0o755);
  const preparationProof = writeManifest(tempTarget, {
    kind: "linux-appimage",
    binary: "bin/magick",
    asset: assetName,
    appImage: assetName,
    source: downloadUrl(assetName),
    sourceSha256: expectedSha256(assetName),
  });

  if (!validateRuntime(tempTarget, preparationProof)) {
    fail(`Prepared runtime failed validation at ${tempTarget}`);
  }

  fs.rmSync(TARGET_DIR, { recursive: true, force: true });
  fs.renameSync(tempTarget, TARGET_DIR);
  log(`Prepared ${path.join(TARGET_DIR, "bin", "magick")}`);
}

function resolveCommandPath(command) {
  if (path.isAbsolute(command)) {
    return fs.existsSync(command) ? command : null;
  }
  const result = capture("which", [command]);
  const resolved = (result.stdout || "").trim().split(/\r?\n/).filter(Boolean)[0];
  return result.status === 0 && resolved ? resolved : null;
}

function resolveMacSourcePrefix() {
  const configured = process.env.IMAGEMAGICK_VENDOR_DIR?.trim();
  if (!configured) {
    return null;
  }
  const sourcePrefix = path.resolve(configured);
  if (!fs.existsSync(sourcePrefix) || !fs.statSync(sourcePrefix).isDirectory()) {
    throw new Error(`IMAGEMAGICK_VENDOR_DIR is not a directory: ${sourcePrefix}`);
  }
  return sourcePrefix;
}

function parseOtoolDeps(filePath) {
  const result = capture("otool", ["-L", filePath]);
  if (result.status !== 0) {
    fail(`otool -L failed for ${filePath}: ${result.stderr || result.status}`);
  }
  return (result.stdout || "")
    .split(/\r?\n/)
    .slice(1)
    .map((line) => line.trim().split(/\s+/)[0])
    .filter(Boolean)
    .filter((dep) => !dep.startsWith("/System/Library/") && !dep.startsWith("/usr/lib/"));
}

function isMachOFile(filePath) {
  if (!fs.existsSync(filePath) || !fs.statSync(filePath).isFile()) {
    return false;
  }
  const result = capture("file", [filePath]);
  return result.status === 0 && /Mach-O/.test(result.stdout || "");
}

function walkFiles(rootDir) {
  const stack = [rootDir];
  const files = [];
  while (stack.length) {
    const current = stack.pop();
    const entries = fs.readdirSync(current, { withFileTypes: true });
    for (const entry of entries) {
      const fullPath = path.join(current, entry.name);
      if (entry.isDirectory()) {
        stack.push(fullPath);
      } else if (entry.isFile()) {
        files.push(fullPath);
      }
    }
  }
  return files;
}

function isPathInside(rootDir, candidatePath) {
  const resolvedRoot = path.resolve(rootDir);
  const resolvedCandidate = path.resolve(candidatePath);
  return resolvedCandidate === resolvedRoot ||
    resolvedCandidate.startsWith(`${resolvedRoot}${path.sep}`);
}

function relinkMacDylibs(targetDir, mainExecutable, verifiedSourceRoot) {
  for (const tool of ["otool", "install_name_tool", "file"]) {
    if (!resolveCommandPath(tool)) {
      fail(`macOS runtime vendoring requires ${tool}.`);
    }
  }

  const libDir = path.join(targetDir, "lib");
  fs.mkdirSync(libDir, { recursive: true });

  const queue = [mainExecutable];
  const visited = new Set();
  const copiedBySource = new Map();

  while (queue.length) {
    const current = queue.shift();
    if (visited.has(current) || !fs.existsSync(current) || !isMachOFile(current)) {
      continue;
    }
    visited.add(current);

    const deps = parseOtoolDeps(current);
    for (const dep of deps) {
      if (dep.startsWith("@loader_path/") || dep.startsWith("@executable_path/")) {
        const token = dep.startsWith("@loader_path/")
          ? "@loader_path/"
          : "@executable_path/";
        const baseDir = token === "@loader_path/"
          ? path.dirname(current)
          : path.dirname(mainExecutable);
        const relativeDependency = path.resolve(baseDir, dep.slice(token.length));
        if (
          !isPathInside(targetDir, relativeDependency) ||
          !fs.existsSync(relativeDependency)
        ) {
          fail(`Refusing unresolved or external macOS dependency: ${dep} (${current})`);
        }
        queue.push(relativeDependency);
        continue;
      }
      if (!path.isAbsolute(dep)) {
        fail(
          `Refusing unresolved macOS dependency ${dep}; pre-relocate @rpath dependencies inside IMAGEMAGICK_VENDOR_DIR.`,
        );
      }
      const resolvedDependency = path.resolve(dep);
      if (!isPathInside(verifiedSourceRoot, resolvedDependency)) {
        fail(
          `Refusing unverified macOS dependency outside IMAGEMAGICK_VENDOR_DIR: ${dep}`,
        );
      }
      const snapshotDependency = path.join(
        targetDir,
        path.relative(path.resolve(verifiedSourceRoot), resolvedDependency),
      );
      if (
        !isPathInside(targetDir, snapshotDependency) ||
        !fs.existsSync(snapshotDependency) ||
        !fs.statSync(snapshotDependency).isFile()
      ) {
        fail(`Verified macOS snapshot does not contain dependency: ${dep}`);
      }
      const depBase = path.basename(dep);
      let vendored = copiedBySource.get(dep);
      if (!vendored) {
        vendored = path.join(libDir, depBase);
        if (!fs.existsSync(vendored)) {
          fs.copyFileSync(snapshotDependency, vendored);
          fs.chmodSync(vendored, 0o755);
        }
        copiedBySource.set(dep, vendored);
        queue.push(vendored);
      }

      const replacement = current === mainExecutable
        ? `@executable_path/../lib/${depBase}`
        : `@loader_path/${depBase}`;
      run("install_name_tool", ["-change", dep, replacement, current]);
    }

    if (current !== mainExecutable) {
      run("install_name_tool", ["-id", `@loader_path/${path.basename(current)}`, current]);
    }
  }
}

function adHocSignMacRuntime(targetDir, mainExecutable) {
  if (!resolveCommandPath("codesign")) {
    fail("macOS runtime vendoring requires codesign.");
  }

  const machOFiles = walkFiles(targetDir).filter(isMachOFile);
  const signOrder = machOFiles
    .filter((filePath) => filePath !== mainExecutable)
    .concat(machOFiles.includes(mainExecutable) ? [mainExecutable] : []);

  log(`Ad-hoc signing ${signOrder.length} Mach-O files for macOS runtime.`);
  for (const filePath of signOrder) {
    run("codesign", ["--force", "--sign", "-", "--timestamp=none", filePath]);
  }
}

async function prepareMacOS() {
  const sourcePrefix = resolveMacSourcePrefix();
  if (!sourcePrefix) {
    throw new Error(
      "Set IMAGEMAGICK_VENDOR_DIR to an explicit, self-contained macOS runtime tree.",
    );
  }
  if (!isSha256(MAC_SOURCE_TREE_SHA256)) {
    throw new Error(
      "IMAGEMAGICK_MAC_SOURCE_TREE_SHA256 must be a 64-character lowercase hexadecimal digest.",
    );
  }
  const tempTarget = `${TARGET_DIR}.tmp`;
  fs.rmSync(tempTarget, { recursive: true, force: true });
  fs.cpSync(sourcePrefix, tempTarget, {
    recursive: true,
    dereference: false,
    verbatimSymlinks: true,
  });
  const snapshotSourceTreeSha256 = sha256Tree(tempTarget, {
    excludeManifest: false,
  });
  if (snapshotSourceTreeSha256 !== MAC_SOURCE_TREE_SHA256) {
    fs.rmSync(tempTarget, { recursive: true, force: true });
    throw new Error(
      `macOS ImageMagick source-tree SHA-256 mismatch. Expected ${MAC_SOURCE_TREE_SHA256}; got ${snapshotSourceTreeSha256}.`,
    );
  }

  const targetMagick = path.join(tempTarget, "bin", "magick");
  if (!fs.existsSync(targetMagick) || !fs.statSync(targetMagick).isFile()) {
    throw new Error(`macOS ImageMagick snapshot does not contain bin/magick: ${sourcePrefix}`);
  }
  fs.chmodSync(targetMagick, 0o755);
  relinkMacDylibs(tempTarget, targetMagick, sourcePrefix);
  adHocSignMacRuntime(tempTarget, targetMagick);
  const preparationProof = writeManifest(tempTarget, {
    kind: "macos-vendored",
    binary: "bin/magick",
    source: "explicit-vendor-tree",
    sourceTreeSha256: MAC_SOURCE_TREE_SHA256,
  });

  if (!validateRuntime(tempTarget, preparationProof)) {
    fail(`Prepared runtime failed validation at ${tempTarget}`);
  }

  fs.rmSync(TARGET_DIR, { recursive: true, force: true });
  fs.renameSync(tempTarget, TARGET_DIR);
  log(`Prepared ${path.join(TARGET_DIR, "bin", "magick")}`);
}

async function main() {
  if (process.argv[2] === "--print-tree-sha256") {
    const sourceDir = process.argv[3];
    if (!sourceDir) {
      throw new Error("Usage: prepare-imagemagick.cjs --print-tree-sha256 <directory>");
    }
    console.log(sha256Tree(path.resolve(sourceDir), { excludeManifest: false }));
    return;
  }

  if (PLATFORM === "darwin") {
    const sourcePrefix = resolveMacSourcePrefix();
    if (sourcePrefix && !MAC_SOURCE_TREE_SHA256) {
      throw new Error(
        "IMAGEMAGICK_VENDOR_DIR requires IMAGEMAGICK_MAC_SOURCE_TREE_SHA256.",
      );
    }
    if (!MAC_SOURCE_TREE_SHA256 && !EXPORT_ENABLED) {
      fs.rmSync(TARGET_DIR, { recursive: true, force: true });
      fs.rmSync(`${TARGET_DIR}.tmp`, { recursive: true, force: true });
      log(
        "macOS runtime safe-disabled because presentation export is disabled and no verified vendor tree was supplied.",
      );
      return;
    }
    if (!isSha256(MAC_SOURCE_TREE_SHA256)) {
      throw new Error(
        "IMAGEMAGICK_MAC_SOURCE_TREE_SHA256 must be a 64-character lowercase hexadecimal digest.",
      );
    }
  }

  if (PLATFORM === "win32") {
    await prepareWindows();
    return;
  }
  if (PLATFORM === "linux") {
    await prepareLinux();
    return;
  }
  if (PLATFORM === "darwin") {
    await prepareMacOS();
    return;
  }

  fail(`Unsupported platform for bundled ImageMagick: ${PLATFORM}-${ARCH}`);
}

if (require.main === module) {
  main().catch((error) => fail(error?.stack || error?.message || String(error)));
}

module.exports = {
  MANIFEST_NAME,
  readManifest,
  sha256File,
  sha256Tree,
  validateRuntimeIntegrity,
};
