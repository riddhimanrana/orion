"use client";

import React from "react";
import { useSystemStatus } from "@/hooks/use-system-status";
import { CheckCircle, AlertCircle, XCircle, Settings } from "lucide-react";

interface SystemStatusProps {
  className?: string;
}

export const SystemStatus = ({ className }: SystemStatusProps) => {
  const { status, loading } = useSystemStatus();

  if (loading) {
    return (
      <div
        className={`inline-flex items-center space-x-2 px-3 py-2 bg-black/5 dark:bg-white/5 rounded-full border border-black/10 dark:border-white/10 ${className}`}
      >
        <div className="w-2 h-2 bg-gray-400 rounded-full animate-pulse"></div>
        <span className="text-black/60 dark:text-white/60 text-sm font-medium">
          Checking Status...
        </span>
      </div>
    );
  }

  const getStatusConfig = () => {
    switch (status.overall) {
      case "operational":
        return {
          icon: CheckCircle,
          text: "All systems operational",
          color: "text-green-500",
          bgColor: "bg-green-500",
        };
      case "degraded":
        return {
          icon: AlertCircle,
          text: "Some Systems Degraded",
          color: "text-yellow-500",
          bgColor: "bg-yellow-500",
        };
      case "outage":
        return {
          icon: XCircle,
          text: "System Outage",
          color: "text-red-500",
          bgColor: "bg-red-500",
        };
      case "maintenance":
        return {
          icon: Settings,
          text: "Under Maintenance",
          color: "text-blue-500",
          bgColor: "bg-blue-500",
        };
      default:
        return {
          icon: CheckCircle,
          text: "All Systems Operational",
          color: "text-green-500",
          bgColor: "bg-green-500",
        };
    }
  };

  const config = getStatusConfig();
  const StatusIcon = config.icon;

  return (
    <a
      href="https://status.orionlive.ai"
      target="_blank"
      rel="noopener noreferrer"
      className={`inline-flex items-center space-x-1 px-3 py-2 bg-black/5 dark:bg-white/5 rounded-full border border-black/10 dark:border-white/10 cursor-pointer transition hover:bg-black/10 dark:hover:bg-white/10 ${className}`}
      aria-label="View OrionLive system status"
    >
      <div className="flex items-center space-x-2 px-1">
        <div
          className={`w-2 h-2 ${config.bgColor} rounded-full ${status.overall === "operational" ? "animate-pulse" : ""}`}
        ></div>
        {/*<StatusIcon className={`w-3.5 h-3.5 ${config.color}`} />*/}
        <span className="text-black/60 dark:text-white/60 text-sm font-medium">
          {config.text}
        </span>
      </div>
    </a>
  );
};

export default SystemStatus;
