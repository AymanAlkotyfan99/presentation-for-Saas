import fs from "node:fs";
import path from "node:path";
import process from "node:process";
import { fileURLToPath } from "node:url";

const ROOT = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..");
const errors = [];
const MAINTAINED_BRANCHES = ["dev", "staging", "production"];

const requiredFiles = [
  "AGENTS.md",
  "ARCHITECTURE.md",
  "SECURITY.md",
  "CODESTYLE.md",
  "TESTING.md",
  "Sprint_exeuteive.md",
  "servers/fastapi/AGENTS.md",
  "servers/nextjs/AGENTS.md",
  "electron/AGENTS.md",
  ".github/workflows/README.md",
  ".github/workflows/quality.yml",
  ".github/workflows/secret-scan.yml",
  ".github/workflows/test-all.yml",
  "config/architecture-boundaries.json",
  "schemas/presentation-document/v1.schema.json",
  "servers/fastapi/utils/architecture_flags.py",
  "servers/fastapi/utils/outbound_http.py",
  "servers/fastapi/modules/providers/application/executor.py",
  "servers/fastapi/modules/jobs/application/submit.py",
  "servers/fastapi/modules/assets/providers/storage/base.py",
  "servers/nextjs/lib/safe-markdown.ts",
  "servers/nextjs/lib/security-headers.mjs",
];

function absolute(relativePath) {
  return path.join(ROOT, ...relativePath.split("/"));
}

function read(relativePath) {
  return fs.readFileSync(absolute(relativePath), "utf8");
}

for (const relativePath of requiredFiles) {
  if (!fs.existsSync(absolute(relativePath))) {
    errors.push(`required-path: ${relativePath}: file does not exist`);
  } else if (fs.statSync(absolute(relativePath)).isFile() && !read(relativePath).trim()) {
    errors.push(`required-path: ${relativePath}: file is empty`);
  }
}

const requiredDocumentText = {
  "AGENTS.md": [
    "ARCHITECTURE.md",
    "SECURITY.md",
    "CODESTYLE.md",
    "TESTING.md",
    "Sprint_exeuteive.md",
    "Maintained branches are `dev`, `staging`, and `production`",
    "MUST NOT",
  ],
  "ARCHITECTURE.md": [
    "## Rollout state: current authority versus staged foundations",
    "## Dependency direction and extension points",
    "## Planned evolution (not current implementation)",
  ],
  "SECURITY.md": [
    "## Trust boundaries",
    "### Known gaps",
    "## Production security invariants",
  ],
  "CODESTYLE.md": [
    "## Python and FastAPI",
    "## TypeScript, React, and Next.js",
    "There is no repository-wide formatter",
  ],
  "TESTING.md": [
    "## Mandatory local checks",
    "## CI checks",
    "## Known baseline blockers",
    "## Manual acceptance and E2E",
    "npm run check:governance",
  ],
};

for (const [relativePath, fragments] of Object.entries(requiredDocumentText)) {
  if (!fs.existsSync(absolute(relativePath))) continue;
  const content = read(relativePath);
  for (const fragment of fragments) {
    if (!content.includes(fragment)) {
      errors.push(`document-contract: ${relativePath}: missing '${fragment}'`);
    }
  }
}

for (const relativePath of [
  "servers/fastapi/AGENTS.md",
  "servers/nextjs/AGENTS.md",
  "electron/AGENTS.md",
]) {
  if (fs.existsSync(absolute(relativePath)) && !read(relativePath).includes("root `AGENTS.md`")) {
    errors.push(`nested-agents: ${relativePath}: must explicitly inherit root AGENTS.md`);
  }
}

function validateMarkdownLinks(relativePath) {
  const content = read(relativePath);
  const links = content.matchAll(/!?(?:\[[^\]]*\])\(([^)]+)\)/g);
  for (const match of links) {
    let target = match[1].trim();
    if (target.startsWith("<") && target.endsWith(">")) {
      target = target.slice(1, -1);
    }
    if (!target || target.startsWith("#") || /^(?:[a-z][a-z0-9+.-]*:|\/\/)/i.test(target)) {
      continue;
    }
    target = target.split("#", 1)[0];
    try {
      target = decodeURIComponent(target);
    } catch {
      errors.push(`markdown-link: ${relativePath}: invalid URL encoding in '${match[1]}'`);
      continue;
    }
    const resolved = path.resolve(path.dirname(absolute(relativePath)), target);
    const withinRepository = resolved === ROOT || resolved.startsWith(`${ROOT}${path.sep}`);
    if (!withinRepository) {
      errors.push(`markdown-link: ${relativePath}: link escapes repository: '${match[1]}'`);
    } else if (!fs.existsSync(resolved)) {
      errors.push(`markdown-link: ${relativePath}: target does not exist: '${match[1]}'`);
    }
  }
}

