"use client";

import { useState } from "react";
import { useUser } from "@/hooks/use-user";
import { Loading } from "@/components/ui/loading";
import { Button } from "@/components/ui/button";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Badge } from "@/components/ui/badge";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import {
  AreaChart,
  Area,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
} from "recharts";
import { Progress } from "@/components/ui/progress";
import {
  Search,
  Download,
  RefreshCw,
  Clock,
  CheckCircle,
  XCircle,
  AlertCircle,
  Monitor,
  Smartphone,
  Tablet,
  Globe,
  Eye,
  MoreHorizontal,
  DollarSign,
  Cloud,
} from "lucide-react";

// Mock data for activity
const activityData = [
  {
    id: 1,
    type: "sync",
    status: "success",
    message: "Successfully synced 47 files",
    device: "MacBook Pro",
    timestamp: "2024-01-15T10:30:00Z",
    duration: 1200,
    filesCount: 47,
    dataSize: "2.4 MB",
  },
  {
    id: 2,
    type: "login",
    status: "success",
    message: "User logged in from new device",
    device: "iPhone 15 Pro",
    timestamp: "2024-01-15T09:45:00Z",
    location: "San Francisco, CA",
  },
  {
    id: 3,
    type: "sync",
    status: "error",
    message: "Sync failed: Connection timeout",
    device: "iPad Pro",
    timestamp: "2024-01-15T08:20:00Z",
    error: "CONNECTION_TIMEOUT",
  },
  {
    id: 4,
    type: "sync",
    status: "success",
    message: "Successfully synced 23 files",
    device: "MacBook Pro",
    timestamp: "2024-01-15T07:15:00Z",
    duration: 850,
    filesCount: 23,
    dataSize: "1.8 MB",
  },
  {
    id: 5,
    type: "settings",
    status: "success",
    message: "Profile updated",
    device: "MacBook Pro",
    timestamp: "2024-01-15T06:30:00Z",
  },
];

// Visual perception activity logs
const visionActivityLogs = [
  {
    id: 1,
    timestamp: "2024-01-15T14:30:00Z",
    type: "api_call",
    description: "Visual perception session started",
    duration: "2h 34m",
    platform: "local",
    cost: 0.0,
    frames: 18429,
  },
  {
    id: 2,
    timestamp: "2024-01-15T12:15:00Z",
    type: "cloud_processing",
    description: "Context memory sync to cloud",
    duration: "45s",
    platform: "cloud",
    cost: 0.08,
    data: "2.1 GB",
  },
  {
    id: 3,
    timestamp: "2024-01-15T10:22:00Z",
    type: "api_call",
    description: "Real-time video analysis",
    duration: "1h 18m",
    platform: "local",
    cost: 0.0,
    frames: 9430,
  },
  {
    id: 4,
    timestamp: "2024-01-15T09:45:00Z",
    type: "cloud_processing",
    description: "Advanced temporal reasoning",
    duration: "3m 22s",
    platform: "cloud",
    cost: 0.45,
    complexity: "high",
  },
  {
    id: 5,
    timestamp: "2024-01-15T08:30:00Z",
    type: "api_call",
    description: "iPhone camera feed processing",
    duration: "45m",
    platform: "local",
    cost: 0.0,
    frames: 5220,
  },
];

const chartData = [
  { name: "00:00", syncs: 12, errors: 1 },
  { name: "04:00", syncs: 8, errors: 0 },
  { name: "08:00", syncs: 45, errors: 2 },
  { name: "12:00", syncs: 67, errors: 1 },
  { name: "16:00", syncs: 89, errors: 3 },
  { name: "20:00", syncs: 56, errors: 0 },
];

const deviceStats = [
  {
    device: "MacBook Pro",
    syncs: 156,
    lastActive: "2 min ago",
    status: "online",
  },
  {
    device: "iPhone 15 Pro",
    syncs: 89,
    lastActive: "5 min ago",
    status: "online",
  },
  {
    device: "iPad Pro",
    syncs: 34,
    lastActive: "1 hour ago",
    status: "offline",
  },
];

