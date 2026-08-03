/**
 * Docker / startup terminal banner. The exported function name is retained as
 * a compatibility API for start.js; display identity comes from the registry.
 * Renders a compact brand logo + startup status.
 */

import fs from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";

const RESET = "\x1b[0m";
const BOLD = "\x1b[1m";
const DIM = "\x1b[2m";
const thisDir = path.dirname(fileURLToPath(import.meta.url));
const PRODUCT_IDENTITY = JSON.parse(
  fs.readFileSync(path.join(thisDir, "..", "config", "product-identity.json"), "utf8"),
);

function hexRgb(value) {
  const hex = value.slice(1);
  return [0, 2, 4].map((index) => Number.parseInt(hex.slice(index, index + 2), 16));
}

const PRIMARY_RGB = hexRgb(PRODUCT_IDENTITY.colors.primary);
const SECONDARY_RGB = hexRgb(PRODUCT_IDENTITY.colors.secondary);

function fgRgb(r, g, b, text) {
  return `\x1b[38;2;${r};${g};${b}m${text}${RESET}`;
}

function brand(text) {
  return BOLD + fgRgb(...PRIMARY_RGB, text);
}

function accent(text) {
  return fgRgb(...SECONDARY_RGB, text);
}

function muted(text) {
  return DIM + fgRgb(148, 163, 184, text);
}

function styleAsciiArt(rawAscii) {
  const lines = rawAscii.replace(/\r/g, "").split("\n");
  const palette = [PRIMARY_RGB, SECONDARY_RGB];

  return lines
    .map((line, lineIdx) => {
      const [r, g, b] = palette[lineIdx % palette.length];
      return line.replace(/[^\s]/g, (ch) => fgRgb(r, g, b, ch));
    })
    .join("\n");
}

function loadAsciiBanner() {
  return styleAsciiArt(`  ${PRODUCT_IDENTITY.product.name}`);
}

function loadPackageVersion() {
  const packageJsonPath = path.join(thisDir, "..", "package.json");

  try {
    const pkg = JSON.parse(fs.readFileSync(packageJsonPath, "utf8"));
    return typeof pkg.version === "string" ? pkg.version : "";
  } catch {
    return "";
  }
}

/** Visible width (strips SGR sequences). */
function visLen(s) {
  return s.replace(/\x1b\[[0-9;:]*m/g, "").length;
}

/** Pad styled fragment to fixed visible width. */
function padVis(styled, width) {
  return styled + " ".repeat(Math.max(0, width - visLen(styled)));
}

/**
 * @param {object} [opts]
 * @param {"development" | "production"} [opts.mode]
 * @param {number} [opts.nextPort]
 * @param {number} [opts.fastapiPort]
 * @param {string} [opts.hostHttpPort] — host-published HTTP port (docker -p HOST:80). Default from env or "5001".
 */
export function printPresentonStartupBanner(opts = {}) {
  const mode = opts.mode === "development" ? "development" : "production";
  const nextPort = opts.nextPort ?? 3000;
  const fastapiPort = opts.fastapiPort ?? 8000;
  const version = opts.version ?? loadPackageVersion();
  const hostHttpPort =
    opts.hostHttpPort ??
    process.env.PRESENTON_HTTP_HOST_PORT ??
    process.env.PRESENTON_HOST_HTTP_PORT ??
    process.env.PRESENTON_PUBLIC_PORT ??
    "5001";

  const nextUrl = `http://127.0.0.1:${nextPort}`;
  const apiUrl = `http://127.0.0.1:${fastapiPort}`;
  const publicUrl =
    String(hostHttpPort) === "80"
      ? "http://127.0.0.1"
      : `http://127.0.0.1:${hostHttpPort}`;

  const iconBlock = loadAsciiBanner();

  const title = [
    "",
    BOLD + fgRgb(...PRIMARY_RGB, `   ${PRODUCT_IDENTITY.product.description}`),
    ...(mode === "development"
      ? [
          "   " +
            accent("Love the Project?  ") +
            brand("Upstream repository: ") +
            BOLD +
            fgRgb(224, 218, 255, "https://github.com/presenton/presenton"),
        ]
      : []),
    muted("   ─────────────────────────────────────────────────────────"),
    "",
  ].join("\n");

  const W = 68;
  const pipe = (inner) => brand("  ║") + inner + brand("║");

  const boxTop = brand(
    "  ╔════════════════════════════════════════════════════════════════════╗",
  );
  const boxDivider = brand(
    "  ╠════════════════════════════════════════════════════════════════════╣",
  );
  const boxBottom = brand(
    "  ╚════════════════════════════════════════════════════════════════════╝",
  );

  const summaryLines =
    mode === "development"
      ? [
          pipe(padVis("  " + BOLD + "Routing summary" + RESET, W)),
          boxDivider,
          pipe(padVis("  " + muted("Mode:                 ") + mode, W)),
          ...(version
            ? [pipe(padVis("  " + muted("Version:              ") + version, W))]
            : []),
          pipe(padVis("  " + accent("/         ") + muted("→ Next.js"), W)),
          pipe(padVis("  " + accent("/api/v1/  ") + muted("→ FastAPI"), W)),
          pipe(padVis("  " + muted("Next.js docker URL: ") + nextUrl, W)),
          pipe(padVis("  " + muted("FastAPI docker URL:     ") + apiUrl, W)),
          pipe(
            padVis(
              "  " +
                muted("Public URL (Ctrl+Click to open):     ") +
                BOLD +
                fgRgb(255, 255, 255, publicUrl),
              W,
            ),
          ),
        ]
      : [
          pipe(padVis("  " + BOLD + "Application URL" + RESET, W)),
          boxDivider,
          pipe(padVis("  " + muted("Mode:             ") + mode, W)),
          ...(version
            ? [pipe(padVis("  " + muted("Version:          ") + version, W))]
            : []),
          pipe(
            padVis(
              "  " +
                muted(`Open ${PRODUCT_IDENTITY.product.shortName}:     `) +
                BOLD +
                fgRgb(255, 255, 255, publicUrl),
              W,
            ),
          ),
        ];

  const summary = [
    boxTop,
    ...summaryLines,
    boxBottom,
    "",
    "   " + muted(`Support: ${PRODUCT_IDENTITY.product.supportEmail}`),
  ].join("\n");

  const bannerHeader = iconBlock ? `${iconBlock}\n` : "";
  console.log("\n" + bannerHeader + title + summary);
}
