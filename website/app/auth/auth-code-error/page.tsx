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
  AlertTriangle,
  ArrowLeft,
  RefreshCw,
  AlertCircle,
  Loader2,
  CheckCircle,
} from "lucide-react";
import Link from "next/link";

function AuthCodeErrorContent() {
  const [errorMessage, setErrorMessage] = useState<string>("");
  const [errorTitle, setErrorTitle] = useState<string>("Authentication Error");
  const [isMobileSignupOnDesktop, setIsMobileSignupOnDesktop] =
    useState<boolean>(false);
  const searchParams = useSearchParams();

  useEffect(() => {
    // Extract error information from URL
    const error = searchParams.get("error");
    const errorCode = searchParams.get("error_code");
    const errorDescription = searchParams.get("error_description");
    const redirectTo = searchParams.get("redirectTo");

    // Check if this is a mobile signup link opened on desktop
    const isMobileRedirect =
      redirectTo && decodeURIComponent(redirectTo).startsWith("orion://");
    const isMobileDevice =
      /Android|webOS|iPhone|iPad|iPod|BlackBerry|IEMobile|Opera Mini/i.test(
        navigator.userAgent,
      );

    if (isMobileRedirect && !isMobileDevice) {
      setIsMobileSignupOnDesktop(true);
      setErrorTitle("Signup Already Confirmed");
      setErrorMessage(
        "Your mobile account has been successfully confirmed. Please use the Orion Live app to sign in.",
      );
      return;
    }

    // Check for specific mobile signup errors
    if (
      isMobileRedirect &&
      (errorCode === "otp_expired" || error === "access_denied")
    ) {
      setIsMobileSignupOnDesktop(true);
      setErrorTitle("Account Already Confirmed");
      setErrorMessage(
        "Your email has already been confirmed. You can now sign in to the Orion Live app with your credentials.",
      );
      return;
    }

    // Use the error description from Supabase if available
    if (errorDescription) {
      const decodedDescription = decodeURIComponent(
        errorDescription.replace(/\+/g, " "),
      );
      setErrorMessage(decodedDescription);
    } else {
      // Fallback error messages based on error codes
      switch (errorCode) {
        case "access_denied":
          setErrorTitle("Access Denied");
          setErrorMessage(
            "You denied access to the application or the request was cancelled.",
          );
          break;
        case "unauthorized_client":
          setErrorTitle("Unauthorized Client");
          setErrorMessage(
            "The application is not authorized to perform this request.",
          );
          break;
        case "invalid_request":
          setErrorTitle("Invalid Request");
          setErrorMessage(
            "The authentication request was invalid or malformed.",
          );
          break;
        case "server_error":
          setErrorTitle("Server Error");
          setErrorMessage(
            "A server error occurred during authentication. Please try again.",
          );
          break;
        default:
          setErrorTitle("Authentication Error");
          setErrorMessage(
            error
              ? `Authentication failed: ${error}`
              : "Something went wrong during the sign-in process.",
          );
      }
    }

    // Set a default message if none was set
    if (!errorMessage && !errorDescription && !errorCode && !error) {
      setErrorMessage(
        "An unexpected error occurred during authentication. Please try signing in again.",
      );
    }
  }, [searchParams, errorMessage]);
  return (
    <div className="min-h-screen flex items-center justify-center p-4 bg-gradient-to-br from-background via-background to-muted/20">
      <div className="w-full max-w-md">
        <div className="text-center mb-8">
          <div
            className={`w-16 h-16 rounded-full flex items-center justify-center mx-auto mb-4 ${
              isMobileSignupOnDesktop ? "bg-green-500/10" : "bg-red-500/10"
            }`}
          >
            {isMobileSignupOnDesktop ? (
              <CheckCircle className="w-8 h-8 text-green-500" />
            ) : (
              <AlertTriangle className="w-8 h-8 text-red-500" />
            )}
          </div>
          <h1 className="text-3xl font-bold tracking-tight">{errorTitle}</h1>
          <p className="text-muted-foreground mt-2">
            {errorMessage || "Something went wrong during the sign-in process"}
          </p>
        </div>

        <Card className="border-border/50 shadow-lg">
          <CardHeader className="text-center">
            <CardTitle className="text-xl">
              {isMobileSignupOnDesktop ? "Account Ready" : "Unable to Sign In"}
            </CardTitle>
            <CardDescription>
              {isMobileSignupOnDesktop
                ? "Your account is confirmed and ready to use in the mobile app."
                : "We encountered an error while trying to authenticate your account."}
            </CardDescription>
          </CardHeader>
          <CardContent className="space-y-6">
            {errorMessage && (
              <div className="p-4 bg-muted/50 rounded-lg space-y-2">
                <div className="flex items-center justify-left gap-2">
                  <AlertCircle className="w-4 h-4 text-red-600 dark:text-red-400" />
                  <p className="text-sm font-medium text-destructive m-0">
                    Error Details
                  </p>
                </div>
                <p className="text-xs text-muted-foreground">{errorMessage}</p>
              </div>
            )}

            <div className="p-3 bg-blue-50 dark:bg-blue-950/20 border border-blue-200 dark:border-blue-800 rounded-md">
              {isMobileSignupOnDesktop ? (
                <p className="text-xs text-blue-700 dark:text-blue-300">
                  <strong>For Orion Live App Login:</strong>
                  <br />
                  • Open the Orion Live app on your mobile device
                  <br />
                  • Sign in with your email and password
                  <br />• Your account is ready to use!
                </p>
              ) : (
                <p className="text-xs text-blue-700 dark:text-blue-300">
                  <strong>Common causes:</strong>
                  <br />
                  • Authentication process was cancelled
                  <br />
                  • Temporary issue with the authentication provider
                  <br />
                  • Network connectivity problems
                  <br />• Browser cookies or JavaScript disabled
                </p>
              )}
            </div>

            <div className="space-y-3">
              {isMobileSignupOnDesktop ? (
                <></>
              ) : (
                <Button asChild className="w-full">
                  <Link href="/login">
                    <RefreshCw className="w-4 h-4 mr-2" />
                    Try Again
                  </Link>
                </Button>
              )}

              <Button variant="outline" asChild className="w-full">
                <Link href="/">
                  <ArrowLeft className="w-4 h-4 mr-2" />
                  Back to Home
                </Link>
              </Button>
            </div>
          </CardContent>
        </Card>

        <div className="mt-8 text-center text-xs text-muted-foreground">
          If you continue to experience issues, please{" "}
          <Link href="/contact" className="hover:underline text-primary">
            contact our support team
          </Link>{" "}
          for assistance.
        </div>
      </div>
    </div>
  );
}

export default function AuthCodeErrorPage() {
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
      <AuthCodeErrorContent />
    </Suspense>
  );
}
