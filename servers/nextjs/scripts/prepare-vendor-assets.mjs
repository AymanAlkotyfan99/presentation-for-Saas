import { copyFileSync, mkdirSync } from "node:fs";
import { dirname, resolve } from "node:path";
import { fileURLToPath } from "node:url";

const nextRoot = resolve(dirname(fileURLToPath(import.meta.url)), "..");
const source = resolve(nextRoot, "node_modules/chart.js/dist/chart.umd.min.js");
const destinations = [
  resolve(nextRoot, "public/vendor/chart.umd.min.js"),
  resolve(nextRoot, "../fastapi/static/vendor/chart.umd.min.js"),
];

for (const destination of destinations) {
  mkdirSync(dirname(destination), { recursive: true });
  copyFileSync(source, destination);
}

console.log("Prepared locked Chart.js browser assets.");
