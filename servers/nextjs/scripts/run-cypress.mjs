import { spawnSync } from "node:child_process";
import { resolve } from "node:path";

// Electron desktop development can set this flag for its Node bridge. Cypress
// launches its own Electron binary, where inheriting the flag makes that binary
// reject Cypress's smoke-test arguments. Keep the component runner hermetic.
const environment = { ...process.env };
delete environment.ELECTRON_RUN_AS_NODE;

const cypressCli = resolve("node_modules", "cypress", "bin", "cypress");
const result = spawnSync(
  process.execPath,
  [cypressCli, "run", "--component", "--browser", "electron"],
  {
    env: environment,
    stdio: "inherit",
  },
);

if (result.error) throw result.error;
process.exit(result.status ?? 1);
