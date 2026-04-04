#!/usr/bin/env node

/**
 * Orion Signal connection/auth diagnostics
 *
 * Usage:
 *   npm run verify:connections
 *
 * Optional env vars:
 *   SIGNAL_BASE_URL=https://signal.orionlive.ai
 *   ORION_API_BASE_URL=https://orionlive.ai
 *   SIGNAL_BEARER_TOKEN=<jwt>              # enables authenticated /v1/ice, /v1/diag, /v1/account-usage checks
 *   RENDER_API_KEY=<render token>          # enables Render API check
 *   RENDER_SERVICE_ID=<render service id>  # required with RENDER_API_KEY
 */

const SIGNAL_BASE_URL = process.env.SIGNAL_BASE_URL || "https://signal.orionlive.ai";
const ORION_API_BASE_URL = process.env.ORION_API_BASE_URL || "https://orionlive.ai";
const SIGNAL_BEARER_TOKEN = process.env.SIGNAL_BEARER_TOKEN;
const RENDER_API_KEY = process.env.RENDER_API_KEY;
const RENDER_SERVICE_ID = process.env.RENDER_SERVICE_ID;

function printResult(label, ok, detail) {
  const icon = ok ? "✅" : "❌";
  console.log(`${icon} ${label}: ${detail}`);
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

async function checkSignalHealth() {
  const { res, body } = await jsonFetch(`${SIGNAL_BASE_URL}/health`);
  if (res.status !== 200) {
    throw new Error(`Expected 200 from /health, got ${res.status}`);
  }

  const status = body?.status;
  if (status !== "ok") {
    throw new Error(`Expected status=ok, got ${JSON.stringify(body)}`);
  }

  printResult("Signal health", true, `rooms=${body?.roomsActive ?? "?"}, clients=${body?.clientsConnected ?? "?"}`);
}

async function checkUnauthenticatedProtection() {
  const ice = await jsonFetch(`${SIGNAL_BASE_URL}/v1/ice`);
  const diag = await jsonFetch(`${SIGNAL_BASE_URL}/v1/diag`);
  const accountUsage = await jsonFetch(`${SIGNAL_BASE_URL}/v1/account-usage`);

  const iceOk = ice.res.status === 401;
  const diagOk = diag.res.status === 401;
  const usageOk = accountUsage.res.status === 401;

  printResult("/v1/ice requires auth", iceOk, `status=${ice.res.status}`);
  printResult("/v1/diag requires auth", diagOk, `status=${diag.res.status}`);
  printResult("/v1/account-usage requires auth", usageOk, `status=${accountUsage.res.status}`);

  if (!iceOk || !diagOk || !usageOk) {
    throw new Error("Auth guard check failed for one or more signal endpoints");
  }
}

async function checkAuthenticatedEndpoints() {
  if (!SIGNAL_BEARER_TOKEN) {
    console.log("ℹ️ Skipping authenticated /v1/ice, /v1/diag, /v1/account-usage checks (SIGNAL_BEARER_TOKEN not set)");
    return;
  }

  const headers = {
    Authorization: `Bearer ${SIGNAL_BEARER_TOKEN}`,
    Accept: "application/json",
  };

  const ice = await jsonFetch(`${SIGNAL_BASE_URL}/v1/ice`, { headers });
  const diag = await jsonFetch(`${SIGNAL_BASE_URL}/v1/diag`, { headers });
  const accountUsage = await jsonFetch(`${SIGNAL_BASE_URL}/v1/account-usage`, { headers });

  const iceOk = ice.res.status === 200 && Array.isArray(ice.body?.urls);
  const diagOk = diag.res.status === 200 && diag.body?.authenticated === true;
  const usageOk =
    accountUsage.res.status === 200 &&
    accountUsage.body?.authenticated === true &&
    accountUsage.body?.estimatedCostUsd?.totalUsd !== undefined;

  printResult("Authenticated /v1/ice", iceOk, `status=${ice.res.status}`);
  printResult("Authenticated /v1/diag", diagOk, `status=${diag.res.status}, roomClients=${diag.body?.room?.connectedClients ?? "?"}`);
  printResult(
    "Authenticated /v1/account-usage",
    usageOk,
    `status=${accountUsage.res.status}, estUsd=${accountUsage.body?.estimatedCostUsd?.totalUsd ?? "?"}`,
  );

  if (!iceOk || !diagOk || !usageOk) {
    throw new Error("Authenticated endpoint check failed");
  }
}

async function checkOrionTokenEndpointBehavior() {
  const { res } = await jsonFetch(`${ORION_API_BASE_URL}/api/auth/webrtc-token`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      Accept: "application/json",
    },
    body: JSON.stringify({ deviceId: "diagnostic-device" }),
  });

  // Without auth we expect rejection (typically 401/403), proving auth enforcement.
  const guarded = res.status === 401 || res.status === 403;
  printResult("Orion token endpoint auth guard", guarded, `status=${res.status}`);

  if (!guarded) {
    throw new Error(`Expected auth-protected token endpoint, got status ${res.status}`);
  }
}

async function checkRenderService() {
  if (!RENDER_API_KEY || !RENDER_SERVICE_ID) {
    console.log("ℹ️ Skipping Render API check (set RENDER_API_KEY and RENDER_SERVICE_ID to enable)");
    return;
  }

  const { res, body } = await jsonFetch(`https://api.render.com/v1/services/${RENDER_SERVICE_ID}`, {
    headers: {
      Accept: "application/json",
      Authorization: `Bearer ${RENDER_API_KEY}`,
    },
  });

  const ok = res.status === 200 && body?.id;
  printResult("Render service API", ok, `status=${res.status}, name=${body?.service?.name || body?.name || "unknown"}`);

  if (!ok) {
    throw new Error(`Render API check failed with status ${res.status}`);
  }
}

async function main() {
  console.log("🔍 Orion connection/auth diagnostics\n");
  console.log(`Signal base URL: ${SIGNAL_BASE_URL}`);
  console.log(`Orion API base URL: ${ORION_API_BASE_URL}`);

  await checkSignalHealth();
  await checkUnauthenticatedProtection();
  await checkAuthenticatedEndpoints();
  await checkOrionTokenEndpointBehavior();
  await checkRenderService();

  console.log("\n🎉 Diagnostics completed successfully.");
}

main().catch((err) => {
  console.error(`\n❌ Diagnostics failed: ${err.message}`);
  process.exit(1);
});