for (const relativePath of [
  "AGENTS.md",
  "ARCHITECTURE.md",
  "SECURITY.md",
  "CODESTYLE.md",
  "TESTING.md",
  "servers/fastapi/AGENTS.md",
  "servers/nextjs/AGENTS.md",
  "electron/AGENTS.md",
]) {
  if (fs.existsSync(absolute(relativePath))) validateMarkdownLinks(relativePath);
}

if (fs.existsSync(absolute("package.json"))) {
  const packageJson = JSON.parse(read("package.json"));
  if (packageJson.scripts?.["check:governance"] !== "node scripts/check-governance.mjs") {
    errors.push("package-script: package.json must expose check:governance");
  }
}

if (fs.existsSync(absolute("config/architecture-boundaries.json"))) {
  const boundaries = JSON.parse(read("config/architecture-boundaries.json"));
  const capabilityRoute = "servers/fastapi/api/runtime_capabilities.py";
  if (!boundaries.routeOwners?.[capabilityRoute]) {
    errors.push(`route-owner: ${capabilityRoute}: current API route must have an owner`);
  }
}

const workflowDirectory = absolute(".github/workflows");
for (const entry of fs.readdirSync(workflowDirectory, { withFileTypes: true })) {
  if (!entry.isFile() || !/\.ya?ml$/i.test(entry.name)) continue;
  const relativePath = `.github/workflows/${entry.name}`;
  const content = read(relativePath);
  for (const match of content.matchAll(/^\s*-?\s*uses:\s*([^\s#]+).*$/gm)) {
    const action = match[1];
    if (action.startsWith("./")) continue;
    const revision = action.includes("@") ? action.slice(action.lastIndexOf("@") + 1) : "";
    if (!/^[0-9a-f]{40}$/i.test(revision)) {
      errors.push(`action-pin: ${relativePath}: '${action}' must use a full commit SHA`);
    }
  }
}

function getWorkflowBranchFilter(relativePath, eventName) {
  const lines = read(relativePath).replace(/\r\n/g, "\n").split("\n");
  const eventLine = `  ${eventName}:`;
  const eventStart = lines.findIndex((line) => line === eventLine);
  if (eventStart < 0) return { error: `missing '${eventName}' trigger` };

  let eventEnd = lines.length;
  for (let index = eventStart + 1; index < lines.length; index += 1) {
    if (/^  [A-Za-z_][A-Za-z0-9_-]*:\s*$/.test(lines[index])) {
      eventEnd = index;
      break;
    }
  }

  const branchesLine = lines.findIndex(
    (line, index) => index > eventStart && index < eventEnd && /^    branches:/.test(line),
  );
  if (branchesLine < 0) return { error: `'${eventName}' trigger has no branch filter` };

  const inline = lines[branchesLine].match(/^    branches:\s*\[(.*)\]\s*$/);
  if (inline) {
    return {
      branches: inline[1]
        .split(",")
        .map((branch) => branch.trim().replace(/^["']|["']$/g, ""))
        .filter(Boolean),
    };
  }

  if (lines[branchesLine] !== "    branches:") {
    return { error: `'${eventName}' branch filter has an unsupported shape` };
  }

  const branches = [];
  for (let index = branchesLine + 1; index < eventEnd; index += 1) {
    const match = lines[index].match(/^      -\s*([A-Za-z0-9._/-]+)\s*$/);
    if (match) branches.push(match[1]);
  }
  return { branches };
}

for (const relativePath of [
  ".github/workflows/quality.yml",
  ".github/workflows/secret-scan.yml",
  ".github/workflows/test-all.yml",
]) {
  if (!fs.existsSync(absolute(relativePath))) continue;
  for (const eventName of ["push", "pull_request"]) {
    const result = getWorkflowBranchFilter(relativePath, eventName);
    if (result.error) {
      errors.push(`branch-policy: ${relativePath}: ${result.error}`);
      continue;
    }
    if (JSON.stringify(result.branches) !== JSON.stringify(MAINTAINED_BRANCHES)) {
      errors.push(
        `branch-policy: ${relativePath}: '${eventName}' branches must be exactly ${MAINTAINED_BRANCHES.join(", ")}; found ${result.branches.join(", ") || "none"}`,
      );
    }
  }
}

if (fs.existsSync(absolute(".github/workflows/quality.yml"))) {
  const quality = read(".github/workflows/quality.yml");
  for (const command of [
    "npm run check:governance",
    "npm run check:architecture",
    "npm run localization:check",
    "npm run canonical:check",
    "python3 scripts/scan_secrets.py",
    "docker compose config --quiet",
  ]) {
    if (!quality.includes(command)) {
      errors.push(`quality-workflow: missing '${command}'`);
    }
  }
}

if (errors.length) {
  console.error(
    "Governance check failed:\n" + errors.map((error) => `  - ${error}`).join("\n"),
  );
  process.exit(1);
}

console.log(
  `Governance check passed (${requiredFiles.length} required paths, ${Object.keys(requiredDocumentText).length} root documents, pinned workflow actions, maintained branch policy).`,
);
