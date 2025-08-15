"use client";

import { useState, useEffect } from "react";
import { Badge } from "@/components/ui/badge";
import { Wifi, WifiOff, Loader2 } from "lucide-react";

type Status = "connecting" | "connected" | "disconnected";

export function P2PStatusIndicator() {
  const [status, setStatus] = useState<Status>("connecting");

  useEffect(() => {
    const checkStatus = async () => {
      // Don't change status if it's already connecting from a previous check
      setStatus((prev) => (prev === "connected" ? "connecting" : prev));

      try {
        const healthUrl = `${process.env.NEXT_PUBLIC_P2P_SIGNAL_URL || 'ws://localhost:3001'}/health`.replace(/^ws/, 'http');
        const response = await fetch(healthUrl, { method: 'GET', cache: 'no-store' });
        
        if (response.ok) {
          const data = await response.json();
          if (data.status === 'ok') {
            setStatus("connected");
            return;
          }
        }
        setStatus("disconnected");
      } catch (error) {
        setStatus("disconnected");
      }
    };

    // Initial check
    checkStatus();

    // Periodically check status every 15 seconds
    const interval = setInterval(checkStatus, 15000);

    // Cleanup on component unmount
    return () => clearInterval(interval);
  }, []);

  const getStatusContent = () => {
    switch (status) {
      case "connecting":
        return (
          <Badge variant="outline" className="text-amber-600 border-amber-600">
            <Loader2 className="h-3 w-3 mr-1 animate-spin" />
            Connecting...
          </Badge>
        );
      case "connected":
        return (
          <Badge variant="outline" className="text-green-600 border-green-600">
            <Wifi className="h-3 w-3 mr-1" />
            Signaling: Connected
          </Badge>
        );
      case "disconnected":
      default:
        return (
          <Badge variant="destructive">
            <WifiOff className="h-3 w-3 mr-1" />
            Signaling: Disconnected
          </Badge>
        );
    }
  };

  return <div className="flex items-center space-x-2">{getStatusContent()}</div>;
}