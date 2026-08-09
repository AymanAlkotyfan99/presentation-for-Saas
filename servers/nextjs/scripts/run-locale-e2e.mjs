import { spawn } from "node:child_process";
import { resolve } from "node:path";

const port = 3310;
const environment = { ...process.env, PORT: String(port), NEXT_PUBLIC_FAST_API: "http://127.0.0.1:8000", NEXT_PUBLIC_URL: `http://127.0.0.1:${port}` };
delete environment.ELECTRON_RUN_AS_NODE;
const nextCli = resolve("node_modules", "next", "dist", "bin", "next");
const server = spawn(process.execPath, [nextCli, "start", "-p", String(port)], { env: environment, stdio: ["ignore", "pipe", "pipe"], windowsHide: true });

async function waitForServer() {
  for (let attempt = 0; attempt < 60; attempt += 1) {
    try {
      const response = await fetch(`http://127.0.0.1:${port}/en/a-route-that-does-not-exist`, { redirect: "manual" });
      if (response.status > 0) return;
    } catch {}
    await new Promise((resolvePromise) => setTimeout(resolvePromise, 500));
  }
  throw new Error("Next.js locale E2E server did not become ready");
}

try {
  await waitForServer();
  const cypressCli = resolve("node_modules", "cypress", "bin", "cypress");
  const cypress = spawn(process.execPath, [cypressCli, "run", "--e2e", "--browser", "electron", "--config", `baseUrl=http://127.0.0.1:${port}`], { env: environment, stdio: "inherit", windowsHide: true });
  const status = await new Promise((resolvePromise, reject) => {
    cypress.once("error", reject);
    cypress.once("exit", resolvePromise);
  });
  if (status !== 0) {
    console.error('localization_metric {"signal":"rtl_layout_test_failure","reason":"e2e_failure"}');
    process.exitCode = Number(status ?? 1);
  }
} finally {
  server.kill("SIGTERM");
}
