const fs = require("fs");
const path = require("path");

const electronRoot = path.join(__dirname, "..");
const identity = JSON.parse(
  fs.readFileSync(path.join(electronRoot, "..", "config", "product-identity.json"), "utf8"),
);
const pkg = JSON.parse(
  fs.readFileSync(path.join(electronRoot, "package.json"), "utf8"),
);
let existing = {};
try {
  existing = JSON.parse(
    fs.readFileSync(path.join(electronRoot, "version.json"), "utf8"),
  );
} catch (_) {}

const version = pkg.version;

const update = {
  version,
  message: process.env.UPDATE_MESSAGE || existing.message || "",
  downloads: {
    linux: existing.downloads?.linux || identity.desktop.compatibilityDownloadUrl,
    mac: existing.downloads?.mac || identity.desktop.compatibilityDownloadUrl,
    windows: existing.downloads?.windows || identity.desktop.compatibilityDownloadUrl,
  },
};

fs.writeFileSync(
  path.join(electronRoot, "version.json"),
  JSON.stringify(update, null, 2),
);

console.log("version.json generated");
