"use client";

import { useState, useEffect, Suspense } from "react";
import { useSearchParams } from "next/navigation";
import { Button } from "@/components/ui/button";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import {
  Loader2,
  AlertCircle,
  XCircle,
  Lock,
  ArrowLeft,
} from "lucide-react";
import Link from "next/link";

function InvalidResetTokenContent() {
  const [errorMessage, setErrorMessage] = useState<string>("");
  const [errorTitle, setErrorTitle] = useState<string>("Invalid reset link");
  const searchParams = useSearchParams();

  useEffect(() => {
    // Extract error information from URL
    const error = searchParams.get("error");
    const errorCode = searchParams.get("error_code");
    const errorDescription = searchParams.get("error_description");

    // Use the error description from Supabase if available
    if (errorDescription) {
      const decodedDescription = decodeURIComponent(
        errorDescription.replace(/\+/g, " "),
      );
      setErrorMessage(decodedDescription);
    } else {
      // Fallback error messages based on error codes
      switch (errorCode) {
        case "otp_expired":
          setErrorTitle("Reset link expired");
          setErrorMessage(
            "The password reset link has expired. Password reset links are only valid for 1 hour for security reasons.",
          );
          break;
        case "access_denied":
          setErrorTitle("Access denied");
          setErrorMessage(
            "Access denied. The reset link may be invalid, already used, or expired.",
          );
          break;
        case "invalid_request":
          setErrorTitle("Invalid request");
          setErrorMessage(
            "The password reset request is invalid. Please try requesting a new reset link.",
          );
          break;
        default:
          setErrorTitle("Invalid reset link");
          setErrorMessage(
            error
              ? `Authentication error: ${error}`
              : "The password reset link is invalid or has expired. Please request a new one.",
          );
      }
    }

    // Set a default message if none was set
    if (!errorMessage && !errorDescription && !errorCode) {
      setErrorMessage(
        "The password reset link is invalid or has expired. Please request a new reset link to continue.",
      );
    }
  }, [searchParams, errorMessage]);

  return (
    <div className="min-h-screen flex items-center justify-center p-4 bg-gradient-to-br from-background via-background to-muted/20">
      <div className="w-full max-w-md">
        <Card className="border-border/50 shadow-lg">
          <CardHeader className="text-center space-y-4">
            <div className="mx-auto w-16 h-16 bg-red-100 dark:bg-red-900/20 rounded-full flex items-center justify-center">
              <XCircle className="w-8 h-8 text-red-600 dark:text-red-400" />
            </div>
            <div>
              <CardTitle className="text-2xl">{errorTitle}</CardTitle>
              <CardDescription className="mt-2">
                Unable to process your password reset request
              </CardDescription>
            </div>
          </CardHeader>
          <CardContent className="space-y-4 text-center">
            <div className="p-4 bg-muted/50 rounded-lg space-y-2">
              <AlertCircle className="w-5 h-5 text-red-600 dark:text-red-400 mx-auto" />
              <p className="text-sm font-medium text-destructive">
                Error Details
              </p>
              <p className="text-xs text-muted-foreground">
                {errorMessage}
              </p>
            </div>

            <div className="p-3 bg-blue-50 dark:bg-blue-950/20 border border-blue-200 dark:border-blue-800 rounded-md">
              <p className="text-xs text-blue-700 dark:text-blue-300">
                <strong>💡 What to do next:</strong>
                <br />
                • Request a new password reset link
                <br />
                • Check that you&apos;re using the latest email
                <br />
                • Make sure the link hasn&apos;t been used already
              </p>
            </div>

            <div className="space-y-2">
              <Button asChild className="w-full">
                <Link href="/reset-password">
                  <Lock className="w-4 h-4 mr-2" />
                  Request new reset link
                </Link>
              </Button>

              <Button asChild variant="outline" className="w-full">
                <Link href="/login">
                  <ArrowLeft className="w-4 h-4 mr-2" />
                  Back to sign in
                </Link>
              </Button>
            </div>

            <div className="text-center text-sm text-muted-foreground">
              Need help?{" "}
              <Link href="/contact" className="hover:underline text-primary">
                Contact support
              </Link>
            </div>
          </CardContent>
        </Card>

        <div className="mt-8 text-center text-xs text-muted-foreground">
          Password reset links expire after 1 hour for security reasons.
        </div>
      </div>
    </div>
  );
}

export default function InvalidResetTokenPage() {
  return (
    <Suspense
      fallback={
        <div className="min-h-screen flex items-center justify-center p-4">
          <div className="w-full max-w-md">
            <Card className="border-border/50 shadow-lg">
              <CardHeader className="text-center space-y-4">
                <div className="mx-auto w-16 h-16 bg-blue-100 dark:bg-blue-900/20 rounded-full flex items-center justify-center">
                  <Loader2 className="w-8 h-8 text-blue-600 dark:text-blue-400 animate-spin" />
                </div>
                <div>
                  <CardTitle className="text-2xl">Loading</CardTitle>
                  <CardDescription className="mt-2">
                    Please wait...
                  </CardDescription>
                </div>
              </CardHeader>
            </Card>
          </div>
        </div>
      }
    >
      <InvalidResetTokenContent />
    </Suspense>
  );
}
