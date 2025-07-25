"use client";

import React, { useState } from "react";
import { Button } from "@/components/ui/button";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import {
  Smartphone,
  Monitor,
  Cloud,
  CheckCircle,
  Zap,
  Shield,
  Wifi,
  Crown,
  ArrowRight,
  Laptop,
  Users,
  Code,
  Wrench,
} from "lucide-react";
import Link from "next/link";

import { SiGithub } from "react-icons/si";

export default function GetStartedPage() {
  const [selectedMethod, setSelectedMethod] = useState<
    "local" | "cloud" | null
  >(null);

  return (
    <div className="min-h-screen bg-gradient-to-br from-background via-background to-muted/20">
      <div className="container mx-auto px-4 py-16">
        {/* Hero Section */}
        <div className="text-center mb-16">
          <h1 className="text-4xl md:text-6xl font-bold mb-6">Get Started with Orion Live</h1>
          <p className="text-xl text-muted-foreground max-w-3xl mx-auto mb-8">
            Experience revolutionary visual AI on your devices. Download our iOS app and optional Mac server 
            to start understanding the world around you with cutting-edge computer vision technology.
          </p>
          
          {/* Development Status Alert */}
          <div className="max-w-2xl mx-auto mb-8">
            <Card className="border-amber-200 dark:border-amber-800 bg-amber-50/50 dark:bg-amber-900/20">
              <CardContent className="p-4">
                <div className="flex items-center gap-2 mb-2">
                  <Wrench className="h-4 w-4 text-amber-500" />
                  <h3 className="font-semibold text-sm">Currently in Development</h3>
                </div>
                <p className="text-sm text-muted-foreground">
                  Orion Live is actively being developed. While there are no public app store releases yet, 
                  you can compile and test the apps yourself from our open-source GitHub repository.
                </p>
              </CardContent>
            </Card>
          </div>

          <div className="flex flex-col sm:flex-row gap-4 justify-center">
            <Button size="lg" className="px-8" asChild>
              <Link href="https://github.com/riddhimanrana/orion" target="_blank" rel="noopener noreferrer">
                <SiGithub className="h-5 w-5" />
                View on GitHub
              </Link>
            </Button>
            <Button variant="outline" size="lg" className="px-8" asChild>
              <Link href="/signup">
                Create Account
                <ArrowRight className="ml-2 h-5 w-5" />
              </Link>
            </Button>
          </div>
        </div>

        {/* Quick Start Steps */}
        <div className="max-w-4xl mx-auto mb-16">
          <h2 className="text-3xl font-bold text-center mb-8">
            How to Get Started
          </h2>
          <div className="grid grid-cols-1 md:grid-cols-3 gap-8">
            <Card className="text-center">
              <CardHeader>
                <div className="w-12 h-12 bg-blue-100 dark:bg-blue-900 rounded-full flex items-center justify-center mx-auto mb-4">
                  <Smartphone className="h-6 w-6 text-blue-600 dark:text-blue-400" />
                </div>
                <CardTitle>1. Get the iOS App</CardTitle>
              </CardHeader>
              <CardContent>
                <p className="text-muted-foreground mb-4">
                  Compile the Orion Live iOS app from GitHub and install on your iPhone
                </p>
                <Button className="w-full" variant="outline" asChild>
                  <Link href="https://github.com/riddhimanrana/orion" target="_blank" rel="noopener noreferrer">
                    <Code className="h-4 w-4" />
                    iOS Source Code
                  </Link>
                </Button>
              </CardContent>
            </Card>

            <Card className="text-center">
              <CardHeader>
                <div className="w-12 h-12 bg-green-100 dark:bg-green-900 rounded-full flex items-center justify-center mx-auto mb-4">
                  <Monitor className="h-6 w-6 text-green-600 dark:text-green-400" />
                </div>
                <CardTitle>2. Setup Mac Server (Optional)</CardTitle>
              </CardHeader>
              <CardContent>
                <p className="text-muted-foreground mb-4">
                  For local processing, compile and run the Mac server for faster inference
                </p>
                <Button className="w-full" variant="outline" asChild>
                  <Link href="https://github.com/riddhimanrana/orion" target="_blank" rel="noopener noreferrer">
                    <Laptop className="h-4 w-4" />
                    Mac Server Code
                  </Link>
                </Button>
              </CardContent>
            </Card>

            <Card className="text-center">
              <CardHeader>
                <div className="w-12 h-12 bg-purple-100 dark:bg-purple-900 rounded-full flex items-center justify-center mx-auto mb-4">
                  <Users className="h-6 w-6 text-purple-600 dark:text-purple-400" />
                </div>
                <CardTitle>3. Create Your Account</CardTitle>
              </CardHeader>
              <CardContent>
                <p className="text-muted-foreground mb-4">
                  Sign up for an account to sync devices and manage your AI processing
                </p>
                <Button className="w-full" variant="outline" asChild>
                  <Link href="/signup">Create Account</Link>
                </Button>
              </CardContent>
            </Card>
          </div>
        </div>

        {/* Development Info Section */}
        <div className="max-w-4xl mx-auto mb-16">
          <Card className="border-blue-200 dark:border-blue-800 bg-blue-50/50 dark:bg-blue-900/20">
            <CardHeader>
              <CardTitle className="flex items-center gap-2">
                <SiGithub className="h-5 w-5" />
                Open Source Development
              </CardTitle>
              <CardDescription>
                Orion Live is currently in active development and available as open source
              </CardDescription>
            </CardHeader>
            <CardContent className="space-y-4">
              <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
                <div>
                  <h3 className="font-semibold mb-2">Current Status</h3>
                  <ul className="space-y-1 text-sm text-muted-foreground">
                    <li>• iOS app in development</li>
                    <li>• Mac server for local inference</li>
                    <li>• Core computer vision algorithms</li>
                    <li>• Authentication and sync system</li>
                  </ul>
                </div>
                <div>
                  <h3 className="font-semibold mb-2">How to Try It</h3>
                  <ul className="space-y-1 text-sm text-muted-foreground">
                    <li>• Clone the repository from GitHub</li>
                    <li>• Follow setup instructions in README</li>
                    <li>• Compile for iOS using Xcode</li>
                    <li>• Run Mac server for local processing</li>
                  </ul>
                </div>
              </div>
              <div className="pt-4 border-t">
                <Button asChild>
                  <Link href="https://github.com/riddhimanrana/orion" target="_blank" rel="noopener noreferrer">
                    <SiGithub className="h-4 w-4" />
                    Explore the Code
                  </Link>
                </Button>
              </div>
            </CardContent>
          </Card>
        </div>

        {/* Setup Options */}
        <div className="max-w-6xl mx-auto mb-16">
          <h2 className="text-3xl font-bold text-center mb-8">
            Setup Options
          </h2>

          <Tabs defaultValue="comparison" className="w-full">
            <TabsList className="grid w-full grid-cols-3">
              <TabsTrigger value="comparison">Compare Options</TabsTrigger>
              <TabsTrigger value="local">Local Setup</TabsTrigger>
              <TabsTrigger value="cloud">Cloud Setup</TabsTrigger>
            </TabsList>

            <TabsContent value="comparison" className="space-y-6">
              <div className="grid grid-cols-1 lg:grid-cols-2 gap-8">
                {/* Local Option */}
                <Card
                  className={`cursor-pointer transition-all ${
                    selectedMethod === "local" ? "ring-2 ring-blue-500" : ""
                  }`}
                  onClick={() =>
                    setSelectedMethod(
                      selectedMethod === "local" ? null : "local",
                    )
                  }
                >
                  <CardHeader>
                    <div className="flex items-center gap-2 mb-2">
                      <Monitor className="h-6 w-6 text-green-600" />
                      <CardTitle className="text-xl">Local Inference</CardTitle>
                      <Badge variant="secondary">Recommended</Badge>
                    </div>
                    <CardDescription>
                      Process everything on your Mac for maximum privacy and
                      speed
                    </CardDescription>
                  </CardHeader>
                  <CardContent className="space-y-4">
                    <div className="space-y-3">
                      <div className="flex items-center gap-2 text-sm">
                        <Zap className="h-4 w-4 text-green-600" />
                        <span>Ultra-fast processing (~50ms)</span>
                      </div>
                      <div className="flex items-center gap-2 text-sm">
                        <Shield className="h-4 w-4 text-green-600" />
                        <span>
                          Complete privacy - nothing leaves your devices
                        </span>
                      </div>
                      <div className="flex items-center gap-2 text-sm">
                        <Wifi className="h-4 w-4 text-green-600" />
                        <span>Works offline</span>
                      </div>
                      <div className="flex items-center gap-2 text-sm">
                        <Crown className="h-4 w-4 text-green-600" />
                        <span>No API usage limits</span>
                      </div>
                    </div>

                    <div className="pt-4 border-t">
                      <p className="text-sm font-medium mb-2">Requirements:</p>
                      <ul className="text-sm text-muted-foreground space-y-1">
                        <li>• Mac with Apple Silicon (M1/M2/M3)</li>
                        <li>• iPhone (iOS 16+)</li>
                        <li>• Same Wi-Fi network</li>
                      </ul>
                    </div>

                    <Button className="w-full" asChild>
                      <Link href="https://github.com/riddhimanrana/orion" target="_blank" rel="noopener noreferrer">
                        <SiGithub className="h-4 w-4" />
                        Get Mac Server Code
                      </Link>
                    </Button>
                  </CardContent>
                </Card>

                {/* Cloud Option */}
                <Card
                  className={`cursor-pointer transition-all ${
                    selectedMethod === "cloud" ? "ring-2 ring-blue-500" : ""
                  }`}
                  onClick={() =>
                    setSelectedMethod(
                      selectedMethod === "cloud" ? null : "cloud",
                    )
                  }
                >
                  <CardHeader>
                    <div className="flex items-center gap-2 mb-2">
                      <Cloud className="h-6 w-6 text-blue-600" />
                      <CardTitle className="text-xl">Cloud Inference</CardTitle>
                      <Badge variant="outline">Easy Setup</Badge>
                    </div>
                    <CardDescription>
                      Use our cloud servers for processing - no additional setup
                      required
                    </CardDescription>
                  </CardHeader>
                  <CardContent className="space-y-4">
                    <div className="space-y-3">
                      <div className="flex items-center gap-2 text-sm">
                        <CheckCircle className="h-4 w-4 text-blue-600" />
                        <span>No additional software needed</span>
                      </div>
                      <div className="flex items-center gap-2 text-sm">
                        <Wifi className="h-4 w-4 text-blue-600" />
                        <span>Works from anywhere</span>
                      </div>
                      <div className="flex items-center gap-2 text-sm">
                        <Users className="h-4 w-4 text-blue-600" />
                        <span>Always up-to-date models</span>
                      </div>
                      <div className="flex items-center gap-2 text-sm">
                        <Zap className="h-4 w-4 text-blue-600" />
                        <span>Good performance (~150ms)</span>
                      </div>
                    </div>

                    <div className="pt-4 border-t">
                      <p className="text-sm font-medium mb-2">Requirements:</p>
                      <ul className="text-sm text-muted-foreground space-y-1">
                        <li>• iPhone (iOS 16+)</li>
                        <li>• Internet connection</li>
                        <li>• Orion Live account</li>
                      </ul>
                    </div>

                    <Button className="w-full" variant="outline" size="lg">
                      <CheckCircle className="h-4 w-4" />
                      Ready to Use
                    </Button>
                  </CardContent>
                </Card>
              </div>
            </TabsContent>

            <TabsContent value="local" className="space-y-6">
              <Card>
                <CardHeader>
                  <CardTitle className="flex items-center gap-2">
                    <Monitor className="h-6 w-6" />
                    Local Inference Setup
                  </CardTitle>
                  <CardDescription>
                    Set up Orion Live with local processing for maximum privacy
                    and performance
                  </CardDescription>
                </CardHeader>
                <CardContent className="space-y-6">
                  {/* Step 1 */}
                  <div className="flex gap-4">
                    <div className="flex-shrink-0 w-8 h-8 bg-blue-100 dark:bg-blue-900 rounded-full flex items-center justify-center">
                      <span className="text-sm font-bold text-blue-600 dark:text-blue-400">
                        1
                      </span>
                    </div>
                    <div className="flex-1">
                      <h3 className="font-semibold mb-2">
                        Get and Compile Mac Server
                      </h3>
                      <p className="text-sm text-muted-foreground mb-3">
                        Clone the Orion Live repository and compile the Mac server for local AI processing.
                      </p>
                      <Button className="mb-3" asChild>
                        <Link href="https://github.com/riddhimanrana/orion" target="_blank" rel="noopener noreferrer">
                          <SiGithub className="h-4 w-4" />
                          Get Server Code
                        </Link>
                      </Button>
                      <div className="text-sm text-muted-foreground">
                        <p className="mb-1">System Requirements:</p>
                        <ul className="space-y-1 ml-4">
                          <li>• macOS 13.0 or later</li>
                          <li>• Apple Silicon Mac (M1, M2, or M3)</li>
                          <li>• At least 8GB of RAM (16GB recommended)</li>
                          <li>• 2GB free disk space</li>
                        </ul>
                      </div>
                    </div>
                  </div>

                  {/* Step 2 */}
                  <div className="flex gap-4">
                    <div className="flex-shrink-0 w-8 h-8 bg-blue-100 dark:bg-blue-900 rounded-full flex items-center justify-center">
                      <span className="text-sm font-bold text-blue-600 dark:text-blue-400">
                        2
                      </span>
                    </div>
                    <div className="flex-1">
                      <h3 className="font-semibold mb-2">
                        Get iPhone App
                      </h3>
                      <p className="text-sm text-muted-foreground mb-3">
                        Compile the Orion Live iOS app from our GitHub repository using Xcode.
                      </p>
                      <Button variant="outline" asChild>
                        <Link href="https://github.com/riddhimanrana/orion" target="_blank" rel="noopener noreferrer">
                          <Code className="h-4 w-4" />
                          Get iOS App Code
                        </Link>
                      </Button>
                    </div>
                  </div>

                  {/* Step 3 */}
                  <div className="flex gap-4">
                    <div className="flex-shrink-0 w-8 h-8 bg-blue-100 dark:bg-blue-900 rounded-full flex items-center justify-center">
                      <span className="text-sm font-bold text-blue-600 dark:text-blue-400">
                        3
                      </span>
                    </div>
                    <div className="flex-1">
                      <h3 className="font-semibold mb-2">Connect Devices</h3>
                      <p className="text-sm text-muted-foreground mb-3">
                        Make sure both devices are on the same Wi-Fi network,
                        then pair them in the app.
                      </p>
                      <div className="p-3 bg-muted/50 rounded-lg text-sm">
                        <p className="font-medium mb-1">Connection Steps:</p>
                        <ol className="space-y-1 ml-4">
                          <li>1. Start the Mac server application</li>
                          <li>2. Open Orion Live on iPhone</li>
                          <li>3. Sign in with your account</li>
                          <li>4. Tap &quot;Connect to Mac Server&quot;</li>
                          <li>5. Your Mac should appear automatically</li>
                        </ol>
                      </div>
                    </div>
                  </div>
                </CardContent>
              </Card>
            </TabsContent>

            <TabsContent value="cloud" className="space-y-6">
              <Card>
                <CardHeader>
                  <CardTitle className="flex items-center gap-2">
                    <Cloud className="h-6 w-6" />
                    Cloud Inference Setup
                  </CardTitle>
                  <CardDescription>
                    Get started with cloud processing in minutes - no additional
                    software required
                  </CardDescription>
                </CardHeader>
                <CardContent className="space-y-6">
                  {/* Step 1 */}
                  <div className="flex gap-4">
                    <div className="flex-shrink-0 w-8 h-8 bg-blue-100 dark:bg-blue-900 rounded-full flex items-center justify-center">
                      <span className="text-sm font-bold text-blue-600 dark:text-blue-400">
                        1
                      </span>
                    </div>
                    <div className="flex-1">
                      <h3 className="font-semibold mb-2">
                        Get iPhone App
                      </h3>
                      <p className="text-sm text-muted-foreground mb-3">
                        Compile the Orion Live app from our GitHub repository using Xcode.
                      </p>
                      <Button asChild>
                        <Link href="https://github.com/riddhimanrana/orion" target="_blank" rel="noopener noreferrer">
                          <Code className="h-4 w-4" />
                          Get iOS App Code
                        </Link>
                      </Button>
                    </div>
                  </div>

                  {/* Step 2 */}
                  <div className="flex gap-4">
                    <div className="flex-shrink-0 w-8 h-8 bg-blue-100 dark:bg-blue-900 rounded-full flex items-center justify-center">
                      <span className="text-sm font-bold text-blue-600 dark:text-blue-400">
                        2
                      </span>
                    </div>
                    <div className="flex-1">
                      <h3 className="font-semibold mb-2">Sign In</h3>
                      <p className="text-sm text-muted-foreground mb-3">
                        Open the app and sign in with your Orion Live account.
                      </p>
                      <Button variant="outline" asChild>
                        <Link href="/login">Sign In to Your Account</Link>
                      </Button>
                    </div>
                  </div>

                  {/* Step 3 */}
                  <div className="flex gap-4">
                    <div className="flex-shrink-0 w-8 h-8 bg-green-100 dark:bg-green-900 rounded-full flex items-center justify-center">
                      <CheckCircle className="h-4 w-4 text-green-600 dark:text-green-400" />
                    </div>
                    <div className="flex-1">
                      <h3 className="font-semibold mb-2">
                        Start Using Orion Live
                      </h3>
                      <p className="text-sm text-muted-foreground mb-3">
                        You&apos;re all set! The app will automatically use
                        cloud processing.
                      </p>
                      <div className="p-3 bg-amber-50 dark:bg-amber-900/20 border border-amber-200 dark:border-amber-800 rounded-lg">
                        <p className="text-sm text-amber-800 dark:text-amber-200">
                          <strong>Development Status:</strong> Orion Live is currently in active development. 
                          Create an account to stay updated on progress and releases.
                        </p>
                      </div>
                    </div>
                  </div>
                </CardContent>
              </Card>
            </TabsContent>
          </Tabs>
        </div>

        {/* FAQ Section */}
        <div className="max-w-4xl mx-auto">
          <h2 className="text-3xl font-bold text-center mb-8">
            Frequently Asked Questions
          </h2>
          <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
            <Card>
              <CardHeader>
                <CardTitle className="text-lg">
                  Can I download the apps now?
                </CardTitle>
              </CardHeader>
              <CardContent>
                <p className="text-sm text-muted-foreground">
                  Orion Live is currently in active development. While there are no App Store releases yet, 
                  you can compile and test the apps yourself from our open-source GitHub repository.
                </p>
              </CardContent>
            </Card>

            <Card>
              <CardHeader>
                <CardTitle className="text-lg">
                  What do I need to compile the apps?
                </CardTitle>
              </CardHeader>
              <CardContent>
                <p className="text-sm text-muted-foreground">
                  For iOS: Xcode with iOS 16+ SDK. For Mac server: macOS 13+ with Xcode Command Line Tools. 
                  Follow the setup instructions in the GitHub repository README.
                </p>
              </CardContent>
            </Card>

            <Card>
              <CardHeader>
                <CardTitle className="text-lg">Is the project open source?</CardTitle>
              </CardHeader>
              <CardContent>
                <p className="text-sm text-muted-foreground">
                  Yes! Orion Live is completely open source. You can view the code, contribute to development, 
                  report issues, and suggest features on our GitHub repository.
                </p>
              </CardContent>
            </Card>

            <Card>
              <CardHeader>
                <CardTitle className="text-lg">When will it be released?</CardTitle>
              </CardHeader>
              <CardContent>
                <p className="text-sm text-muted-foreground">
                  We&apos;re actively developing Orion Live. Follow our GitHub repository or create an account 
                  to stay updated on development progress and release announcements.
                </p>
              </CardContent>
            </Card>
          </div>
        </div>

        {/* CTA Section */}
        <div className="text-center mt-16">
          <h2 className="text-2xl font-bold mb-4">Ready to explore the code?</h2>
          <p className="text-muted-foreground mb-6 max-w-2xl mx-auto">
            Orion Live is open source and actively being developed. Check out the repository 
            to compile and test the apps yourself, or create an account to stay updated.
          </p>
          <div className="flex flex-col sm:flex-row gap-4 justify-center">
            <Button size="lg" className="px-8" asChild>
              <Link href="https://github.com/riddhimanrana/orion" target="_blank" rel="noopener noreferrer">
                <SiGithub className="h-5 w-5" />
                Explore GitHub Repository
              </Link>
            </Button>
            <Button variant="outline" size="lg" className="px-8" asChild>
              <Link href="/signup">
                Create Account
                <ArrowRight className="ml-2 h-5 w-5" />
              </Link>
            </Button>
          </div>
        </div>
      </div>
    </div>
  );
}
