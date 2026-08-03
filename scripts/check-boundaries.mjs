import fs from "node:fs";
import path from "node:path";
import process from "node:process";
import { execFileSync } from "node:child_process";
import { fileURLToPath } from "node:url";

const ROOT = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..");
const CONFIG_PATH = path.join(ROOT, "config", "architecture-boundaries.json");
const SOURCE_EXTENSIONS = new Set([".js", ".jsx", ".mjs", ".cjs", ".ts", ".tsx", ".py"]);
const SKIP_DIRECTORIES = new Set([
  ".git", ".next", ".venv", "node_modules", "app_dist", "dist", "build", "coverage",
  "htmlcov", "playwright-report", "test-results", "artifacts", "__pycache__",
]);

function relative(file) {
  return path.relative(ROOT, file).replaceAll("\\", "/");
}

function filesUnder(directory) {
  if (!fs.existsSync(directory)) return [];
  const files = [];
  for (const entry of fs.readdirSync(directory, { withFileTypes: true })) {
    if (entry.isDirectory() && SKIP_DIRECTORIES.has(entry.name)) continue;
    const full = path.join(directory, entry.name);
    if (entry.isDirectory()) files.push(...filesUnder(full));
    else if (SOURCE_EXTENSIONS.has(path.extname(entry.name))) files.push(full);
  }
  return files;
}

function imports(text) {
  return [...text.matchAll(/(?:from\s+|import\s*\(|require\s*\()\s*["']([^"']+)["']/g)]
    .map((match) => match[1]);
}

const config = JSON.parse(fs.readFileSync(CONFIG_PATH, "utf8"));
const errors = [];
const sourceFiles = [
  ...filesUnder(path.join(ROOT, "servers", "fastapi")),
  ...filesUnder(path.join(ROOT, "servers", "nextjs")),
  ...filesUnder(path.join(ROOT, "electron", "app")),
];

const exceptionKeys = new Set();
for (const exception of config.exceptions ?? []) {
  for (const field of ["rule", "file", "reason", "owner", "removalSprint"]) {
    if (!exception[field] || typeof exception[field] !== "string") {
      errors.push(`boundary-config: exception is missing non-empty '${field}'`);
    }
  }
  exceptionKeys.add(`${exception.rule}:${exception.file}`);
}

function report(rule, file, detail) {
  const rel = relative(file);
  if (!exceptionKeys.has(`${rule}:${rel}`)) errors.push(`${rule}: ${rel}: ${detail}`);
}

for (const file of sourceFiles) {
  const rel = relative(file);
  const text = fs.readFileSync(file, "utf8");
  const imported = imports(text);

  if (rel.startsWith("servers/nextjs/components/ui/")) {
    for (const specifier of imported) {
      if (specifier.startsWith("@/features/") || specifier.includes("app/(presentation-generator)")) {
        report("shared-ui-imports-feature", file, `shared UI imports feature module '${specifier}'`);
      }
    }
  }

  if (rel.startsWith("servers/nextjs/")) {
    for (const specifier of imported) {
      if (specifier === "electron" || specifier.includes("electron/app")) {
        report("browser-imports-electron", file, `browser source imports '${specifier}'`);
      }
      const isServerExportAdapter = rel === "servers/nextjs/app/api/export-presentation/route.ts";
      if (specifier.includes("presentation-export") && !rel.includes("services/api/") && !isServerExportAdapter) {
        report("browser-imports-export-runtime", file, `ordinary application source imports '${specifier}'`);
      }
    }
  }

  if (rel.startsWith("servers/fastapi/modules/presentations/")) {
    for (const specifier of imported) {
      if (/api\.v1\.ppt\.endpoints\.(openai|google|anthropic|ollama)/.test(specifier) || /provider_settings/.test(specifier)) {
        report("domain-imports-provider", file, `presentation domain imports provider transport/settings '${specifier}'`);
      }
    }
  }

  const isNewEditorSurface = rel.startsWith("servers/nextjs/components/slide-editor/") || rel.startsWith("servers/nextjs/features/");
  if (isNewEditorSurface && /(?:V1ContentRender|V1SelectEdit)/.test(text)) {
    report("legacy-v1-import", file, "new editor/feature code imports a deprecated V1 renderer");
  }

  if (!rel.includes("/scripts/") && !rel.includes("/tests/") && !rel.endsWith("generated/product-identity.ts")) {
    const writesRuntimeSource = /(?:writeFile|writeFileSync|outputFile|createWriteStream)[\s\S]{0,220}\.(?:tsx?|jsx?)["'`]/.test(text);
    if (writesRuntimeSource) report("runtime-source-generation", file, "runtime code appears to write source files");
  }
}

const routeDecorator = /@(?:\w+_ROUTER|router)\.(?:get|post|put|patch|delete)\s*\(/;
for (const file of filesUnder(path.join(ROOT, "servers", "fastapi", "api"))) {
  const rel = relative(file);
  if (!routeDecorator.test(fs.readFileSync(file, "utf8"))) continue;
  if (!config.routeOwners[rel]) errors.push(`unowned-route: ${rel}: add an owner to config/architecture-boundaries.json`);
}
for (const ownedFile of Object.keys(config.routeOwners)) {
  if (!fs.existsSync(path.join(ROOT, ownedFile))) errors.push(`stale-route-owner: ${ownedFile}: file does not exist`);
}

const forbiddenTrackedCandidates = [
  "servers/nextjs/tsconfig.tsbuildinfo", "servers/nextjs/playwright-report",
  "servers/nextjs/test-results", "artifacts/sbom",
];
const trackedFiles = new Set(
  execFileSync("git", ["ls-files"], { cwd: ROOT, encoding: "utf8" })
    .split(/\r?\n/)
    .filter(Boolean),
);
for (const candidate of forbiddenTrackedCandidates) {
  const tracked = [...trackedFiles].some(
    (file) => file === candidate || file.startsWith(`${candidate}/`),
  );
  if (tracked) {
    errors.push(`generated-artifact: ${candidate}: generated output must not be tracked`);
  }
}

if (errors.length) {
  console.error("Architecture boundary check failed:\n" + errors.map((error) => `  - ${error}`).join("\n"));
  process.exit(1);
}
console.log(`Architecture boundary check passed (${sourceFiles.length} source files, ${Object.keys(config.routeOwners).length} route owners).`);
