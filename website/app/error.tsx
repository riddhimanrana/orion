"use client";

import { useEffect } from "react";
import { Button } from "@/components/ui/button";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { AlertTriangle, Home, RefreshCw } from "lucide-react";
import Link from "next/link";

export default function Error({
  error,
  reset,
}: {
  error: Error & { digest?: string };
  reset: () => void;
}) {
  useEffect(() => {
    // Log the error to an error reporting service
    console.error("Application error:", error);
  }, [error]);

  return (
    <div className="min-h-screen flex items-center justify-center p-4 bg-gradient-to-br from-background via-background to-muted/20">
      <div className="w-full max-w-md">
        <div className="text-center mb-8">
          <div className="w-16 h-16 rounded-full bg-red-500/10 flex items-center justify-center mx-auto mb-4">
            <AlertTriangle className="w-8 h-8 text-red-500" />
          </div>
          <h1 className="text-3xl font-bold tracking-tight">
            Something went wrong
          </h1>
          <p className="text-muted-foreground mt-2">
            We encountered an unexpected error
          </p>
        </div>

        <Card className="border-border/50 shadow-lg">
          <CardHeader className="text-center">
            <CardTitle className="text-xl">Application Error</CardTitle>
            <CardDescription>
              An unexpected error has occurred. This could be due to a temporary
              issue or a problem with your request.
            </CardDescription>
          </CardHeader>
          <CardContent className="space-y-6">
            {process.env.NODE_ENV === "development" && (
              <div className="p-4 bg-muted rounded-lg">
                <p className="text-sm font-medium mb-2">Error Details:</p>
                <pre className="text-xs text-muted-foreground overflow-auto">
                  {error.message}
                </pre>
              </div>
            )}

            <div className="space-y-3">
              <Button onClick={reset} className="w-full">
                <RefreshCw className="w-4 h-4 mr-2" />
                Try Again
              </Button>

              <Button variant="outline" asChild className="w-full">
                <Link href="/">
                  <Home className="w-4 h-4 mr-2" />
                  Back to Home
                </Link>
              </Button>
            </div>
          </CardContent>
        </Card>

        <div className="mt-8 text-center text-xs text-muted-foreground">
          If this problem persists, please{" "}
          <Link href="/contact" className="hover:underline text-primary">
            contact our support team
          </Link>
          .
        </div>
      </div>
    </div>
  );
}
