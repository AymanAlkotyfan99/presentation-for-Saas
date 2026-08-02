const crypto = require("crypto");
const fs = require("fs");
const https = require("https");
const path = require("path");
const { spawnSync } = require("child_process");

const electronRoot = path.join(__dirname, "..");
const repositoryRoot = path.join(electronRoot, "..");
const fastapiDir = path.join(repositoryRoot, "servers", "fastapi");
const integrityFile = path.join(repositoryRoot, "config", "artifact-integrity.json");
const uvCmd = process.platform === "win32" ? "uv.exe" : "uv";
const strictMode =
  (process.env.MEM0_SPACY_STRICT || "").trim().toLowerCase() === "true";
const venvDir = path.join(fastapiDir, ".venv");
const venvPython = path.join(
  venvDir,
  process.platform === "win32" ? "Scripts" : "bin",
  process.platform === "win32" ? "python.exe" : "python",
);

function isSha256(value) {
  return /^[a-f0-9]{64}$/.test(value || "");
}

function sha256File(filePath) {
  const hash = crypto.createHash("sha256");
  hash.update(fs.readFileSync(filePath));
  return hash.digest("hex");
}

function readModelPolicy() {
  if (!fs.existsSync(integrityFile)) {
    throw new Error("Missing config/artifact-integrity.json; refusing mutable spaCy model acquisition.");
  }
  const policy = JSON.parse(fs.readFileSync(integrityFile, "utf8")).spacyModel;
  if (
    !policy ||
    !/^[a-z][a-z0-9_]*$/.test(policy.name || "") ||
    !/^[0-9]+(?:\.[0-9]+){2}(?:[a-z0-9.-]*)?$/.test(policy.version || "") ||
    policy.asset !== `${policy.name}-${policy.version}-py3-none-any.whl` ||
    path.basename(policy.asset || "") !== policy.asset ||
    !policy.asset.endsWith(".whl") ||
    !isSha256(policy.sha256) ||
    typeof policy.source !== "string" ||
    !policy.source.startsWith("https://")
  ) {
    throw new Error("config/artifact-integrity.json contains an invalid spaCy model policy.");
  }
  const requestedModel = (process.env.MEM0_SPACY_MODEL || policy.name).trim();
  if (requestedModel !== policy.name) {
    throw new Error(
      `MEM0_SPACY_MODEL=${requestedModel} is not pinned; only ${policy.name} ${policy.version} is allowed.`,
    );
  }
  return policy;
}

function modelDownloadUrl(policy) {
  const tagPrefix = "https://github.com/explosion/spacy-models/releases/tag/";
  if (!policy.source.startsWith(tagPrefix)) {
    throw new Error(`Unsupported spaCy model policy source: ${policy.source}`);
  }
  const releaseTag = policy.source.slice(tagPrefix.length);
  if (releaseTag !== `${policy.name}-${policy.version}`) {
    throw new Error(`Invalid spaCy model release tag: ${releaseTag}`);
  }
  return `https://github.com/explosion/spacy-models/releases/download/${releaseTag}/${policy.asset}`;
}

function runUv(args, description, options = {}) {
  const result = spawnSync(uvCmd, args, {
    cwd: fastapiDir,
    stdio: options.quiet ? "ignore" : "inherit",
    env: process.env,
  });
  if (result.error) {
    throw new Error(`${description} failed: ${result.error.message}`);
  }
  return result.status === 0;
}

function syncLockedEnvironment() {
  console.log("[spacy-setup] Synchronizing the locked FastAPI environment.");
  return runUv(["sync", "--locked", "--dev"], "uv sync --locked");
}

function runUvPython(args, description, options = {}) {
  return runUv(
    ["run", "--locked", "--no-sync", "python", ...args],
    description,
    options,
  );
}

function hasModelInstalled(policy) {
  const probe = [
    "import importlib, spacy",
    `model = importlib.import_module(${JSON.stringify(policy.name)})`,
    `assert model.__version__ == ${JSON.stringify(policy.version)}`,
    `spacy.load(${JSON.stringify(policy.name)})`,
  ].join("; ");
  return runUvPython(
    ["-c", probe],
    `spaCy model check (${policy.name} ${policy.version})`,
    { quiet: true },
  );
}

