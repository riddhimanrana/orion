"use client";

import { useState, useEffect, Suspense } from "react";
import { useParams, useSearchParams } from "next/navigation";
import { useForm } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
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
import {
  Loader2,
  AlertCircle,
  Eye,
  EyeOff,
  CheckCircle,
  XCircle,
  Lock,
  ArrowLeft,
} from "lucide-react";
import Link from "next/link";
import { toast } from "sonner";
import { useRouter } from "next/navigation";
import {
  passwordResetConfirmSchema,
  type PasswordResetConfirmFormData,
} from "@/lib/auth-schemas";
import { confirmPasswordReset } from "../actions";

function PasswordResetTokenContent() {
  const [loading, setLoading] = useState(false);
  const [showPassword, setShowPassword] = useState(false);
  const [showConfirmPassword, setShowConfirmPassword] = useState(false);
  const [resetSuccess, setResetSuccess] = useState(false);
  const [tokenValid, setTokenValid] = useState<boolean | null>(null);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);

  const params = useParams();
  const searchParams = useSearchParams();
  const router = useRouter();

  // Extract token from URL path
  const token = params.token as string;

  // Extract error information from URL
  const error = searchParams.get("error");
  const errorCode = searchParams.get("error_code");
  const errorDescription = searchParams.get("error_description");
  const type = searchParams.get("type");

  const form = useForm<PasswordResetConfirmFormData>({
    resolver: zodResolver(passwordResetConfirmSchema),
    defaultValues: {
      password: "",
      confirmPassword: "",
    },
  });

  useEffect(() => {
    // Check for errors from Supabase first
    if (error) {
      setTokenValid(false);

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
            setErrorMessage(
              "The password reset link has expired. Please request a new one.",
            );
            break;
          case "access_denied":
            setErrorMessage(
              "Access denied. The reset link may be invalid or already used.",
            );
            break;
          default:
            setErrorMessage(
              "The password reset link is invalid or has expired.",
            );
        }
      }
      return;
    }

    // Validate token presence and type
    if (!token) {
      setTokenValid(false);
      setErrorMessage(
        "No reset token found in the URL. Please use the link from your email.",
      );
    } else if (type && type !== "recovery") {
      setTokenValid(false);
      setErrorMessage(
        "Invalid link type. Please use the password reset link from your email.",
      );
    } else {
      setTokenValid(true);
      setErrorMessage(null);
    }
  }, [token, type, error, errorCode, errorDescription]);

  const handlePasswordReset = async (data: PasswordResetConfirmFormData) => {
    if (!token) {
      toast.error("Invalid reset token", {
        description: "Please request a new password reset link.",
      });
      return;
    }

    setLoading(true);
    try {
      const result = await confirmPasswordReset(data, token);

      if (result?.error) {
        // Handle error response which can be string or ErrorResponse object
        if (typeof result.error === "string") {
          // Handle string errors
          if (
            result.error.includes("expired") ||
            result.error.includes("invalid") ||
            result.error.includes("JWT") ||
            result.error.includes("Invalid or expired reset link")
          ) {
            toast.error("Reset link expired", {
              description:
                "This password reset link has expired or is invalid.",
              action: {
                label: "Request New Link",
                onClick: () => (window.location.href = "/reset-password"),
              },
            });
            setTokenValid(false);
            setErrorMessage(
              "This password reset link has expired or is invalid.",
            );
          } else if (result.error.includes("same as the old password")) {
            toast.error("Password unchanged", {
              description:
                "Your new password must be different from your current password.",
            });
          } else if (result.error.includes("weak password")) {
            toast.error("Password too weak", {
              description:
                "Please choose a stronger password with at least 8 characters, including uppercase, lowercase, and numbers.",
            });
          } else {
            toast.error("Password reset failed", {
              description: result.error,
            });
          }
        } else {
          // Handle ErrorResponse object
          if (result.error.server) {
            toast.error("Password reset failed", {
              description: result.error.server[0],
            });
          } else if (result.error.password) {
            form.setError("password", {
              type: "server",
              message: result.error.password[0],
            });
          } else {
            toast.error("Password reset failed", {
              description: "An unexpected error occurred.",
            });
          }
        }
      } else if (result?.success) {
        setResetSuccess(true);
        toast.success("Password updated!", {
          description: "Your password has been successfully changed.",
        });
        form.reset();

        // Redirect to login after a delay
        setTimeout(() => {
          router.push("/login");
        }, 3000);
      }
    } catch (err) {
      console.error("Password reset error:", err);
      toast.error("An unexpected error occurred", {
        description: "Please try again later.",
      });
    } finally {
      setLoading(false);
    }
  };

  // Show invalid token error
  if (tokenValid === false) {
    return (
      <div className="min-h-screen flex items-center justify-center p-4 bg-gradient-to-br from-background via-background to-muted/20">
        <div className="w-full max-w-md">
          <Card className="border-border/50 shadow-lg">
            <CardHeader className="text-center space-y-4">
              <div className="mx-auto w-16 h-16 bg-red-100 dark:bg-red-900/20 rounded-full flex items-center justify-center">
                <XCircle className="w-8 h-8 text-red-600 dark:text-red-400" />
              </div>
              <div>
                <CardTitle className="text-2xl">Invalid reset link</CardTitle>
                <CardDescription className="mt-2">
                  This password reset link is invalid or has expired
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
                  {errorMessage ||
                    "The password reset link is invalid or has expired."}
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
            </CardContent>
          </Card>
        </div>
      </div>
    );
  }

  // Show success state
  if (resetSuccess) {
    return (
      <div className="min-h-screen flex items-center justify-center p-4 bg-gradient-to-br from-background via-background to-muted/20">
        <div className="w-full max-w-md">
          <Card className="border-border/50 shadow-lg">
            <CardHeader className="text-center space-y-4">
              <div className="mx-auto w-16 h-16 bg-green-100 dark:bg-green-900/20 rounded-full flex items-center justify-center">
                <CheckCircle className="w-8 h-8 text-green-600 dark:text-green-400" />
              </div>
              <div>
                <CardTitle className="text-2xl">Password updated</CardTitle>
                <CardDescription className="mt-2">
                  Your password has been successfully changed
                </CardDescription>
              </div>
            </CardHeader>
            <CardContent className="space-y-4 text-center">
              <div className="p-4 bg-muted/50 rounded-lg space-y-2">
                <p className="text-sm font-medium">Security measure applied</p>
                <p className="text-xs text-muted-foreground">
                  For your security, you&apos;ve been signed out. You will be
                  redirected to sign in with your new password.
                </p>
              </div>

              <Button asChild className="w-full">
                <Link href="/login">Sign in with new password</Link>
              </Button>
            </CardContent>
          </Card>
        </div>
      </div>
    );
  }

  // Show loading state while validating token
  if (tokenValid === null) {
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
                  Validating reset link
                </CardTitle>
                <CardDescription className="mt-2">
                  Please wait while we verify your reset token
                </CardDescription>
              </div>
            </CardHeader>
          </Card>
        </div>
      </div>
    );
  }

  // Show password reset form
  return (
    <div className="min-h-screen flex items-center justify-center p-4 bg-gradient-to-br from-background via-background to-muted/20">
      <div className="w-full max-w-md">
        <div className="text-center mb-8">
          <h1 className="text-3xl font-bold tracking-tight">
            Set new password
          </h1>
          <p className="text-muted-foreground mt-2">
            Enter your new password below
          </p>
        </div>

        <Card className="border-border/50 shadow-lg">
          <CardHeader className="space-y-1 text-center">
            <CardTitle className="text-2xl">Reset your password</CardTitle>
            <CardDescription>
              Choose a strong password to secure your account
            </CardDescription>
          </CardHeader>
          <CardContent className="space-y-6">
            <form
              onSubmit={form.handleSubmit(handlePasswordReset)}
              className="space-y-4"
            >
              <div className="space-y-2">
                <Label htmlFor="password">New password</Label>
                <div className="relative">
                  <Input
                    id="password"
                    type={showPassword ? "text" : "password"}
                    placeholder="Enter your new password"
                    {...form.register("password")}
                    className={
                      form.formState.errors.password
                        ? "border-destructive pr-10"
                        : "pr-10"
                    }
                  />
                  <button
                    type="button"
                    onClick={() => setShowPassword(!showPassword)}
                    className="absolute right-3 top-1/2 -translate-y-1/2 text-muted-foreground hover:text-foreground"
                  >
                    {showPassword ? (
                      <EyeOff className="w-4 h-4" />
                    ) : (
                      <Eye className="w-4 h-4" />
                    )}
                  </button>
                </div>
                {form.formState.errors.password && (
                  <p className="text-sm text-destructive flex items-center gap-1">
                    <AlertCircle className="w-4 h-4" />
                    {form.formState.errors.password.message}
                  </p>
                )}
                <p className="text-xs text-muted-foreground">
                  Must be at least 8 characters with uppercase, lowercase, and
                  numbers
                </p>
              </div>

              <div className="space-y-2">
                <Label htmlFor="confirmPassword">Confirm new password</Label>
                <div className="relative">
                  <Input
                    id="confirmPassword"
                    type={showConfirmPassword ? "text" : "password"}
                    placeholder="Confirm your new password"
                    {...form.register("confirmPassword")}
                    className={
                      form.formState.errors.confirmPassword
                        ? "border-destructive pr-10"
                        : "pr-10"
                    }
                  />
                  <button
                    type="button"
                    onClick={() => setShowConfirmPassword(!showConfirmPassword)}
                    className="absolute right-3 top-1/2 -translate-y-1/2 text-muted-foreground hover:text-foreground"
                  >
                    {showConfirmPassword ? (
                      <EyeOff className="w-4 h-4" />
                    ) : (
                      <Eye className="w-4 h-4" />
                    )}
                  </button>
                </div>
                {form.formState.errors.confirmPassword && (
                  <p className="text-sm text-destructive flex items-center gap-1">
                    <AlertCircle className="w-4 h-4" />
                    {form.formState.errors.confirmPassword.message}
                  </p>
                )}
              </div>

              <Button
                type="submit"
                className="w-full h-11 font-medium"
                disabled={loading}
              >
                {loading ? (
                  <>
                    <Loader2 className="w-5 h-5 animate-spin mr-2" />
                    Updating password...
                  </>
                ) : (
                  <>
                    <Lock className="w-5 h-5 mr-2" />
                    Set new password
                  </>
                )}
              </Button>
            </form>

            <div className="text-center text-sm text-muted-foreground">
              Remember your password?{" "}
              <Link
                href="/login"
                className="font-medium text-primary hover:underline"
              >
                Sign in
              </Link>
            </div>
          </CardContent>
        </Card>

        <div className="mt-8 text-center text-xs text-muted-foreground">
          For security, you&apos;ll be signed out after changing your password.
        </div>
      </div>
    </div>
  );
}

export default function ResetPasswordTokenPage() {
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
      <PasswordResetTokenContent />
    </Suspense>
  );
}
