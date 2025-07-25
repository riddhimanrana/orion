"use client";

import { useEffect, Suspense } from "react";
import { useSearchParams } from "next/navigation";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { CheckCircle } from "lucide-react";

function CloseWindowContent() {
  const searchParams = useSearchParams();
  const message = searchParams.get("message") || "You can now return to the app";

  useEffect(() => {
    // Try to close the window multiple times with different methods
    const closeAttempts = [
      () => window.close(),
      () => window.self.close(),
      () => window.top?.close(),
    ];

    closeAttempts.forEach((attempt, index) => {
      setTimeout(() => {
        try {
          attempt();
        } catch (error) {
          console.log(`Close attempt ${index + 1} failed:`, error);
        }
      }, index * 500);
    });

    // If we're still here after 3 seconds, show instructions
    const timer = setTimeout(() => {
      document.body.style.display = "block";
    }, 3000);

    return () => clearTimeout(timer);
  }, []);

  return (
    <div className="min-h-screen flex items-center justify-center p-4 bg-gradient-to-br from-background via-background to-muted/20">
      <div className="w-full max-w-md">
        <Card className="border-border/50 shadow-lg">
          <CardHeader className="text-center space-y-4">
            <div className="mx-auto w-16 h-16 bg-green-100 dark:bg-green-900/20 rounded-full flex items-center justify-center">
              <CheckCircle className="w-8 h-8 text-green-600 dark:text-green-400" />
            </div>
            <div>
              <CardTitle className="text-2xl">Success!</CardTitle>
            </div>
          </CardHeader>
          <CardContent className="text-center space-y-4">
            <p className="text-muted-foreground">{message}</p>
            <p className="text-xs text-muted-foreground">
              This window should close automatically. If it doesn&apos;t, you can close it manually.
            </p>
          </CardContent>
        </Card>
      </div>
    </div>
  );
}

export default function CloseWindowPage() {
  return (
    <div style={{ display: "none" }}>
      <Suspense fallback={<div>Loading...</div>}>
        <CloseWindowContent />
      </Suspense>
    </div>
  );
}
