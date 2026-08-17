import http from "node:http";
import { spawn } from "node:child_process";
import { fileURLToPath } from "node:url";
import path from "node:path";

import { createMockProductApiServer } from "./mock-product-e2e-api.mjs";

const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..");
const host = "127.0.0.1";
const nextPort = 3310;
const apiPort = 8320;

function listen(server, port) {
  return new Promise((resolve, reject) => {
    server.once("error", reject);
    server.listen(port, host, resolve);
  });
}

function close(server) {
  return new Promise((resolve) => server.close(resolve));
}

async function waitForUrl(url, timeoutMs = 120_000) {
  const started = Date.now();
  let lastError;
  while (Date.now() - started < timeoutMs) {
    try {
      const response = await fetch(url, { redirect: "manual" });
      if (response.status > 0 && response.status < 500) return;
    } catch (error) {
      lastError = error;
    }
    await new Promise((resolve) => setTimeout(resolve, 500));
  }
  throw new Error(`Timed out waiting for ${url}: ${lastError || "no response"}`);
}

const apiServer = createMockProductApiServer();
let nextProcess;

try {
  await listen(apiServer, apiPort);
  nextProcess = spawn(process.execPath, [
    path.join(root, "node_modules", "next", "dist", "bin", "next"),
    "dev",
    "--webpack",
    "-H",
    host,
    "-p",
    String(nextPort),
  ], {
    cwd: root,
    env: {
      ...process.env,
      FAST_API_INTERNAL_URL: `http://${host}:${apiPort}`,
      NEXT_PUBLIC_FAST_API: "",
      NEXT_PUBLIC_URL: `http://${host}:${nextPort}`,
      CAN_CHANGE_KEYS: "false",
      DISABLE_AUTH: "false",
    },
    stdio: ["ignore", "inherit", "inherit"],
  });
  await waitForUrl(`http://${host}:${nextPort}/en`);

  const cypress = spawn(process.execPath, [
    path.join(root, "node_modules", "cypress", "bin", "cypress"),
    "run",
    "--e2e",
    "--browser",
    "electron",
    "--spec",
    "cypress/e2e/product-journeys.cy.ts",
    "--config",
    `baseUrl=http://${host}:${nextPort},video=false,screenshotOnRunFailure=false`,
  ], { cwd: root, env: process.env, stdio: "inherit" });

  const exitCode = await new Promise((resolve) => cypress.once("exit", resolve));
  if (exitCode !== 0) process.exitCode = typeof exitCode === "number" ? exitCode : 1;
} finally {
  if (nextProcess && !nextProcess.killed) nextProcess.kill("SIGTERM");
  await close(apiServer);
}
