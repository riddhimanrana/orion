#!/usr/bin/env node

import { execFileSync } from "node:child_process";

const DEFAULT_SERVICE_NAME = process.env.RENDER_SERVICE_NAME || "Orion Signal Server";
const SERVICE_ID = process.env.RENDER_SERVICE_ID || "";
const WAIT_FOR_COMPLETION = (process.env.RENDER_WAIT_FOR_COMPLETION || "true") !== "false";
const CLEAR_CACHE = (process.env.RENDER_DEPLOY_CLEAR_CACHE || "false") === "true";
const POLL_INTERVAL_MS = Number(process.env.RENDER_DEPLOY_POLL_INTERVAL_MS || "10000");
const MAX_WAIT_MS = Number(process.env.RENDER_DEPLOY_MAX_WAIT_MS || "900000");

function runRender(args, { json = false } = {}) {
  const fullArgs = [...args, ...(json ? ["--output", "json"] : [])];
  const out = execFileSync("render", fullArgs, {
    encoding: "utf8",
    stdio: ["ignore", "pipe", "pipe"],
  });
  if (!json) return out;
  try {
    return JSON.parse(out);
  } catch {
    return out;
  }
}

function findServiceByIdOrName(servicesPayload) {
  const services = Array.isArray(servicesPayload) ? servicesPayload : [];
  const normalized = services
    .map((entry) => entry?.service)
    .filter(Boolean);

  if (SERVICE_ID) {
    const byId = normalized.find((s) => s.id === SERVICE_ID);
    if (!byId) throw new Error(`RENDER_SERVICE_ID not found: ${SERVICE_ID}`);
    return byId;
  }

  const byExactName = normalized.find((s) => s.name === DEFAULT_SERVICE_NAME);
  if (byExactName) return byExactName;

  const byLooseName = normalized.find((s) =>
    String(s.name || "").toLowerCase().includes("signal"),
  );
  if (byLooseName) return byLooseName;

  throw new Error(
    `Could not resolve service. Set RENDER_SERVICE_ID or RENDER_SERVICE_NAME (current default: ${DEFAULT_SERVICE_NAME}).`,
  );
}

function terminalStatus(status) {
  const s = String(status || "").toLowerCase();
  if (["live", "successful"].includes(s)) return "success";
  if (s.includes("failed") || s.includes("canceled") || s.includes("cancelled") || s.includes("error")) return "failed";
  return "pending";
}

async function sleep(ms) {
  await new Promise((resolve) => setTimeout(resolve, ms));
}

async function main() {
  console.log("🚀 Render deploy: Orion Signal\n");

  // Validate auth/session quickly
  const whoamiRaw = runRender(["whoami"], { json: false });
  const workspace = runRender(["workspace", "current"], { json: true });
  const whoamiLabel = String(whoamiRaw).trim().replace(/\s+/g, " ");
  console.log(`Authenticated as: ${whoamiLabel || "unknown"}`);
  console.log(`Workspace: ${workspace?.name || workspace?.slug || "unknown"}`);

  const servicesPayload = runRender(["services"], { json: true });
  const service = findServiceByIdOrName(servicesPayload);

  console.log(`Service: ${service.name} (${service.id})`);
  console.log(`Plan: ${service.plan || "unknown"}`);

  const createArgs = ["deploys", "create", service.id, "--confirm"];
  if (CLEAR_CACHE) createArgs.push("--clear-cache");

  if (WAIT_FOR_COMPLETION) {
    createArgs.push("--wait");
  }

  const createOut = runRender(createArgs, { json: false });
  if (String(createOut || "").trim().length > 0) {
    console.log(String(createOut).trim());
  }

  if (!WAIT_FOR_COMPLETION) {
    console.log("Skipping wait (RENDER_WAIT_FOR_COMPLETION=false)");
    return;
  }

  const initialDeploys = runRender(["deploys", "list", service.id], { json: true });
  const deploy = Array.isArray(initialDeploys) ? initialDeploys[0] : null;
  if (!deploy) {
    throw new Error("Could not resolve latest deploy after create");
  }

  console.log(`Latest deploy: ${deploy.id}`);
  console.log(`Status: ${deploy.status}`);

  const start = Date.now();
  while (Date.now() - start < MAX_WAIT_MS) {
    const deploys = runRender(["deploys", "list", service.id], { json: true });
    const current = Array.isArray(deploys)
      ? deploys.find((d) => d.id === deploy.id) || deploys[0]
      : null;

    if (!current) {
      console.log("Waiting for deploy to appear in list...");
      await sleep(POLL_INTERVAL_MS);
      continue;
    }

    const status = current.status;
    const phase = terminalStatus(status);
    console.log(`Deploy status: ${status}`);

    if (phase === "success") {
      console.log("✅ Deploy is live.");
      return;
    }
    if (phase === "failed") {
      throw new Error(`Deploy failed with status: ${status}`);
    }

    await sleep(POLL_INTERVAL_MS);
  }

  throw new Error("Timed out waiting for deploy to complete");
}

main().catch((err) => {
  console.error(`\n❌ Render deploy failed: ${err.message}`);
  process.exit(1);
});
