import { mkdirSync, readFileSync, writeFileSync } from "node:fs";
import { dirname, resolve } from "node:path";
import { fileURLToPath } from "node:url";
import { spawnSync } from "node:child_process";

const scriptDirectory = dirname(fileURLToPath(import.meta.url));
const repositoryRoot = resolve(scriptDirectory, "..");
const outputDirectory = resolve(repositoryRoot, "artifacts", "sbom");
const cyclonedxNpmCli = resolve(
  repositoryRoot,
  "node_modules",
  "@cyclonedx",
  "cyclonedx-npm",
  "bin",
  "cyclonedx-npm-cli.js",
);

const args = new Set(process.argv.slice(2));
const nodeOnly = args.has("--node-only");
const pythonOnly = args.has("--python-only");

if (nodeOnly && pythonOnly) {
  throw new Error("Use at most one of --node-only and --python-only");
}

mkdirSync(outputDirectory, { recursive: true });

function run(command, commandArgs, options = {}) {
  const result = spawnSync(command, commandArgs, {
    cwd: repositoryRoot,
    encoding: "utf8",
    stdio: "inherit",
    ...options,
  });
  if (result.error) throw result.error;
  if (result.status !== 0) {
    throw new Error(`${command} exited with status ${result.status}`);
  }
}

function generateNodeSbom(name, manifestPath) {
  run(process.execPath, [
    cyclonedxNpmCli,
    "--package-lock-only",
    "--output-reproducible",
    "--output-format",
    "JSON",
    "--spec-version",
    "1.6",
    "--validate",
    "--output-file",
    resolve(outputDirectory, `${name}.cdx.json`),
    resolve(repositoryRoot, manifestPath),
  ]);
}

function generateExternalArtifactSbom() {
  const policy = JSON.parse(
    readFileSync(resolve(repositoryRoot, "config", "artifact-integrity.json"), "utf8"),
  );
  const components = [];
  const addAssets = (groupName, group) => {
    for (const [assetName, sha256] of Object.entries(group.assets)) {
      components.push({
        type: "file",
        name: assetName,
        version: group.version,
        hashes: [{ alg: "SHA-256", content: sha256 }],
        externalReferences: [{ type: "distribution", url: group.source }],
        properties: [
          { name: "presenton:artifact-group", value: groupName },
          { name: "presenton:license-status", value: group.licenseStatus },
        ],
      });
    }
  };

  addAssets("presentation-export", policy.presentationExport);
  addAssets("imagemagick", policy.imageMagick);
  components.push({
    type: "file",
    name: policy.spacyModel.asset,
    version: policy.spacyModel.version,
    hashes: [{ alg: "SHA-256", content: policy.spacyModel.sha256 }],
    externalReferences: [{ type: "distribution", url: policy.spacyModel.source }],
    properties: [
      { name: "presenton:artifact-group", value: "spacy-model" },
      { name: "presenton:license-status", value: policy.spacyModel.licenseStatus },
    ],
  });
  components.sort((left, right) => left.name.localeCompare(right.name));

  const bom = {
    bomFormat: "CycloneDX",
    specVersion: "1.6",
    version: 1,
    metadata: {
      component: {
        type: "application",
        name: "presenton-external-artifacts",
      },
      properties: [
        {
          name: "presenton:policy-source",
          value: "config/artifact-integrity.json",
        },
        {
          name: "presenton:chromium-status",
          value: policy.electronChromium.verificationStatus,
        },
      ],
    },
    components,
  };
  writeFileSync(
    resolve(outputDirectory, "external-artifacts.cdx.json"),
    `${JSON.stringify(bom, null, 2)}\n`,
    { encoding: "utf8", mode: 0o600 },
  );
}

if (!pythonOnly) {
  generateNodeSbom("root-node", "package.json");
  generateNodeSbom("nextjs", "servers/nextjs/package.json");
  generateNodeSbom("electron", "electron/package.json");
  generateExternalArtifactSbom();
}

if (!nodeOnly) {
  run(
    process.platform === "win32" ? "uv.exe" : "uv",
    [
      "run",
      "--locked",
      "cyclonedx-py",
      "environment",
      "--pyproject",
      "pyproject.toml",
      "--output-reproducible",
      "--output-format",
      "JSON",
      "--output-file",
      resolve(outputDirectory, "python.cdx.json"),
    ],
    { cwd: resolve(repositoryRoot, "servers", "fastapi") },
  );
}

console.log(`CycloneDX SBOMs generated in ${outputDirectory}`);
