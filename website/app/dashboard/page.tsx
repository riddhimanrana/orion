"use client";

import { useEffect, useState } from "react";
import { useUser } from "@/hooks/use-user";
import { useSubscription } from "@/hooks/use-subscription";
import { Button } from "@/components/ui/button";
import { Loading } from "@/components/ui/loading";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { Progress } from "@/components/ui/progress";
import { Badge } from "@/components/ui/badge";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import {
  Smartphone,
  Monitor,
  Cloud,
  Download,
  CheckCircle,
  ExternalLink,
  Settings,
  CreditCard,
  Activity,
  Wifi,
  WifiOff,
  Crown,
  AppWindow,
} from "lucide-react";

interface DeviceStatus {
  id: string;
  name: string;
  type: "iPhone" | "Mac";
  status: "connected" | "disconnected";
  lastSeen: string;
  version: string;
}

interface ApiUsage {
  plan: "Free" | "Pro";
  used: number;
  limit: number;
  resetDate: string;
}

export default function DashboardPage() {
  const { user, loading } = useUser();
  const { subscriptionTier } = useSubscription();
  const [devices, setDevices] = useState<DeviceStatus[]>([]);
  const [isClosingWindow, setIsClosingWindow] = useState(false);
  const [apiUsage, setApiUsage] = useState<ApiUsage>({
    plan: "Free",
    used: 0,
    limit: 1000,
    resetDate: "2024-01-01",
  });

  // Check if this is a mobile authentication session that should auto-close
  useEffect(() => {
    const urlParams = new URLSearchParams(window.location.search);
    const timestamp = urlParams.get('t'); // Cache busting parameter from auth callback
    const referrer = document.referrer;
    const userAgent = navigator.userAgent;
    const isMobileDevice = /Android|webOS|iPhone|iPad|iPod|BlackBerry|IEMobile|Opera Mini/i.test(userAgent);
    
    // Check if this is likely a mobile web authentication session
    const isMobileAuthSession = (
      isMobileDevice && 
      timestamp && 
      (referrer.includes('/auth/callback') || referrer.includes('/auth/confirm'))
    );
    
    if (isMobileAuthSession && user) {
      console.log("Mobile auth session detected - closing window in 2 seconds");
      setIsClosingWindow(true);
      setTimeout(() => {
        // Try to close the window
        try {
          window.close();
        } catch (error) {
          console.log("Could not close window:", error);
          // Fallback: redirect to close page
          window.location.href = `/auth/close-window?message=${encodeURIComponent("You can now return to the Orion Live app")}`;
        }
      }, 2000);
    }
  }, [user]);

  useEffect(() => {
    if (process.env.NODE_ENV === "development") {
      console.log("👤 Dashboard user state changed:", user?.email || "No user");
    }
  }, [user]);

  // Mock data for development
  useEffect(() => {
    if (user) {
      setDevices([
        {
          id: "1",
          name: "iPhone 15 Pro",
          type: "iPhone",
          status: "connected",
          lastSeen: "2 minutes ago",
          version: "1.2.0",
        },
        {
          id: "2",
          name: "MacBook Pro M3",
          type: "Mac",
          status: "disconnected",
          lastSeen: "1 hour ago",
          version: "1.1.0",
        },
      ]);

      setApiUsage({
        plan: subscriptionTier === "pro" ? "Pro" : "Free",
        used: subscriptionTier === "pro" ? 1247 : 247,
        limit: subscriptionTier === "pro" ? 10000 : 1000,
        resetDate: "2024-02-01",
      });
    }
  }, [user, subscriptionTier]);

  if (loading) {
    return (
      <Loading fullScreen size="xl" text="Loading dashboard..." />
    );
  }

  if (isClosingWindow) {
    return (
      <div className="min-h-screen flex items-center justify-center">
        <div className="text-center">
          <div className="text-green-500 mb-4">
            <svg className="w-16 h-16 mx-auto" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M5 13l4 4L19 7" />
            </svg>
          </div>
          <h1 className="text-2xl font-bold mb-2">Authentication Successful!</h1>
          <p className="text-muted-foreground">
            You can now return to the Orion Live app. This window will close automatically.
          </p>
        </div>
      </div>
    );
  }

  if (!loading && !user) {
    return (
      <div className="min-h-screen flex items-center justify-center">
        <div className="text-center">
          <h1 className="text-2xl font-bold text-muted-foreground">
            Please Sign In
          </h1>
          <p className="text-muted-foreground mt-2">
            You need to be signed in to access your dashboard.
          </p>
          <Button
            onClick={() => (window.location.href = "/login")}
            className="mt-4"
          >
            Sign In
          </Button>
        </div>
      </div>
    );
  }

  const usagePercentage = (apiUsage.used / apiUsage.limit) * 100;
  const connectedDevices = devices.filter(
    (d) => d.status === "connected",
  ).length;

  return (
    <div className="min-h-screen bg-white dark:bg-black">
      <div className="container mx-auto px-4 py-8">
        {/* Welcome Section */}
        <div className="mb-8">
          <h2 className="text-4xl font-bold mb-2 flex items-center gap-2 ">
            {(() => {
              const hour = new Date().getHours();
              if (hour < 12) return "Good morning,";
              if (hour < 18) return "Good afternoon,";
              return "Good evening,";
            })()}{" "}
            {user?.user_metadata?.full_name?.split(" ")[0] || "user"}
            {subscriptionTier === "pro" && (
              <Crown className="h-8 w-8 text-amber-500" />
            )}
          </h2>
          <p className="text-xl text-muted-foreground">
            Manage your Orion Live account, devices, and subscription.
            {/* {subscriptionTier === "pro" && (
              <span className="ml-2 text-amber-600 font-medium">
                Orion Pro Member
              </span>
            )} */}
          </p>
        </div>

        {/* Quick Stats */}
        <div className="grid grid-cols-1 md:grid-cols-3 gap-6 mb-8">
          <Card>
            <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
              <CardTitle className="text-sm font-medium">
                Connected Devices
              </CardTitle>
              <Smartphone className="h-4 w-4 text-muted-foreground" />
            </CardHeader>
            <CardContent>
              <div className="text-2xl font-bold">{connectedDevices}</div>
              <p className="text-xs text-muted-foreground">
                {devices.length} total devices
              </p>
            </CardContent>
          </Card>

          <Card>
            <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
              <CardTitle className="text-sm font-medium">API Usage</CardTitle>
              <Activity className="h-4 w-4 text-muted-foreground" />
            </CardHeader>
            <CardContent>
              <div className="text-2xl font-bold">
                {apiUsage.used.toLocaleString()}
              </div>
              <p className="text-xs text-muted-foreground">
                of {apiUsage.limit.toLocaleString()} this month
              </p>
            </CardContent>
          </Card>

          <Card>
            <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
              <CardTitle className="text-sm font-medium">
                Current Plan
              </CardTitle>
              {subscriptionTier === "pro" ? (
                <Crown className="h-4 w-4 text-amber-500" />
              ) : (
                <CreditCard className="h-4 w-4 text-muted-foreground" />
              )}
            </CardHeader>
            <CardContent>
              <div className="text-2xl font-bold flex items-center gap-2">
                {subscriptionTier === "pro" ? "Orion Pro" : "Free"}
                {/* {subscriptionTier === "pro" && (
                  <Crown className="h-5 w-5 text-amber-500" />
                )} */}
              </div>
              <p className="text-xs text-muted-foreground">
                {subscriptionTier === "free"
                  ? "Upgrade for unlimited features"
                  : "All premium features enabled"}
              </p>
            </CardContent>
          </Card>
        </div>

        <Tabs defaultValue="setup" className="space-y-4">
          <TabsList>
            <TabsTrigger value="setup">Get Started</TabsTrigger>
            <TabsTrigger value="devices">Devices</TabsTrigger>
            <TabsTrigger value="usage">Usage</TabsTrigger>
            <TabsTrigger value="billing">Billing</TabsTrigger>
          </TabsList>

          <TabsContent value="setup" className="space-y-6">
            <Card>
              <CardHeader>
                <CardTitle className="flex items-center gap-2">
                  <AppWindow className="h-5 w-5" />
                  Getting Started with Orion Live
                </CardTitle>
                <CardDescription>
                  Follow these steps to set up Orion Live on your devices
                </CardDescription>
              </CardHeader>
              <CardContent className="space-y-6">
                {/* Step 1: Download iPhone App */}
                <div className="flex items-start space-x-4 p-4 border rounded-lg">
                  <div className="flex-shrink-0 w-8 h-8 bg-blue-100 dark:bg-blue-900 rounded-full flex items-center justify-center">
                    <span className="text-sm font-bold text-blue-600 dark:text-blue-400">
                      1
                    </span>
                  </div>
                  <div className="flex-1">
                    <h3 className="font-semibold mb-2 flex items-center gap-2">
                      <Smartphone className="h-4 w-4" />
                      Download Orion Live for iPhone
                    </h3>
                    <p className="text-sm text-muted-foreground mb-3">
                      Get the Orion Live app from the App Store to start using
                      visual AI on your iPhone.
                    </p>
                    <Button className="flex items-center gap-2">
                      <Download className="h-4 w-4" />
                      Download from App Store
                      <ExternalLink className="h-3 w-3" />
                    </Button>
                  </div>
                </div>

                {/* Step 2: Choose Inference Method */}
                <div className="flex items-start space-x-4 p-4 border rounded-lg">
                  <div className="flex-shrink-0 w-8 h-8 bg-blue-100 dark:bg-blue-900 rounded-full flex items-center justify-center">
                    <span className="text-sm font-bold text-blue-600 dark:text-blue-400">
                      2
                    </span>
                  </div>
                  <div className="flex-1">
                    <h3 className="font-semibold mb-2">
                      Choose Your Inference Method
                    </h3>
                    <p className="text-sm text-muted-foreground mb-4">
                      Choose between local inference (faster, private) or cloud
                      inference (easier setup).
                    </p>

                    <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                      {/* Local Option */}
                      <div className="border rounded-lg p-4 space-y-3">
                        <div className="flex items-center gap-2">
                          <Monitor className="h-4 w-4 text-green-600" />
                          <h4 className="font-medium">
                            Local Inference (Recommended)
                          </h4>
                        </div>
                        <ul className="text-sm text-muted-foreground space-y-1">
                          <li>• Faster processing (~50ms)</li>
                          <li>• Complete privacy</li>
                          <li>• Works offline</li>
                          <li>• Requires Mac server</li>
                        </ul>
                        <Button
                          variant="outline"
                          className="w-full flex items-center gap-2"
                        >
                          <Download className="h-4 w-4" />
                          Download Mac Server (.dmg)
                        </Button>
                      </div>

                      {/* Cloud Option */}
                      <div className="border rounded-lg p-4 space-y-3">
                        <div className="flex items-center gap-2">
                          <Cloud className="h-4 w-4 text-blue-600" />
                          <h4 className="font-medium">Cloud Inference</h4>
                        </div>
                        <ul className="text-sm text-muted-foreground space-y-1">
                          <li>• No additional setup</li>
                          <li>• Works anywhere</li>
                          <li>• API usage limits</li>
                          <li>• Slightly higher latency</li>
                        </ul>
                        <Button variant="outline" className="w-full" disabled>
                          <CheckCircle className="h-4 w-4" />
                          Ready to use
                        </Button>
                      </div>
                    </div>
                  </div>
                </div>

                {/* Step 3: Sign In */}
                <div className="flex items-start space-x-4 p-4 border rounded-lg">
                  <div className="flex-shrink-0 w-8 h-8 bg-blue-100 dark:bg-blue-900 rounded-full flex items-center justify-center">
                    <span className="text-sm font-bold text-blue-600 dark:text-blue-400">
                      3
                    </span>
                  </div>
                  <div className="flex-1">
                    <h3 className="font-semibold mb-2 flex items-center gap-2">
                      <CheckCircle className="h-4 w-4 text-green-600" />
                      Sign In to Your Account
                    </h3>
                    <p className="text-sm text-muted-foreground mb-3">
                      You&apos;re already signed in! Open the Orion Live app and
                      sign in with this account: <strong>{user?.email}</strong>
                    </p>
                  </div>
                </div>
              </CardContent>
            </Card>
          </TabsContent>

          <TabsContent value="devices" className="space-y-4">
            <Card>
              <CardHeader>
                <CardTitle>Connected Devices</CardTitle>
                <CardDescription>
                  Manage your Orion Live devices and their connection status
                </CardDescription>
              </CardHeader>
              <CardContent>
                <div className="space-y-4">
                  {devices.map((device) => (
                    <div
                      key={device.id}
                      className="flex items-center justify-between p-4 border rounded-lg"
                    >
                      <div className="flex items-center space-x-4">
                        <div className="flex-shrink-0">
                          {device.type === "iPhone" ? (
                            <Smartphone className="h-8 w-8 text-muted-foreground" />
                          ) : (
                            <Monitor className="h-8 w-8 text-muted-foreground" />
                          )}
                        </div>
                        <div>
                          <h3 className="font-medium">{device.name}</h3>
                          <p className="text-sm text-muted-foreground">
                            Version {device.version} • Last seen{" "}
                            {device.lastSeen}
                          </p>
                        </div>
                      </div>
                      <div className="flex items-center space-x-2">
                        <Badge
                          variant={
                            device.status === "connected"
                              ? "default"
                              : "secondary"
                          }
                        >
                          {device.status === "connected" ? (
                            <>
                              <Wifi className="h-3 w-3 mr-1" /> Connected
                            </>
                          ) : (
                            <>
                              <WifiOff className="h-3 w-3 mr-1" /> Disconnected
                            </>
                          )}
                        </Badge>
                        <Button variant="ghost" size="sm">
                          <Settings className="h-4 w-4" />
                        </Button>
                      </div>
                    </div>
                  ))}

                  {devices.length === 0 && (
                    <div className="text-center py-8">
                      <Smartphone className="h-12 w-12 text-muted-foreground mx-auto mb-4" />
                      <h3 className="font-medium mb-2">No devices connected</h3>
                      <p className="text-sm text-muted-foreground">
                        Download the Orion Live app and sign in to see your
                        devices here.
                      </p>
                    </div>
                  )}
                </div>
              </CardContent>
            </Card>
          </TabsContent>

          <TabsContent value="usage" className="space-y-4">
            <Card>
              <CardHeader>
                <CardTitle>API Usage</CardTitle>
                <CardDescription>
                  Monitor your Orion Live API consumption and limits
                </CardDescription>
              </CardHeader>
              <CardContent className="space-y-6">
                <div>
                  <div className="flex justify-between items-center mb-2">
                    <span className="text-sm font-medium">This month</span>
                    <span className="text-sm text-muted-foreground">
                      {apiUsage.used.toLocaleString()} /{" "}
                      {apiUsage.limit.toLocaleString()} requests
                    </span>
                  </div>
                  <Progress value={usagePercentage} className="w-full" />
                  <p className="text-xs text-muted-foreground mt-2">
                    Resets on{" "}
                    {new Date(apiUsage.resetDate).toLocaleDateString()}
                  </p>
                </div>

                {subscriptionTier === "free" && usagePercentage > 80 && (
                  <div className="p-4 bg-yellow-50 dark:bg-yellow-900/20 border border-yellow-200 dark:border-yellow-800 rounded-lg">
                    <h4 className="font-medium text-yellow-800 dark:text-yellow-200 mb-2">
                      Approaching Usage Limit
                    </h4>
                    <p className="text-sm text-yellow-700 dark:text-yellow-300 mb-3">
                      You&apos;ve used {usagePercentage.toFixed(0)}% of your
                      monthly API requests. Consider upgrading to Cloud Pro for
                      unlimited usage.
                    </p>
                    <Button
                      size="sm"
                      className="bg-yellow-600 hover:bg-yellow-700"
                      onClick={() => (window.location.href = "/account")}
                    >
                      <Crown className="h-4 w-4 mr-2" />
                      Upgrade to Cloud Pro
                    </Button>
                  </div>
                )}

                {subscriptionTier === "pro" && (
                  <div className="p-4 bg-green-50 dark:bg-green-900/20 border border-green-200 dark:border-green-800 rounded-lg">
                    <h4 className="font-medium text-green-800 dark:text-green-200 mb-2 flex items-center gap-2">
                      <Crown className="h-4 w-4" />
                      Cloud Pro Active
                    </h4>
                    <p className="text-sm text-green-700 dark:text-green-300">
                      You have unlimited API requests and access to all premium
                      features.
                    </p>
                  </div>
                )}
              </CardContent>
            </Card>
          </TabsContent>

          <TabsContent value="billing" className="space-y-4">
            <Card>
              <CardHeader>
                <CardTitle>Subscription Management</CardTitle>
                <CardDescription>
                  Manage your Orion Live subscription and features
                </CardDescription>
              </CardHeader>
              <CardContent className="space-y-6">
                <div className="flex items-center justify-between p-4 border rounded-lg">
                  <div>
                    <h3 className="font-medium flex items-center gap-2">
                      Current Plan:{" "}
                      {subscriptionTier === "pro" ? "Cloud Pro" : "Free"}
                      {subscriptionTier === "pro" && (
                        <Crown className="h-4 w-4 text-amber-500" />
                      )}
                    </h3>
                    <p className="text-sm text-muted-foreground">
                      {subscriptionTier === "free"
                        ? `${apiUsage.limit.toLocaleString()} API requests per month`
                        : "Unlimited API requests + premium features"}
                    </p>
                  </div>
                  <div className="text-right">
                    <p className="font-bold text-lg">
                      {subscriptionTier === "free" ? "$0" : "$19"}
                      <span className="text-sm font-normal text-muted-foreground">
                        /month
                      </span>
                    </p>
                  </div>
                </div>

                {subscriptionTier === "free" ? (
                  <div className="space-y-4">
                    <h4 className="font-medium">Upgrade to Cloud Pro</h4>
                    <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                      <div className="space-y-2">
                        <h5 className="font-medium text-sm">What you get:</h5>
                        <ul className="text-sm text-muted-foreground space-y-1">
                          <li>• Unlimited API requests</li>
                          <li>• Unlimited context memory</li>
                          <li>• Advanced AI models</li>
                          <li>• Priority support</li>
                          <li>• Early access to features</li>
                        </ul>
                      </div>
                      <div className="flex items-center">
                        <Button
                          className="w-full"
                          onClick={() => (window.location.href = "/account")}
                        >
                          <Crown className="h-4 w-4 mr-2" />
                          Upgrade to Cloud Pro - $19/month
                        </Button>
                      </div>
                    </div>
                  </div>
                ) : (
                  <div className="p-4 bg-green-50 dark:bg-green-900/20 border border-green-200 dark:border-green-800 rounded-lg">
                    <h4 className="font-medium text-green-800 dark:text-green-200 mb-2 flex items-center gap-2">
                      <Crown className="h-4 w-4" />
                      Cloud Pro Active
                    </h4>
                    <p className="text-sm text-green-700 dark:text-green-300">
                      You have access to all premium features and unlimited API
                      usage. Manage your subscription in Account settings.
                    </p>
                  </div>
                )}
              </CardContent>
            </Card>
          </TabsContent>
        </Tabs>
      </div>
    </div>
  );
}