export default function ActivityPage() {
  const { loading } = useUser();
  const [searchTerm, setSearchTerm] = useState("");
  const [statusFilter, setStatusFilter] = useState("all");
  const [typeFilter, setTypeFilter] = useState("all");

  if (loading) {
    return <Loading fullScreen size="xl" text="Loading activity data..." />;
  }

  const getStatusIcon = (status: string) => {
    switch (status) {
      case "success":
        return <CheckCircle className="w-4 h-4 text-green-500" />;
      case "error":
        return <XCircle className="w-4 h-4 text-red-500" />;
      case "warning":
        return <AlertCircle className="w-4 h-4 text-yellow-500" />;
      default:
        return <Clock className="w-4 h-4 text-gray-500" />;
    }
  };

  const getDeviceIcon = (device: string) => {
    if (device.includes("MacBook") || device.includes("iMac")) {
      return <Monitor className="w-4 h-4" />;
    } else if (device.includes("iPhone")) {
      return <Smartphone className="w-4 h-4" />;
    } else if (device.includes("iPad")) {
      return <Tablet className="w-4 h-4" />;
    }
    return <Globe className="w-4 h-4" />;
  };

  const formatTimestamp = (timestamp: string) => {
    const date = new Date(timestamp);
    const now = new Date();
    const diffInMinutes = Math.floor(
      (now.getTime() - date.getTime()) / (1000 * 60),
    );

    if (diffInMinutes < 60) {
      return `${diffInMinutes} min ago`;
    } else if (diffInMinutes < 1440) {
      return `${Math.floor(diffInMinutes / 60)} hours ago`;
    } else {
      return date.toLocaleDateString();
    }
  };

  const filteredActivity = activityData.filter((item) => {
    const matchesSearch = item.message
      .toLowerCase()
      .includes(searchTerm.toLowerCase());
    const matchesStatus =
      statusFilter === "all" || item.status === statusFilter;
    const matchesType = typeFilter === "all" || item.type === typeFilter;
    return matchesSearch && matchesStatus && matchesType;
  });

  return (
    <div className="min-h-screen bg-gradient-to-br from-background via-background to-muted/20 pt-8">
      <div className="container mx-auto px-4 py-8 max-w-7xl">
        {/* Header */}
        <div className="flex items-center justify-between mb-8">
          <div>
            <h1 className="text-4xl font-bold mb-2">Activity Monitor</h1>
            <p className="text-xl text-muted-foreground">
              Track your visual perception API usage, sync history, and device
              activity
            </p>
          </div>
          <div className="flex items-center space-x-2">
            <Button variant="outline" size="sm">
              <Download className="w-4 h-4 mr-2" />
              Export
            </Button>
            <Button variant="outline" size="sm">
              <RefreshCw className="w-4 h-4 mr-2" />
              Refresh
            </Button>
          </div>
        </div>

        {/* Stats Overview */}
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6 mb-8">
          <Card>
            <CardContent className="p-6">
              <div className="flex items-center justify-between">
                <div>
                  <p className="text-sm font-medium text-muted-foreground">
                    API Calls Today
                  </p>
                  <p className="text-2xl font-bold">1,247</p>
                </div>
                <Eye className="w-8 h-8 text-blue-500" />
              </div>
              <p className="text-xs text-muted-foreground mt-2">
                <span className="text-green-600">+18%</span> from yesterday
              </p>
            </CardContent>
          </Card>

          <Card>
            <CardContent className="p-6">
              <div className="flex items-center justify-between">
                <div>
                  <p className="text-sm font-medium text-muted-foreground">
                    Processing Time
                  </p>
                  <p className="text-2xl font-bold">4h 52m</p>
                </div>
                <Clock className="w-8 h-8 text-green-500" />
              </div>
              <p className="text-xs text-muted-foreground mt-2">
                68% local, 32% cloud
              </p>
            </CardContent>
          </Card>

          <Card>
            <CardContent className="p-6">
              <div className="flex items-center justify-between">
                <div>
                  <p className="text-sm font-medium text-muted-foreground">
                    Usage Charges
                  </p>
                  <p className="text-2xl font-bold">$12.47</p>
                </div>
                <DollarSign className="w-8 h-8 text-purple-500" />
              </div>
              <p className="text-xs text-muted-foreground mt-2">
                Current month
              </p>
            </CardContent>
          </Card>

          <Card>
            <CardContent className="p-6">
              <div className="flex items-center justify-between">
                <div>
                  <p className="text-sm font-medium text-muted-foreground">
                    Total Syncs Today
                  </p>
                  <p className="text-2xl font-bold">127</p>
                </div>
                <div className="p-2 bg-blue-100 dark:bg-blue-900 rounded-full">
                  <RefreshCw className="w-6 h-6 text-blue-600 dark:text-blue-400" />
                </div>
              </div>
              <p className="text-xs text-muted-foreground mt-2">
                <span className="text-green-600">+12%</span> from yesterday
              </p>
            </CardContent>
          </Card>
        </div>

        <Tabs defaultValue="timeline" className="space-y-6">
          <TabsList className="grid w-full grid-cols-5">
            <TabsTrigger value="timeline">Timeline</TabsTrigger>
            <TabsTrigger value="vision">Vision API</TabsTrigger>
            <TabsTrigger value="analytics">Analytics</TabsTrigger>
            <TabsTrigger value="devices">Devices</TabsTrigger>
            <TabsTrigger value="errors">Error Logs</TabsTrigger>
          </TabsList>

          <TabsContent value="timeline" className="space-y-6">
            {/* Filters */}
            <Card>
              <CardHeader>
                <CardTitle>Activity Timeline</CardTitle>
                <CardDescription>
                  View and filter your recent activity across all devices
                </CardDescription>
              </CardHeader>
              <CardContent>
                <div className="flex flex-col sm:flex-row gap-4 mb-6">
                  <div className="flex-1">
                    <Label htmlFor="search" className="sr-only">
                      Search activity
                    </Label>
                    <div className="relative">
                      <Search className="absolute left-3 top-3 h-4 w-4 text-muted-foreground" />
                      <Input
                        id="search"
                        placeholder="Search activity..."
                        className="pl-10"
                        value={searchTerm}
                        onChange={(e) => setSearchTerm(e.target.value)}
                      />
                    </div>
                  </div>
                  <Select value={statusFilter} onValueChange={setStatusFilter}>
                    <SelectTrigger className="w-[140px]">
                      <SelectValue placeholder="Status" />
                    </SelectTrigger>
                    <SelectContent>
                      <SelectItem value="all">All Status</SelectItem>
                      <SelectItem value="success">Success</SelectItem>
                      <SelectItem value="error">Error</SelectItem>
                      <SelectItem value="warning">Warning</SelectItem>
                    </SelectContent>
                  </Select>
                  <Select value={typeFilter} onValueChange={setTypeFilter}>
                    <SelectTrigger className="w-[140px]">
                      <SelectValue placeholder="Type" />
                    </SelectTrigger>
                    <SelectContent>
                      <SelectItem value="all">All Types</SelectItem>
                      <SelectItem value="sync">Sync</SelectItem>
                      <SelectItem value="login">Login</SelectItem>
                      <SelectItem value="settings">Settings</SelectItem>
                    </SelectContent>
                  </Select>
                </div>

                {/* Activity List */}
                <div className="space-y-4">
                  {filteredActivity.map((item) => (
                    <div
                      key={item.id}
                      className="flex items-start space-x-4 p-4 border rounded-lg hover:bg-accent/50 transition-colors"
                    >
                      <div className="flex-shrink-0 mt-1">
                        {getStatusIcon(item.status)}
                      </div>
                      <div className="flex-1 min-w-0">
                        <div className="flex items-center justify-between">
                          <p className="font-medium truncate">{item.message}</p>
                          <div className="flex items-center space-x-2 text-sm text-muted-foreground">
                            {getDeviceIcon(item.device)}
                            <span>{item.device}</span>
                          </div>
                        </div>
                        <div className="flex items-center justify-between mt-2">
                          <div className="flex items-center space-x-4 text-sm text-muted-foreground">
                            <span>{formatTimestamp(item.timestamp)}</span>
                            {item.duration && (
                              <span>Duration: {item.duration}ms</span>
                            )}
                            {item.filesCount && (
                              <span>Files: {item.filesCount}</span>
                            )}
                            {item.dataSize && (
                              <span>Size: {item.dataSize}</span>
                            )}
                          </div>
                          <Button variant="ghost" size="sm">
                            <MoreHorizontal className="w-4 h-4" />
                          </Button>
                        </div>
                      </div>
                    </div>
                  ))}
                </div>
              </CardContent>
            </Card>
          </TabsContent>

          <TabsContent value="vision" className="space-y-6">
            {/* Vision Activity Log */}
            <Card>
              <CardHeader>
                <CardTitle className="flex items-center">
                  <Eye className="w-5 h-5 mr-2" />
                  Visual Perception Activity
                </CardTitle>
                <CardDescription>
                  Your recent API usage, processing sessions, and charges
                </CardDescription>
              </CardHeader>
              <CardContent>
                <div className="space-y-4">
                  {visionActivityLogs.map((activity) => (
                    <div
                      key={activity.id}
                      className="flex items-start space-x-4 p-4 border rounded-lg hover:bg-accent/50 transition-colors"
                    >
                      <div className="flex-shrink-0 mt-1">
                        {activity.type === "api_call" ? (
                          <Eye className="w-4 h-4 text-blue-500" />
                        ) : (
                          <Cloud className="w-4 h-4 text-purple-500" />
                        )}
                      </div>
                      <div className="flex-1 min-w-0">
                        <div className="flex items-center justify-between">
                          <p className="font-medium truncate">
                            {activity.description}
                          </p>
                          <div className="flex items-center space-x-2">
                            <Badge
                              variant={
                                activity.platform === "local"
                                  ? "secondary"
                                  : "default"
                              }
                            >
                              {activity.platform}
                            </Badge>
                            {activity.cost > 0 && (
                              <span className="text-sm font-medium">
                                ${activity.cost.toFixed(2)}
                              </span>
                            )}
                          </div>
                        </div>
                        <div className="flex items-center space-x-4 mt-2 text-sm text-muted-foreground">
                          <span>{formatTimestamp(activity.timestamp)}</span>
                          <span>Duration: {activity.duration}</span>
                          {activity.frames && (
                            <span>
                              Frames: {activity.frames.toLocaleString()}
                            </span>
                          )}
                          {activity.data && <span>Data: {activity.data}</span>}
                          {activity.complexity && (
                            <span>Complexity: {activity.complexity}</span>
                          )}
                        </div>
                      </div>
                    </div>
                  ))}
                </div>
              </CardContent>
            </Card>

            {/* Usage Patterns */}
            <Card>
              <CardHeader>
                <CardTitle>Usage Patterns</CardTitle>
                <CardDescription>
                  Insights into your visual perception platform usage
                </CardDescription>
              </CardHeader>
              <CardContent>
                <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
                  <div className="space-y-4">
                    <h4 className="font-medium">Platform Distribution</h4>
                    <div className="space-y-2">
                      <div className="flex justify-between text-sm">
                        <span>Local Processing</span>
                        <span>68%</span>
                      </div>
                      <Progress value={68} className="h-2" />
                    </div>
                    <div className="space-y-2">
                      <div className="flex justify-between text-sm">
                        <span>Cloud Processing</span>
                        <span>32%</span>
                      </div>
                      <Progress value={32} className="h-2" />
                    </div>
                  </div>
                  <div className="space-y-4">
                    <h4 className="font-medium">Peak Usage Hours</h4>
                    <div className="text-sm text-muted-foreground space-y-1">
                      <p>Most active: 2:00 PM - 6:00 PM</p>
                      <p>Average session: 1h 34m</p>
                      <p>Preferred platform: Local (Mac-iPhone)</p>
                    </div>
                  </div>
                </div>
              </CardContent>
            </Card>
          </TabsContent>

          <TabsContent value="analytics" className="space-y-6">
            <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
              <Card>
                <CardHeader>
                  <CardTitle>Vision API Usage (24h)</CardTitle>
                  <CardDescription>
                    API calls and processing time over the last 24 hours
                  </CardDescription>
                </CardHeader>
                <CardContent>
                  <ResponsiveContainer width="100%" height={300}>
                    <AreaChart
                      data={[
                        { name: "00:00", calls: 45, processing: 120 },
                        { name: "04:00", calls: 23, processing: 80 },
                        { name: "08:00", calls: 156, processing: 340 },
                        { name: "12:00", calls: 234, processing: 520 },
                        { name: "16:00", calls: 298, processing: 680 },
                        { name: "20:00", calls: 187, processing: 420 },
                      ]}
                    >
                      <CartesianGrid
                        strokeDasharray="3 3"
                        className="stroke-muted"
                      />
                      <XAxis dataKey="name" className="text-muted-foreground" />
                      <YAxis className="text-muted-foreground" />
                      <Tooltip
                        contentStyle={{
                          backgroundColor: "hsl(var(--background))",
                          border: "1px solid hsl(var(--border))",
                          borderRadius: "6px",
                        }}
                      />
                      <Area
                        type="monotone"
                        dataKey="calls"
                        stackId="1"
                        stroke="#3b82f6"
                        fill="#3b82f6"
                        fillOpacity={0.6}
                        name="API Calls"
                      />
                      <Area
                        type="monotone"
                        dataKey="processing"
                        stackId="2"
                        stroke="#8b5cf6"
                        fill="#8b5cf6"
                        fillOpacity={0.6}
                        name="Processing Time (min)"
                      />
                    </AreaChart>
                  </ResponsiveContainer>
                </CardContent>
              </Card>

              <Card>
                <CardHeader>
                  <CardTitle>Sync Activity (24h)</CardTitle>
                  <CardDescription>
                    Number of syncs and errors over the last 24 hours
                  </CardDescription>
                </CardHeader>
                <CardContent>
                  <ResponsiveContainer width="100%" height={300}>
                    <AreaChart data={chartData}>
                      <CartesianGrid
                        strokeDasharray="3 3"
                        className="stroke-muted"
                      />
                      <XAxis dataKey="name" className="text-muted-foreground" />
                      <YAxis className="text-muted-foreground" />
                      <Tooltip
                        contentStyle={{
                          backgroundColor: "hsl(var(--background))",
                          border: "1px solid hsl(var(--border))",
                          borderRadius: "6px",
                        }}
                      />
                      <Area
                        type="monotone"
                        dataKey="syncs"
                        stackId="1"
                        stroke="#10b981"
                        fill="#10b981"
                        fillOpacity={0.6}
                      />
                      <Area
                        type="monotone"
                        dataKey="errors"
                        stackId="1"
                        stroke="#ef4444"
                        fill="#ef4444"
                        fillOpacity={0.6}
                      />
                    </AreaChart>
                  </ResponsiveContainer>
                </CardContent>
              </Card>
            </div>

            <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
              <Card>
                <CardHeader>
                  <CardTitle>Vision Processing Metrics</CardTitle>
                  <CardDescription>
                    Visual perception API performance and usage stats
                  </CardDescription>
                </CardHeader>
                <CardContent>
                  <div className="space-y-4">
                    <div className="flex items-center justify-between">
                      <span className="text-sm font-medium">
                        Average Processing Time
                      </span>
                      <span className="text-sm">2.3s</span>
                    </div>
                    <div className="flex items-center justify-between">
                      <span className="text-sm font-medium">
                        Frames Processed
                      </span>
                      <span className="text-sm">45.2K today</span>
                    </div>
                    <div className="flex items-center justify-between">
                      <span className="text-sm font-medium">Success Rate</span>
                      <span className="text-sm">99.7%</span>
                    </div>
                    <div className="flex items-center justify-between">
                      <span className="text-sm font-medium">Cloud Usage</span>
                      <span className="text-sm">32% of total</span>
                    </div>
                  </div>
                </CardContent>
              </Card>

              <Card>
                <CardHeader>
                  <CardTitle>Sync Performance Metrics</CardTitle>
                  <CardDescription>
                    Device synchronization performance and reliability
                  </CardDescription>
                </CardHeader>
                <CardContent>
                  <div className="space-y-4">
                    <div className="flex items-center justify-between">
                      <span className="text-sm font-medium">
                        Average Sync Time
                      </span>
                      <span className="text-sm">1.2s</span>
                    </div>
                    <div className="flex items-center justify-between">
                      <span className="text-sm font-medium">
                        Peak Throughput
                      </span>
                      <span className="text-sm">45 syncs/min</span>
                    </div>
                    <div className="flex items-center justify-between">
                      <span className="text-sm font-medium">Error Rate</span>
                      <span className="text-sm">0.8%</span>
                    </div>
                    <div className="flex items-center justify-between">
                      <span className="text-sm font-medium">Uptime</span>
                      <span className="text-sm">99.9%</span>
                    </div>
                  </div>
                </CardContent>
              </Card>
            </div>
          </TabsContent>

          <TabsContent value="devices" className="space-y-6">
            <Card>
              <CardHeader>
                <CardTitle>Device Activity</CardTitle>
                <CardDescription>
                  Monitor activity across all your connected devices
                </CardDescription>
              </CardHeader>
              <CardContent>
                <div className="space-y-4">
                  {deviceStats.map((device, index) => (
                    <div
                      key={index}
                      className="flex items-center justify-between p-4 border rounded-lg"
                    >
                      <div className="flex items-center space-x-3">
                        {getDeviceIcon(device.device)}
                        <div>
                          <p className="font-medium">{device.device}</p>
                          <p className="text-sm text-muted-foreground">
                            {device.syncs} syncs • Last active{" "}
                            {device.lastActive}
                          </p>
                        </div>
                      </div>
                      <div className="flex items-center space-x-2">
                        <Badge
                          variant={
                            device.status === "online" ? "default" : "secondary"
                          }
                        >
                          <div
                            className={`w-2 h-2 rounded-full mr-2 ${
                              device.status === "online"
                                ? "bg-green-500"
                                : "bg-gray-500"
                            }`}
                          />
                          {device.status}
                        </Badge>
                        <Button variant="ghost" size="sm">
                          <Eye className="w-4 h-4" />
                        </Button>
                      </div>
                    </div>
                  ))}
                </div>
              </CardContent>
            </Card>
          </TabsContent>

          <TabsContent value="errors" className="space-y-6">
            <Card>
              <CardHeader>
                <CardTitle>Error Logs</CardTitle>
                <CardDescription>
                  Review recent errors and system issues
                </CardDescription>
              </CardHeader>
              <CardContent>
                <div className="space-y-4">
                  {activityData
                    .filter((item) => item.status === "error")
                    .map((error) => (
                      <div
                        key={error.id}
                        className="flex items-start space-x-4 p-4 border border-red-200 dark:border-red-800 rounded-lg bg-red-50 dark:bg-red-950/20"
                      >
                        <XCircle className="w-5 h-5 text-red-500 mt-0.5 flex-shrink-0" />
                        <div className="flex-1">
                          <p className="font-medium text-red-900 dark:text-red-100">
                            {error.message}
                          </p>
                          <div className="flex items-center space-x-4 mt-2 text-sm text-red-700 dark:text-red-300">
                            <span>{error.device}</span>
                            <span>{formatTimestamp(error.timestamp)}</span>
                            {error.error && (
                              <Badge variant="destructive" className="text-xs">
                                {error.error}
                              </Badge>
                            )}
                          </div>
                        </div>
                      </div>
                    ))}
                </div>
              </CardContent>
            </Card>
          </TabsContent>
        </Tabs>
      </div>
    </div>
  );
}
