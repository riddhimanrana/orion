"use client";

import { useState, useEffect } from "react";

export interface SystemStatus {
  overall: "operational" | "degraded" | "outage" | "maintenance";
  services: Array<{
    name: string;
    status: "operational" | "degraded" | "outage" | "maintenance";
  }>;
  lastUpdated: Date;
}

const DEFAULT_STATUS: SystemStatus = {
  overall: "operational",
  services: [],
  lastUpdated: new Date(),
};

export function useSystemStatus() {
  const [status, setStatus] = useState<SystemStatus>(DEFAULT_STATUS);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    const fetchStatus = async () => {
      try {
        setLoading(true);
        setError(null);

        const response = await fetch("/api/system-status");

        if (!response.ok) {
          throw new Error(`HTTP error! status: ${response.status}`);
        }

        const data = await response.json();

        setStatus({
          overall: data.overall,
          services: data.services,
          lastUpdated: new Date(data.lastUpdated),
        });
      } catch (err) {
        console.error("Failed to fetch system status:", err);
        setError(err instanceof Error ? err.message : "Failed to fetch status");
        // Fallback to default status on error
        setStatus(DEFAULT_STATUS);
      } finally {
        setLoading(false);
      }
    };

    fetchStatus();

    // Refresh status every 5 minutes
    const interval = setInterval(fetchStatus, 5 * 60 * 1000);

    return () => clearInterval(interval);
  }, []);

  return { status, loading, error };
}
