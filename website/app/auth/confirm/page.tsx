"use client";

import { useState, useEffect, Suspense } from "react";
import { useSearchParams, useRouter } from "next/navigation";
import { Button } from "@/components/ui/button";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import {
  CheckCircle,
  XCircle,
  Loader2,
  Mail,
  ArrowRight,
  RefreshCw,
} from "lucide-react";
import Link from "next/link";
import { createClient } from "@/utils/supabase/client";
import { toast } from "sonner";

function EmailConfirmContent() {
  const [status, setStatus] = useState<"loading" | "success" | "error">(
    "loading",
  );
  const [errorMessage, setErrorMessage] = useState<string>("");
  const [userEmail, setUserEmail] = useState<string>("");
  const searchParams = useSearchParams();
  const router = useRouter();

  const success = searchParams.get("success");
  const error = searchParams.get("error");
  const email = searchParams.get("email");
  const redirectTo = searchParams.get("redirectTo");
  const note = searchParams.get("note"); // For additional context on mobile confirmations

  // For direct token verification (legacy support)
  const token_hash = searchParams.get("token_hash");
  const type = searchParams.get("type");

  useEffect(() => {
    const handleConfirmation = async () => {
      // Handle URL-based success/error (from callback route)
      if (
        success === "email_confirmed" ||
        success === "mobile_signup_confirmed"
      ) {
        setStatus("success");
        setUserEmail(email ? decodeURIComponent(email) : "");

        if (success === "mobile_signup_confirmed") {
          if (note === "already_confirmed") {
            toast.success("Account already confirmed!", {
              description:
                "Your mobile account is ready. Use the Orion Live app to sign in.",
            });
          } else if (note === "session_error") {
            toast.success("Account confirmed successfully!", {
              description:
                "Your account is ready. Use the Orion Live app to sign in.",
            });
          } else {
            toast.success("Mobile account confirmed!", {
              description:
                "Your account is ready. Use the Orion Live app to sign in.",
            });
          }
        } else {
          toast.success("Email confirmed successfully!", {
            description: "Your account is now active.",
          });
        }

        // Check if this is a mobile auth callback and if user is on mobile/desktop hence the native name
        const isMobileAuthCallback =
          redirectTo && decodeURIComponent(redirectTo).startsWith("orion://");
        const isMobileDevice =
          /Android|webOS|iPhone|iPad|iPod|BlackBerry|IEMobile|Opera Mini/i.test(
            navigator.userAgent,
          );

        if (isMobileAuthCallback) {
          if (isMobileDevice && success === "email_confirmed") {
            // Only auto-redirect for email_confirmed on mobile (where we have a session)
            setTimeout(() => {
              const bridgeUrl = `/auth/native-bridge?redirectTo=${encodeURIComponent(redirectTo)}`;
              window.location.href = bridgeUrl;
            }, 1500);
          } else if (isMobileDevice && success === "mobile_signup_confirmed") {
            // For mobile signup confirmed, close the browser window
            setTimeout(() => {
              // Try to close the window (works in ASWebAuthenticationSession)
              window.close();

              // Fallback: redirect to a closing page if window.close() doesn't work
              setTimeout(() => {
                window.location.href = `/auth/close-window?message=${encodeURIComponent("Please return to the Orion Live app")}`;
              }, 1000);
            }, 2000);
          }
          // For desktop users we're just not going to do signups...maybe we'll do it later?
        }

        return;
      }

      if (error) {
        setStatus("error");
        switch (error) {
          case "confirmation_failed":
            setErrorMessage(
              "Failed to confirm email. The link may be invalid or expired.",
            );
            break;
          case "unexpected_error":
            setErrorMessage("An unexpected error occurred. Please try again.");
            break;
          default:
            setErrorMessage("Failed to confirm email. Please try again.");
        }
        return;
      }

      // Legacy direct token verification support
      if (token_hash && type === "email") {
        try {
          const supabase = createClient();

          const { data, error: verifyError } = await supabase.auth.verifyOtp({
            token_hash,
            type: "email",
          });

          if (verifyError) {
            console.error("Email confirmation error:", verifyError);
            setStatus("error");

            if (verifyError.message.includes("expired")) {
              setErrorMessage(
                "This confirmation link has expired. Please request a new one.",
              );
            } else if (verifyError.message.includes("invalid")) {
              setErrorMessage(
                "This confirmation link is invalid. Please check your email for the correct link.",
              );
            } else if (verifyError.message.includes("already confirmed")) {
              setErrorMessage(
                "This email has already been confirmed. You can sign in now.",
              );
            } else {
              setErrorMessage(
                verifyError.message ||
                  "Failed to confirm email. Please try again.",
              );
            }
            return;
          }

          if (data.user) {
            setStatus("success");
            setUserEmail(data.user.email || "");

            toast.success("Email confirmed successfully!", {
              description: "Your account is now active.",
            });

            // Don't auto-redirect, let user click the button
          } else {
            setStatus("error");
            setErrorMessage("Failed to confirm email. Please try again.");
          }
        } catch (error) {
          console.error("Unexpected error during email confirmation:", error);
          setStatus("error");
          setErrorMessage("An unexpected error occurred. Please try again.");
        }
        return;
      }

      // No valid parameters found
      setStatus("error");
      setErrorMessage(
        "Invalid confirmation link. Please check your email for the correct link.",
      );
    };

    handleConfirmation();
  }, [success, error, email, redirectTo, note, token_hash, type, router]);

  if (status === "loading") {
    return (
      <div className="min-h-screen flex items-center justify-center p-4 bg-gradient-to-br from-background via-background to-muted/20">
        <div className="w-full max-w-md">
          <Card className="border-border/50 shadow-lg">
            <CardHeader className="text-center space-y-4">
              <div className="mx-auto w-16 h-16 bg-blue-100 dark:bg-blue-900/20 rounded-full flex items-center justify-center">
                <Loader2 className="w-8 h-8 text-blue-600 dark:text-blue-400 animate-spin" />
              </div>
              <div>
                <CardTitle className="text-2xl">
                  Confirming your email
                </CardTitle>
                <CardDescription className="mt-2">
                  Please wait while we verify your email address
                </CardDescription>
              </div>
            </CardHeader>
            <CardContent className="text-center">
              <div className="space-y-4">
                <div className="flex items-center justify-center space-x-2 text-sm text-muted-foreground">
                  <Mail className="w-4 h-4" />
                  <span>Verifying confirmation token...</span>
                </div>
              </div>
            </CardContent>
          </Card>
        </div>
      </div>
    );
  }

  if (status === "success") {
    const isMobileAuthCallback =
      redirectTo && decodeURIComponent(redirectTo).startsWith("orion://");
    const isMobileDevice =
      /Android|webOS|iPhone|iPad|iPod|BlackBerry|IEMobile|Opera Mini/i.test(
        navigator.userAgent,
      );
    const isMobileSignupConfirmed = success === "mobile_signup_confirmed";

    return (
      <div className="min-h-screen flex items-center justify-center p-4 bg-gradient-to-br from-background via-background to-muted/20">
        <div className="w-full max-w-md">
          <Card className="border-border/50 shadow-lg">
            <CardHeader className="text-center space-y-4">
              <div className="mx-auto w-16 h-16 bg-green-100 dark:bg-green-900/20 rounded-full flex items-center justify-center">
                <CheckCircle className="w-8 h-8 text-green-600 dark:text-green-400" />
              </div>
              <div>
                <CardTitle className="text-2xl">
                  {isMobileSignupConfirmed
                    ? "Account confirmed!"
                    : "Email confirmed!"}
                </CardTitle>
                <CardDescription className="mt-2">
                  {isMobileSignupConfirmed
                    ? "Your Orion Live account has been successfully activated"
                    : "Your account has been successfully activated"}
                  {userEmail && (
                    <>
                      {" "}
                      for{" "}
                      <span className="font-medium text-foreground">
                        {userEmail}
                      </span>
                    </>
                  )}
                </CardDescription>
              </div>
            </CardHeader>
            <CardContent className="space-y-4 text-center">
              <div className="p-4 bg-green-50 dark:bg-green-900/10 border border-green-200 dark:border-green-800 rounded-lg space-y-2">
                <CheckCircle className="w-5 h-5 text-green-600 dark:text-green-400 mx-auto" />
                <p className="text-sm font-medium text-green-800 dark:text-green-200">
                  Account activated successfully
                </p>
                <p className="text-xs text-green-600 dark:text-green-400">
                  {isMobileSignupConfirmed
                    ? "Open the Orion Live app and sign in with your credentials"
                    : "You can now sign in and access all features"}
                </p>
              </div>

              {/* Mobile auth callback on mobile device */}
              {isMobileAuthCallback &&
                isMobileDevice &&
                !isMobileSignupConfirmed && (
                  <div className="space-y-3">
                    <div className="p-4 bg-blue-50 dark:bg-blue-900/10 border border-blue-200 dark:border-blue-800 rounded-lg">
                      <p className="text-sm text-blue-800 dark:text-blue-200">
                        Opening Orion Live app...
                      </p>
                    </div>
                    <Button
                      onClick={() => {
                        // Go through the mobile bridge to get authenticated tokens
                        const bridgeUrl = `/auth/native-bridge?redirectTo=${encodeURIComponent(redirectTo)}`;
                        window.location.href = bridgeUrl;
                      }}
                      className="w-full"
                    >
                      <ArrowRight className="w-4 h-4 mr-2" />
                      Open Orion Live
                    </Button>
                  </div>
                )}

              {/* Mobile auth callback on desktop OR mobile signup confirmed */}
              {((isMobileAuthCallback && !isMobileDevice) ||
                isMobileSignupConfirmed) && (
                <div className="space-y-3">
                  {/* <div className="p-4 bg-green-50 dark:bg-green-900/10 border border-green-200 dark:border-green-800 rounded-lg">
                    <p className="text-sm text-green-800 dark:text-green-200 font-medium mb-2">
                      🎉 {isMobileSignupConfirmed
                        ? "Mobile account confirmed successfully!"
                        : "This signup was intended for the mobile app"
                      }
                    </p>
                    <p className="text-xs text-green-700 dark:text-green-300">
                      {isMobileSignupConfirmed
                        ? "Your account is ready! Open the Orion Live app on your mobile device and sign in with your email and password to get started."
                        : "Please open the Orion Live app on your mobile device and sign in with your email and password to continue."
                      }
                    </p>
                  </div> */}

                  <div className="p-3 bg-blue-50 dark:bg-blue-900/10 border border-blue-200 dark:border-blue-800 rounded-lg">
                    <p className="text-xs text-blue-700 dark:text-blue-300">
                      <strong>Next steps:</strong>
                      <br />
                      1. Open the Orion Live app on your phone
                      <br />
                      2. Tap &quot;Log In&quot; and enter your credentials
                      <br />
                      3. Start using Orion Live!
                    </p>
                  </div>

                  <Button
                    onClick={() => router.push("/")}
                    variant="outline"
                    className="w-full"
                  >
                    <ArrowRight className="w-4 h-4 mr-2" />
                    Continue to website
                  </Button>
                </div>
              )}

              {/* Regular web signup */}
              {!isMobileAuthCallback && !isMobileSignupConfirmed && (
                <div className="space-y-3">
                  <Button
                    onClick={() => {
                      const targetUrl = redirectTo
                        ? decodeURIComponent(redirectTo)
                        : "/dashboard";
                      router.push(targetUrl);
                    }}
                    className="w-full"
                  >
                    <ArrowRight className="w-4 h-4 mr-2" />
                    Continue to {redirectTo ? "your destination" : "dashboard"}
                  </Button>
                </div>
              )}
            </CardContent>
          </Card>
        </div>
      </div>
    );
  }

  // Error state
  return (
    <div className="min-h-screen flex items-center justify-center p-4 bg-gradient-to-br from-background via-background to-muted/20">
      <div className="w-full max-w-md">
        <Card className="border-border/50 shadow-lg">
          <CardHeader className="text-center space-y-4">
            <div className="mx-auto w-16 h-16 bg-red-100 dark:bg-red-900/20 rounded-full flex items-center justify-center">
              <XCircle className="w-8 h-8 text-red-600 dark:text-red-400" />
            </div>
            <div>
              <CardTitle className="text-2xl">Confirmation failed</CardTitle>
              <CardDescription className="mt-2">
                We couldn&apos;t confirm your email address
              </CardDescription>
            </div>
          </CardHeader>
          <CardContent className="space-y-4 text-center">
            <div className="p-4 bg-red-50 dark:bg-red-900/10 border border-red-200 dark:border-red-800 rounded-lg">
              <p className="text-sm text-red-800 dark:text-red-200">
                {errorMessage}
              </p>
            </div>

            <div className="space-y-3">
              {errorMessage.includes("expired") && (
                <Button
                  onClick={() => router.push("/signup")}
                  className="w-full"
                  variant="outline"
                >
                  <RefreshCw className="w-4 h-4 mr-2" />
                  Request new confirmation
                </Button>
              )}

              {errorMessage.includes("already confirmed") && (
                <Button
                  onClick={() => router.push("/login")}
                  className="w-full"
                >
                  <ArrowRight className="w-4 h-4 mr-2" />
                  Sign in to your account
                </Button>
              )}

              <div className="space-y-2">
                <Button
                  onClick={() => window.location.reload()}
                  variant="outline"
                  className="w-full"
                >
                  <RefreshCw className="w-4 h-4 mr-2" />
                  Try again
                </Button>

                <div className="text-xs text-muted-foreground">
                  Need help?{" "}
                  <Link
                    href="/contact"
                    className="text-primary hover:underline"
                  >
                    Contact support
                  </Link>
                </div>
              </div>
            </div>
          </CardContent>
        </Card>
      </div>
    </div>
  );
}

export default function EmailConfirmPage() {
  return (
    <Suspense
      fallback={
        <div className="min-h-screen flex items-center justify-center">
          <div className="text-center">
            <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-primary mx-auto"></div>
            <p className="text-muted-foreground mt-2">Loading...</p>
          </div>
        </div>
      }
    >
      <EmailConfirmContent />
    </Suspense>
  );
}
