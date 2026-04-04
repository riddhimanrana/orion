"use client";

import { useState, useEffect, Suspense } from "react";
import { useParams, useSearchParams } from "next/navigation";
import { useForm } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import {
  Loader2,
  Eye,
  EyeOff,
  CheckCircle,
  XCircle,
  Lock,
  ArrowLeft,
} from "lucide-react";
import Link from "next/link";
import Image from "next/image";
import { toast } from "sonner";
import { useRouter } from "next/navigation";
import {
  passwordResetConfirmSchema,
  type PasswordResetConfirmFormData,
} from "@/lib/auth-schemas";
import { confirmPasswordReset } from "../actions";
import { ShootingStars } from "@/components/ui/shooting-stars";
import { StarsBackground } from "@/components/ui/stars-background";

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
                "Please choose a stronger password with at least 8 characters.",
            });
          } else if (result.error.includes("Password should be")) {
            toast.error("Password requirements not met", {
              description: result.error,
            });
          } else {
            toast.error("Password reset failed", {
              description: result.error,
            });
          }
        } else {
          // Handle ErrorResponse object
          const errorResponse = result.error;
          if (errorResponse.server && errorResponse.server.length > 0) {
            toast.error("Password reset failed", {
              description: errorResponse.server[0],
            });
          } else if (errorResponse.password && errorResponse.password.length > 0) {
            toast.error("Password error", {
              description: errorResponse.password[0],
            });
          } else {
            toast.error("An unexpected error occurred", {
              description: "Please try again later.",
            });
          }
        }
      } else if (result?.success) {
        setResetSuccess(true);
        toast.success("Password reset successful!", {
          description: "You can now sign in with your new password.",
        });
        form.reset();

        // Redirect to login after a delay
        setTimeout(() => {
          router.push("/login");
        }, 3000);
      }
    } catch {
      toast.error("An unexpected error occurred", {
        description: "Please try again later.",
      });
    } finally {
      setLoading(false);
    }
  };

  // Show success screen
  if (resetSuccess) {
    return (
      <div className="min-h-screen bg-background text-foreground flex flex-col relative overflow-hidden dark:bg-neutral-950 dark:text-white">
        {/* Star Background Effects */}
        <ShootingStars />
        <StarsBackground />

        <div className="relative z-10 flex items-center justify-center min-h-screen p-6">
          <div className="w-full max-w-md text-center">
            <div className="mb-8">
              <div className="w-16 h-16 mx-auto bg-green-500 rounded-full flex items-center justify-center mb-4">
                <CheckCircle className="w-8 h-8 text-white" />
              </div>
              <h1 className="text-2xl font-bold mb-2 text-foreground dark:text-white">Password reset successful!</h1>
              <p className="text-muted-foreground dark:text-neutral-400">
                Your password has been updated. You can now sign in with your new password.
              </p>
            </div>

            <div className="space-y-4">
              <div className="p-4 bg-green-50 dark:bg-green-900/20 border border-green-200 dark:border-green-800 rounded-lg">
                <CheckCircle className="w-5 h-5 text-green-600 dark:text-green-400 mx-auto mb-2" />
                <p className="text-sm font-medium text-green-800 dark:text-green-200">
                  Password updated successfully
                </p>
                <p className="text-xs text-green-600 dark:text-green-400 mt-1">
                  Redirecting to sign in page...
                </p>
              </div>

              <Link href="/login">
                <Button className="w-full">
                  Continue to Sign In
                </Button>
              </Link>
            </div>
          </div>
        </div>
      </div>
    );
  }

  // Show error screen for invalid tokens
  if (tokenValid === false) {
    return (
      <div className="min-h-screen bg-background text-foreground flex flex-col relative overflow-hidden dark:bg-neutral-950 dark:text-white">
        {/* Star Background Effects */}
        <ShootingStars />
        <StarsBackground />

        <div className="absolute top-6 left-6 z-10">
          <Link href="/" className="flex items-center gap-2 text-muted-foreground hover:text-foreground dark:text-neutral-400 dark:hover:text-white transition-colors">
            <ArrowLeft className="w-4 h-4" />
            Home
          </Link>
        </div>

        <div className="relative z-10 flex items-center justify-center min-h-screen p-6">
          <div className="w-full max-w-md text-center">
            <div className="mb-8">
              <div className="w-16 h-16 mx-auto bg-red-500 rounded-full flex items-center justify-center mb-4">
                <XCircle className="w-8 h-8 text-white" />
              </div>
              <h1 className="text-2xl font-bold mb-2">Invalid Reset Link</h1>
              <p className="text-muted-foreground">
                {errorMessage || "This password reset link is invalid or has expired."}
              </p>
            </div>

            <div className="space-y-4">
              <div className="p-4 bg-red-50 dark:bg-red-900/20 border border-red-200 dark:border-red-800 rounded-lg">
                <XCircle className="w-5 h-5 text-red-600 dark:text-red-400 mx-auto mb-2" />
                <p className="text-sm font-medium text-red-800 dark:text-red-200">
                  Reset link expired or invalid
                </p>
                <p className="text-xs text-red-600 dark:text-red-400 mt-1">
                  Please request a new password reset link.
                </p>
              </div>

              <div className="space-y-2">
                <Link href="/reset-password">
                  <Button className="w-full">
                    Request New Reset Link
                  </Button>
                </Link>

                <Link href="/login">
                  <Button variant="ghost" className="w-full">
                    Back to Sign In
                  </Button>
                </Link>
              </div>
            </div>
          </div>
        </div>
      </div>
    );
  }

  // Show loading state while validating token
  if (tokenValid === null) {
    return (
      <div className="min-h-screen bg-background text-foreground flex flex-col relative overflow-hidden dark:bg-neutral-950 dark:text-white">
        <div className="relative z-10 flex items-center justify-center min-h-screen p-6">
          <div className="w-full max-w-md text-center">
            <Loader2 className="w-8 h-8 animate-spin mx-auto mb-4" />
            <p className="text-muted-foreground dark:text-neutral-400">Validating reset link...</p>
          </div>
        </div>
      </div>
    );
  }

  // Show password reset form for valid tokens
  return (
    <div className="min-h-screen bg-background text-foreground flex flex-col relative overflow-hidden dark:bg-neutral-950 dark:text-white">
      {/* Star Background Effects */}
      <ShootingStars />
      <StarsBackground />

      {/* Go Home Button */}
      <div className="absolute top-6 left-6 z-10">
        <Link href="/" className="flex items-center gap-2 text-muted-foreground hover:text-foreground dark:text-neutral-400 dark:hover:text-white transition-colors">
          <svg
            className="w-4 h-4"
            fill="none"
            stroke="currentColor"
            viewBox="0 0 24 24"
          >
            <path
              strokeLinecap="round"
              strokeLinejoin="round"
              strokeWidth={2}
              d="M15 19l-7-7 7-7"
            />
          </svg>
          Home
        </Link>
      </div>

      {/* Main Content */}
      <div className="relative z-10 flex items-center justify-center min-h-screen p-6">
        <div className="w-full max-w-md">
          {/* Logo and Title */}
          <div className="text-center mb-8">
            <div className="mb-6">
              <Image 
                src="/orion.svg" 
                alt="Orion" 
                width={48}
                height={48}
                className="mx-auto"
              />
            </div>
            <h1 className="text-3xl font-bold mb-2">Set new password</h1>
            <p className="text-muted-foreground">
              Enter your new password below
            </p>
          </div>

          {/* Password Reset Form */}
          <div className="space-y-6">
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
                    placeholder="••••••••"
                    {...form.register("password")}
                    className={form.formState.errors.password ? "border-destructive" : ""}
                  />
                  <button
                    type="button"
                    onClick={() => setShowPassword(!showPassword)}
                    className="absolute inset-y-0 right-0 pr-3 flex items-center text-muted-foreground hover:text-foreground"
                  >
                    {showPassword ? (
                      <EyeOff className="h-4 w-4" />
                    ) : (
                      <Eye className="h-4 w-4" />
                    )}
                  </button>
                </div>
                {form.formState.errors.password && (
                  <p className="text-destructive text-sm">
                    {form.formState.errors.password.message}
                  </p>
                )}
              </div>

              <div className="space-y-2">
                <Label htmlFor="confirmPassword">Confirm new password</Label>
                <div className="relative">
                  <Input
                    id="confirmPassword"
                    type={showConfirmPassword ? "text" : "password"}
                    placeholder="••••••••"
                    {...form.register("confirmPassword")}
                    className={form.formState.errors.confirmPassword ? "border-destructive" : ""}
                  />
                  <button
                    type="button"
                    onClick={() => setShowConfirmPassword(!showConfirmPassword)}
                    className="absolute inset-y-0 right-0 pr-3 flex items-center text-muted-foreground hover:text-foreground"
                  >
                    {showConfirmPassword ? (
                      <EyeOff className="h-4 w-4" />
                    ) : (
                      <Eye className="h-4 w-4" />
                    )}
                  </button>
                </div>
                {form.formState.errors.confirmPassword && (
                  <p className="text-destructive text-sm">
                    {form.formState.errors.confirmPassword.message}
                  </p>
                )}
              </div>

              <Button
                type="submit"
                className="w-full h-11"
                disabled={loading}
              >
                {loading ? (
                  <Loader2 className="w-5 h-5 animate-spin" />
                ) : (
                  <Lock className="w-5 h-5 mr-2" />
                )}
                {loading ? "Updating Password..." : "Update Password"}
              </Button>
            </form>

            <div className="text-center text-sm text-muted-foreground">
              <Link
                href="/login"
                className="font-medium text-primary hover:underline"
              >
                Back to sign in
              </Link>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}

export default function PasswordResetTokenPage() {
  return (
    <Suspense fallback={<div>Loading...</div>}>
      <PasswordResetTokenContent />
    </Suspense>
  );
}