function downloadFile(url, destination, redirects = 5) {
  return new Promise((resolve, reject) => {
    if (!url.startsWith("https://")) {
      reject(new Error(`Refusing non-HTTPS spaCy model download: ${url}`));
      return;
    }
    const request = https.get(
      url,
      { headers: { "User-Agent": "Presenton spaCy model fetcher" } },
      (response) => {
        if ([301, 302, 303, 307, 308].includes(response.statusCode || 0)) {
          const location = response.headers.location;
          response.resume();
          if (!location || redirects <= 0) {
            reject(new Error(`Invalid redirect while downloading ${url}`));
            return;
          }
          downloadFile(new URL(location, url).toString(), destination, redirects - 1)
            .then(resolve, reject);
          return;
        }
        if (response.statusCode !== 200) {
          response.resume();
          reject(new Error(`Download failed with HTTP ${response.statusCode}: ${url}`));
          return;
        }

        fs.mkdirSync(path.dirname(destination), { recursive: true });
        const temporaryPath = `${destination}.part-${process.pid}`;
        fs.rmSync(temporaryPath, { force: true });
        const output = fs.createWriteStream(temporaryPath, { flags: "wx", mode: 0o600 });
        response.pipe(output);
        output.on("finish", () => {
          output.close(() => {
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
        output.on("error", (error) => {
          fs.rmSync(temporaryPath, { force: true });
          reject(error);
        });
        response.on("error", (error) => {
          output.destroy();
          fs.rmSync(temporaryPath, { force: true });
          reject(error);
        });
      },
    );
    request.setTimeout(120000, () => request.destroy(new Error(`Download timed out: ${url}`)));
    request.on("error", reject);
  });
}

async function acquireVerifiedWheel(policy) {
  const wheelPath = path.join(
    electronRoot,
    ".cache",
    "spacy-model",
    policy.version,
    policy.asset,
  );
  if (fs.existsSync(wheelPath) && sha256File(wheelPath) !== policy.sha256) {
    fs.rmSync(wheelPath, { force: true });
  }
  if (!fs.existsSync(wheelPath)) {
    const url = modelDownloadUrl(policy);
    console.log(`[spacy-setup] Downloading pinned model wheel: ${url}`);
    await downloadFile(url, wheelPath);
  }
  const actual = sha256File(wheelPath);
  if (actual !== policy.sha256) {
    fs.rmSync(wheelPath, { force: true });
    throw new Error(
      `spaCy model SHA-256 mismatch. Expected ${policy.sha256}; got ${actual}.`,
    );
  }
  return wheelPath;
}

function installVerifiedWheel(wheelPath, policy) {
  return runUv(
    [
      "pip",
      "install",
      "--python",
      venvPython,
      "--no-deps",
      "--reinstall",
      wheelPath,
    ],
    `verified spaCy model install (${policy.name} ${policy.version})`,
  );
}

async function main() {
  const policy = readModelPolicy();
  if (!syncLockedEnvironment() || !fs.existsSync(venvPython)) {
    throw new Error("Failed to synchronize the locked FastAPI virtual environment.");
  }
  console.log(`[spacy-setup] Checking spaCy model: ${policy.name} ${policy.version}`);
  if (hasModelInstalled(policy)) {
    console.log(`[spacy-setup] Pinned spaCy model is already available: ${policy.name}`);
    return;
  }

  try {
    const wheelPath = await acquireVerifiedWheel(policy);
    if (installVerifiedWheel(wheelPath, policy) && hasModelInstalled(policy)) {
      console.log(`[spacy-setup] Installed verified spaCy model: ${policy.name} ${policy.version}`);
      return;
    }
  } catch (error) {
    if (strictMode) {
      throw error;
    }
    console.warn(`[spacy-setup] ${error.message}`);
  }

  const message =
    `[spacy-setup] Could not install verified spaCy model (${policy.name} ${policy.version}). ` +
    "Mem0 will self-disable at runtime if this dependency is unavailable.";
  if (strictMode) {
    throw new Error(message);
  }
  console.warn(message);
}

if (require.main === module) {
  main().catch((error) => {
    console.error(`[spacy-setup] ${error.message}`);
    process.exit(1);
  });
}

module.exports = {
  acquireVerifiedWheel,
  modelDownloadUrl,
  readModelPolicy,
  sha256File,
};
