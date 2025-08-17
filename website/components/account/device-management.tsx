"use client";

import { useState, useEffect } from "react";
import {
  getPairedDevices,
  getRegisteredDevices,
  revokeDevicePairForm,
} from "@/app/account/actions";
import { P2PStatusIndicator } from "./p2p-status-indicator";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import {
  Smartphone,
  Monitor,
  Trash2,
  Link as LinkIcon,
  Info,
  AlertCircle,
  CheckCircle2,
  ArrowRightLeft,
} from "lucide-react";
import { Badge } from "@/components/ui/badge";
import { Skeleton } from "@/components/ui/loading";
import { Alert, AlertDescription } from "@/components/ui/alert";
import { Separator } from "@/components/ui/separator";

interface Device {
  id: string;
  name: string;
  type: "ios" | "mac";
  created_at: string;
  user_id: string;
}

interface DevicePair {
  id: string;
  status: string;
  created_at: string;
  revoked_at: string | null;
  mobile_device: Device | Device[] | null;
  server_device: Device | Device[] | null;
}

function DeviceManagement() {
  const [pairs, setPairs] = useState<DevicePair[] | null>(null);
  const [allDevices, setAllDevices] = useState<Device[] | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    const fetchData = async () => {
      try {
        const [pairedData, devicesData] = await Promise.all([
          getPairedDevices(),
          getRegisteredDevices(),
        ]);
        console.log("Paired data:", pairedData);
        setPairs(pairedData);
        setAllDevices(devicesData);
      } catch (err) {
        console.error("Failed to fetch device data:", err);
        setError("Failed to load device data. Please try refreshing the page.");
      } finally {
        setLoading(false);
      }
    };

    fetchData();
  }, []);

  const DeviceLoadingSkeleton = () => (
    <div className="space-y-6">
      <div className="space-y-4">
        <Skeleton className="h-6 w-32" />
        <div className="p-6 border rounded-xl space-y-4">
          <div className="flex items-center justify-between">
            <div className="flex items-center space-x-6">
              <div className="flex items-center space-x-3">
                <Skeleton className="h-6 w-6 rounded" />
                <Skeleton className="h-4 w-24" />
              </div>
              <Skeleton className="h-4 w-4" />
              <div className="flex items-center space-x-3">
                <Skeleton className="h-6 w-6 rounded" />
                <Skeleton className="h-4 w-28" />
              </div>
            </div>
            <Skeleton className="h-9 w-20" />
          </div>
        </div>
      </div>
      <div className="space-y-4">
        <Skeleton className="h-6 w-40" />
        <div className="space-y-3">
          {[1, 2, 3].map((i) => (
            <div
              key={i}
              className="flex items-center justify-between p-4 border rounded-xl"
            >
              <div className="flex items-center space-x-4">
                <Skeleton className="h-6 w-6 rounded" />
                <div className="space-y-2">
                  <Skeleton className="h-4 w-32" />
                  <Skeleton className="h-3 w-24" />
                </div>
              </div>
              <Skeleton className="h-6 w-16 rounded-full" />
            </div>
          ))}
        </div>
      </div>
    </div>
  );

  if (loading) {
    return (
      <Card className="border-0 shadow-sm">
        <CardHeader className="pb-4">
          <CardTitle className="flex items-center text-xl">
            <LinkIcon className="w-5 h-5 mr-3 text-primary" />
            Device Management
          </CardTitle>
          <CardDescription className="text-sm">
            Manage your connected iOS and macOS devices.
          </CardDescription>
        </CardHeader>
        <CardContent>
          <DeviceLoadingSkeleton />
        </CardContent>
      </Card>
    );
  }

  if (error) {
    return (
      <Card className="border-0 shadow-sm">
        <CardHeader className="pb-4">
          <CardTitle className="flex items-center text-xl">
            <LinkIcon className="w-5 h-5 mr-3 text-primary" />
            Device Management
          </CardTitle>
          <CardDescription className="text-sm">
            Manage your connected iOS and macOS devices.
          </CardDescription>
          <P2PStatusIndicator />
        </CardHeader>
        <CardContent>
          <Alert
            variant="destructive"
            className="border-red-200 bg-red-50 dark:bg-red-950/50"
          >
            <AlertCircle className="h-4 w-4" />
            <AlertDescription className="text-sm font-medium">
              {error}
            </AlertDescription>
          </Alert>
        </CardContent>
      </Card>
    );
  }

  const pairedDeviceIds = new Set([
    ...(pairs
      ?.flatMap((p) => [
        Array.isArray(p.mobile_device)
          ? p.mobile_device[0]?.id
          : p.mobile_device?.id,
        Array.isArray(p.server_device)
          ? p.server_device[0]?.id
          : p.server_device?.id,
      ])
      .filter(Boolean) || []),
  ]);

  return (
    <Card className="border-0 shadow-sm">
      <CardHeader className="pb-4">
        <CardTitle className="flex items-center text-xl">
          <LinkIcon className="w-5 h-5 mr-3 text-primary" />
          Device Management
        </CardTitle>
        <CardDescription className="text-sm">
          Manage your connected iOS and macOS devices and their pairing status.
        </CardDescription>
        <P2PStatusIndicator />
      </CardHeader>
      <CardContent className="space-y-8">
        {/* Active Pairs Section */}
        <div className="space-y-4">
          <div className="flex items-center space-x-2">
            <CheckCircle2 className="h-5 w-5 text-green-600" />
            <h3 className="text-lg font-semibold">Active Pairs</h3>
          </div>

          {pairs && pairs.length > 0 ? (
            <div className="space-y-4">
              {pairs.map((pair) => (
                <div
                  key={pair.id}
                  className="relative p-6 border rounded-xl bg-gradient-to-r from-green-50 to-emerald-50 dark:from-green-950/20 dark:to-emerald-950/20 border-green-200 dark:border-green-800"
                >
                  <div className="flex items-center justify-between">
                    <div className="flex items-center space-x-6">
                      <div className="flex items-center space-x-3">
                        <div className="p-2 bg-gray-50 dark:bg-gray-800/50 rounded-lg shadow-sm border border-gray-100 dark:border-gray-700/50">
                          <Smartphone className="h-5 w-5 text-gray-400 dark:text-gray-300" />
                        </div>
                        <div>
                          <p className="font-medium text-gray-900 dark:text-gray-100">
                            {(Array.isArray(pair.mobile_device)
                              ? pair.mobile_device[0]?.name
                              : pair.mobile_device?.name) ||
                              "Unknown Mobile Device"}
                          </p>
                          <p className="text-xs text-gray-500">iOS Device</p>
                        </div>
                      </div>

                      <div className="flex items-center">
                        <ArrowRightLeft className="h-5 w-5 text-green-600" />
                      </div>

                      <div className="flex items-center space-x-3">
                        <div className="p-2 bg-gray-50 dark:bg-gray-800/50 rounded-lg shadow-sm border border-gray-100 dark:border-gray-700/50">
                          <Monitor className="h-5 w-5 text-gray-400 dark:text-gray-300" />
                        </div>
                        <div>
                          <p className="font-medium text-gray-900 dark:text-gray-100">
                            {(Array.isArray(pair.server_device)
                              ? pair.server_device[0]?.name
                              : pair.server_device?.name) ||
                              "Unknown Server Device"}
                          </p>
                          <p className="text-xs text-gray-500">macOS Device</p>
                        </div>
                      </div>
                    </div>

                    <form action={revokeDevicePairForm}>
                      <input type="hidden" name="pairId" value={pair.id} />
                      <Button
                        variant="destructive"
                        size="sm"
                        className="shadow-sm"
                      >
                        <Trash2 className="h-4 w-4 mr-2" />
                        Revoke
                      </Button>
                    </form>
                  </div>
                </div>
              ))}
            </div>
          ) : (
            <div className="text-center py-12 px-6 border-2 border-dashed border-gray-200 dark:border-gray-800 rounded-xl bg-gray-50/50 dark:bg-gray-900/20">
              <div className="w-16 h-16 mx-auto mb-4 bg-gray-100 dark:bg-gray-800 rounded-full flex items-center justify-center">
                <LinkIcon className="w-8 h-8 text-gray-400" />
              </div>
              <p className="text-sm font-medium text-gray-900 dark:text-gray-100 mb-2">
                No devices are currently paired
              </p>
              <p className="text-xs text-gray-500 max-w-sm mx-auto">
                Use the Orion mobile and desktop apps to create device pairs for
                seamless synchronization.
              </p>
            </div>
          )}
        </div>

        <Separator className="my-6" />

        {/* All Devices Section */}
        <div className="space-y-4">
          <div className="flex items-center justify-between">
            <div className="flex items-center space-x-2">
              <Info className="h-5 w-5 text-blue-600" />
              <h3 className="text-lg font-semibold">All Registered Devices</h3>
            </div>
            {allDevices && (
              <Badge variant="secondary" className="text-xs">
                {allDevices.length} device{allDevices.length !== 1 ? "s" : ""}
              </Badge>
            )}
          </div>

          {allDevices && allDevices.length > 0 ? (
            <div className="grid gap-3">
              {allDevices.map((device) => (
                <div
                  key={device.id}
                  className="group flex items-center justify-between p-4 border rounded-xl hover:bg-gray-50 dark:hover:bg-gray-900/20 transition-colors"
                >
                  <div className="flex items-center space-x-4">
                    <div className="p-2 bg-gray-50 dark:bg-gray-800/50 rounded-lg border border-gray-100 dark:border-gray-700/20">
                      {device.type === "ios" ? (
                        <Smartphone className="h-5 w-5 text-gray-400 dark:text-gray-300" />
                      ) : (
                        <Monitor className="h-5 w-5 text-gray-400 dark:text-gray-300" />
                      )}
                    </div>
                    <div>
                      <p className="font-medium text-gray-900 dark:text-gray-100">
                        {device.name}
                      </p>
                      <p className="text-xs text-gray-500">
                        Registered{" "}
                        {new Date(device.created_at).toLocaleDateString(
                          "en-US",
                          {
                            year: "numeric",
                            month: "short",
                            day: "numeric",
                          },
                        )}
                      </p>
                    </div>
                  </div>

                  <div className="flex items-center space-x-3">
                    {pairedDeviceIds.has(device.id) ? (
                      <Badge className="bg-green-100 text-green-800 dark:bg-green-900 dark:text-green-200 border-green-200 dark:border-green-800">
                        <CheckCircle2 className="h-3 w-3 mr-1" />
                        Paired
                      </Badge>
                    ) : (
                      <Badge variant="secondary" className="text-gray-600">
                        Available
                      </Badge>
                    )}
                  </div>
                </div>
              ))}
            </div>
          ) : (
            <div className="text-center py-8 px-6 border border-gray-200 dark:border-gray-800 rounded-xl bg-gray-50/30 dark:bg-gray-900/20">
              <p className="text-sm text-gray-500">
                No devices have been registered yet. Install the Orion app on
                your devices to get started.
              </p>
            </div>
          )}
        </div>
      </CardContent>
    </Card>
  );
}

export { DeviceManagement };
