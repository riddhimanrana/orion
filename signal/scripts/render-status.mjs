#!/usr/bin/env node

import { execFileSync } from "node:child_process";

const SIGNAL_BASE_URL = process.env.SIGNAL_BASE_URL || "https://signal.orionlive.ai";
const SIGNAL_BEARER_TOKEN = process.env.SIGNAL_BEARER_TOKEN || "";
const SERVICE_ID = process.env.RENDER_SERVICE_ID || "";
const SERVICE_NAME = process.env.RENDER_SERVICE_NAME || "Orion Signal Server";

const PLAN_COST_ESTIMATE = {
  free: 0,
  starter: 7,
  standard: 25,
  pro: 85,
  plus: 225,
};

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

async function jsonFetch(url, options = {}) {
  const res = await fetch(url, options);
  const text = await res.text();
  let body;
  try {
    body = text ? JSON.parse(text) : null;
  } catch {
    body = text;
  }
  return { res, body };
}

function printSection(title) {
  console.log(`\n=== ${title} ===`);
}

function resolveService(servicesPayload) {
  const services = Array.isArray(servicesPayload) ? servicesPayload : [];
  const normalized = services.map((entry) => entry?.service).filter(Boolean);

  if (SERVICE_ID) {
    const byId = normalized.find((s) => s.id === SERVICE_ID);
    if (!byId) throw new Error(`Service id not found: ${SERVICE_ID}`);
    return byId;
  }

  return (
    normalized.find((s) => s.name === SERVICE_NAME) ||
    normalized.find((s) => String(s.name || "").toLowerCase().includes("signal"))
  );
}

async function main() {
  printSection("Render context");
  const whoamiRaw = runRender(["whoami"], { json: false });
  const workspace = runRender(["workspace", "current"], { json: true });
  const whoamiLabel = String(whoamiRaw).trim().replace(/\s+/g, " ");
  console.log(`User: ${whoamiLabel || "unknown"}`);
  console.log(`Workspace: ${workspace?.name || workspace?.slug || "unknown"}`);

  const servicesPayload = runRender(["services"], { json: true });
  const service = resolveService(servicesPayload);
  if (!service) throw new Error("Could not resolve Orion signal service");

  printSection("Render service");
  console.log(`Name: ${service.name}`);
  console.log(`ID: ${service.id}`);
  console.log(`Type: ${service.type}`);
  console.log(`Plan: ${service.plan || "unknown"}`);
  console.log(`URL: ${service.serviceDetails?.url || "n/a"}`);
  const planKey = String(service.plan || "").toLowerCase();
  const monthly = PLAN_COST_ESTIMATE[planKey];
  if (monthly !== undefined) {
    console.log(`Estimated infra plan cost/month: $${monthly.toFixed(2)} (approx)`);
  } else {
    console.log("Estimated infra plan cost/month: unknown plan tier");
  }

  printSection("Deploy status");
  const deploys = runRender(["deploys", "list", service.id], { json: true });
  const latest = Array.isArray(deploys) ? deploys[0] : null;
  if (latest) {
    console.log(`Latest deploy: ${latest.id}`);
    console.log(`Status: ${latest.status}`);
    console.log(`Created: ${latest.createdAt || "n/a"}`);
    console.log(`Updated: ${latest.updatedAt || "n/a"}`);
    console.log(`Commit: ${latest.commit?.id || "n/a"}`);
  } else {
    console.log("No deploys found");
  }

  printSection("Signal API health");
  const health = await jsonFetch(`${SIGNAL_BASE_URL}/health`);
  console.log(`GET /health => ${health.res.status}`);
  if (health.res.status === 200 && typeof health.body === "object") {
    console.log(`roomsActive=${health.body.roomsActive ?? "?"}, clientsConnected=${health.body.clientsConnected ?? "?"}, bytesRelayed=${health.body.bytesRelayed ?? "?"}`);
  }

  printSection("Account usage");
  if (!SIGNAL_BEARER_TOKEN) {
    console.log("Skipped authenticated usage check (set SIGNAL_BEARER_TOKEN). ");
  } else {
    const usage = await jsonFetch(`${SIGNAL_BASE_URL}/v1/account-usage`, {
      headers: {
        Authorization: `Bearer ${SIGNAL_BEARER_TOKEN}`,
        Accept: "application/json",
      },
    });
    console.log(`GET /v1/account-usage => ${usage.res.status}`);
    if (usage.res.status === 200 && typeof usage.body === "object") {
      console.log(`packetsRelayed=${usage.body.usage?.packetsRelayed ?? "?"}, bytesRelayed=${usage.body.usage?.bytesRelayed ?? "?"}, estTotalUsd=${usage.body.estimatedCostUsd?.totalUsd ?? "?"}`);
    }
  }
}

main().catch((err) => {
  console.error(`\n❌ render-status failed: ${err.message}`);
  process.exit(1);
});
