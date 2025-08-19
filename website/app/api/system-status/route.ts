import { NextResponse } from "next/server";

export interface SystemStatusResponse {
  overall: "operational" | "degraded" | "outage" | "maintenance";
  services: Array<{
    name: string;
    status: "operational" | "degraded" | "outage" | "maintenance";
  }>;
  lastUpdated: string;
}

const DEFAULT_STATUS: SystemStatusResponse = {
  overall: "operational",
  services: [],
  lastUpdated: new Date().toISOString(),
};

export async function GET() {
  try {
    const apiKey = process.env.BETTERSTACK_UPTIME_STATUS_KEY;

    if (!apiKey) {
      // Return default operational status if no API key is configured
      return NextResponse.json(DEFAULT_STATUS);
    }

    const response = await fetch(
      "https://uptime.betterstack.com/api/v2/monitors",
      {
        headers: {
          Authorization: `Bearer ${apiKey}`,
          "Content-Type": "application/json",
        },
        // Cache for 2 minutes to avoid too many requests
        next: { revalidate: 120 },
      },
    );

    if (!response.ok) {
      console.error(
        `BetterStack API error: ${response.status} ${response.statusText}`,
      );
      return NextResponse.json(DEFAULT_STATUS);
    }

    const data = await response.json();

    // Process the response to determine overall status
    const services =
      data.data?.map(
        (monitor: {
          attributes?: {
            friendly_name?: string;
            url?: string;
            status?: string;
          };
        }) => ({
          name:
            monitor.attributes?.friendly_name ||
            monitor.attributes?.url ||
            "Unknown Service",
          status: mapBetterStackStatus(monitor.attributes?.status),
        }),
      ) || [];

    const overall = determineOverallStatus(services);

    const statusResponse: SystemStatusResponse = {
      overall,
      services,
      lastUpdated: new Date().toISOString(),
    };

    return NextResponse.json(statusResponse);
  } catch (error) {
    console.error("Failed to fetch system status:", error);
    return NextResponse.json(DEFAULT_STATUS);
  }
}

function mapBetterStackStatus(
  betterStackStatus?: string,
): SystemStatusResponse["overall"] {
  switch (betterStackStatus?.toLowerCase()) {
    case "up":
    case "operational":
      return "operational";
    case "down":
    case "outage":
      return "outage";
    case "degraded":
    case "partial_outage":
      return "degraded";
    case "maintenance":
    case "under_maintenance":
      return "maintenance";
    default:
      return "operational";
  }
}

function determineOverallStatus(
  services: SystemStatusResponse["services"],
): SystemStatusResponse["overall"] {
  if (services.length === 0) return "operational";

  const hasOutage = services.some((s) => s.status === "outage");
  const hasMaintenance = services.some((s) => s.status === "maintenance");
  const hasDegraded = services.some((s) => s.status === "degraded");

  if (hasOutage) return "outage";
  if (hasMaintenance) return "maintenance";
  if (hasDegraded) return "degraded";

  return "operational";
}
