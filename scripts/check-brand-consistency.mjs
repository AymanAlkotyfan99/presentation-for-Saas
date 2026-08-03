import fs from "node:fs";
import path from "node:path";
import process from "node:process";
import { spawnSync } from "node:child_process";
import { fileURLToPath } from "node:url";

const ROOT = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..");
const identity = JSON.parse(fs.readFileSync(path.join(ROOT, "config/product-identity.json"), "utf8"));
const errors = [];
const read = (file) => fs.readFileSync(path.join(ROOT, file), "utf8");
const exists = (file) => fs.existsSync(path.join(ROOT, file));

const generation = spawnSync(process.execPath, [path.join(ROOT, "scripts/generate-product-metadata.mjs"), "--check"], { encoding: "utf8" });
if (generation.status !== 0) errors.push((generation.stderr || generation.stdout).trim());

const requiredAssets = [
  "primaryLogo", "lightLogo", "darkLogo", "compactIcon", "favicon", "splash",
];
for (const key of requiredAssets) {
  const name = identity.assets[key];
  if (!exists(`servers/nextjs/public/brand/v1/${name}`)) errors.push(`missing web asset ${name}`);
}
if (!exists(`electron/build/brand/v1/${identity.assets.desktopIcon}`)) errors.push("missing Electron desktop icon");

const approvedCopies = [
  ["assets/branding/PRIMARY_LOGO.png", `servers/nextjs/public/brand/v1/${identity.assets.primaryLogo}`],
  ["assets/branding/LIGHT_LOGO.png", `servers/nextjs/public/brand/v1/${identity.assets.lightLogo}`],
  ["assets/branding/DARK_LOGO.png", `servers/nextjs/public/brand/v1/${identity.assets.darkLogo}`],
  ["assets/branding/COMPACT_ICON.png", `servers/nextjs/public/brand/v1/${identity.assets.compactIcon}`],
  ["assets/branding/FAVICON.png", `servers/nextjs/public/brand/v1/${identity.assets.favicon}`],
  ["assets/branding/SPLASH_IMAGE.png", `servers/nextjs/public/brand/v1/${identity.assets.splash}`],
  ["assets/branding/DESKTOP_ICON.png", `electron/build/brand/v1/${identity.assets.desktopIcon}`],
  ["assets/branding/DESKTOP_ICON.png", "electron/resources/ui/assets/images/brand/v1/desktop-icon.png"],
];
for (const [source, destination] of approvedCopies) {
  if (!exists(source) || !exists(destination)) continue;
  if (!fs.readFileSync(path.join(ROOT, source)).equals(fs.readFileSync(path.join(ROOT, destination)))) {
    errors.push(`${destination} is not a byte-for-byte copy of approved asset ${source}`);
  }
}

const readme = read("README.md");
if (!readme.includes("Bayanly AI")) errors.push("README does not identify Bayanly AI");
if (!/derived (?:work based on|from)[\s\S]{0,180}Presenton/i.test(readme)) errors.push("README lacks explicit Presenton derivation attribution");
if (!read("NOTICE").includes("Presenton upstream project")) errors.push("NOTICE lacks upstream attribution");
if (!exists("LICENSE")) errors.push("LICENSE is missing");

const webIdentitySurfaces = [
  "servers/nextjs/app/layout.tsx", "servers/nextjs/app/not-found.tsx",
  "servers/nextjs/app/(presentation-generator)/upload/page.tsx",
  "servers/nextjs/components/Header.tsx",
  "servers/nextjs/app/(presentation-generator)/(dashboard)/Components/DashboardSidebar.tsx",
  "servers/nextjs/app/(presentation-generator)/(dashboard)/dashboard/components/Header.tsx",
];
for (const file of webIdentitySurfaces) {
  const source = read(file);
  if (/PresentOn|Presenton/.test(source)) errors.push(`${file} contains legacy user-facing brand text`);
  if (/\/(?:logo-with-bg|logo-white|Logo|Presenton_Splash)\.png/.test(source)) errors.push(`${file} references a legacy brand asset`);
}

const electronPackage = JSON.parse(read("electron/package.json"));
if (electronPackage.productName !== identity.desktop.requestedName) errors.push("Electron productName is not registry-driven value");
const buildSource = read("electron/build.js");
if (!buildSource.includes("identity.desktop.activeAppId")) errors.push("Electron build does not use the compatibility app ID from registry");
if (!buildSource.includes("identity.desktop.requestedName")) errors.push("Electron build does not use requested display name");

if (process.argv.includes("--production")) {
  if (identity.web.isPlaceholder) errors.push("production release blocked: web domain is still a placeholder");
  if (identity.publisher.legalStatus !== "CLEARED") errors.push("production release blocked: publisher identity lacks legal clearance");
  if (identity.desktop.updateStatus !== "CONFIGURED") errors.push("production release blocked: update channel is not configured");
}

if (errors.length) {
  console.error("Brand consistency check failed:\n" + errors.map((error) => `  - ${error}`).join("\n"));
  process.exit(1);
}
console.log("Brand consistency check passed (placeholder/legal/update release gates remain explicit)." );
