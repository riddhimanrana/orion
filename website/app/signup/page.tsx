"use client";

import { useState, Suspense } from "react";
import { useSearchParams } from "next/navigation";
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
import { Separator } from "@/components/ui/separator";
import { SiGithub } from "react-icons/si";
import {
  Loader2,
  AlertCircle,
  Eye,
  EyeOff,
  Mail,
  CheckCircle,
  ArrowLeft,
  User,
} from "lucide-react";
import Link from "next/link";
import { toast } from "sonner";
import { signUpSchema, type SignUpFormData } from "@/lib/auth-schemas";
import {
  signUpWithGoogle,
  signUpWithGitHub,
  signUpWithEmail,
  resendEmailVerification,
} from "./actions";
import { checkUserEmailStatus } from "@/utils/supabase/checkUserEmailStatus";

function SignUpPageContent() {
  const [loading, setLoading] = useState<string | null>(null);
  const [showPassword, setShowPassword] = useState(false);
  const [showConfirmPassword, setShowConfirmPassword] = useState(false);
  const [emailSent, setEmailSent] = useState(false);
  const [sentEmail, setSentEmail] = useState("");
  const [resendLoading, setResendLoading] = useState(false);
  const [resendCooldown, setResendCooldown] = useState(0);
  const searchParams = useSearchParams();
  const redirectTo = searchParams.get("redirectTo");

  const form = useForm<SignUpFormData>({
    resolver: zodResolver(signUpSchema),
    defaultValues: {
      fullName: "",
      email: "",
      password: "",
      confirmPassword: "",
    },
  });

  const handleGitHubSignUp = async () => {
    setLoading("github");
    try {
      const result = await signUpWithGitHub(redirectTo || undefined);
      if (result && "error" in result) {
        toast.error("GitHub sign up failed", {
          description: result.error,
        });
      } else if (result && "success" in result && result.url) {
        // Redirect to OAuth provider
        window.location.href = result.url;
        return;
      }
    } catch {
      toast.error("An unexpected error occurred", {
        description: "Please try again later.",
      });
    } finally {
      setLoading(null);
    }
  };

  const handleGoogleSignUp = async () => {
    setLoading("google");
    try {
      const result = await signUpWithGoogle(redirectTo || undefined);
      if (result && "error" in result) {
        toast.error("Google sign up failed", {
          description: result.error,
        });
      } else if (result && "success" in result && result.url) {
        // Redirect to OAuth provider
        window.location.href = result.url;
        return;
      }
    } catch {
      toast.error("An unexpected error occurred", {
        description: "Please try again later.",
      });
    } finally {
      setLoading(null);
    }
  };

  const handleEmailSignUp = async (data: SignUpFormData) => {
    setLoading("email");
    try {
      // Step 1: Check account status using the Supabase RPC
      try {
        const { user_exists, email_confirmed } = await checkUserEmailStatus(data.email);
        if (user_exists) {
          if (email_confirmed) {
            toast.error("Email already registered", {
              description:
                "This email is already registered and confirmed.",
              action: {
                label: "Sign In",
                onClick: () => (window.location.href = "/login"),
              },
            });
          } else {
            toast.warning("Email not confirmed", {
              description:
                "This email is already registered but not confirmed.",
              action: {
                label: "Resend Verification",
                onClick: () => handleResendVerification(data.email),
              },
            });
          }
          setLoading(null);
          return;
        }
      } catch (err: unknown) {
        let message = "Failed to check account status.";
        if (
          err &&
          typeof err === "object" &&
          "message" in err &&
          typeof (err as Record<string, unknown>)["message"] === "string"
        ) {
          message = (err as { message: string }).message;
        }
        toast.error("Error checking account", {
          description: message,
        });
        setLoading(null);
        return;
      }

      // Step 2: If not exists, proceed with signup
      const result = await signUpWithEmail(data, redirectTo || undefined);

      if (result && "error" in result) {
        if (result.error.includes("invalid email")) {
          toast.error("Invalid email address", {
            description: "Please enter a valid email address.",
          });
        } else if (result.error.includes("weak password")) {
          toast.error("Password too weak", {
            description:
              "Please choose a stronger password with at least 8 characters, including uppercase, lowercase, and numbers.",
          });
        } else {
          toast.error("Sign up failed", {
            description: result.error,
          });
        }
      } else if (result && "success" in result) {
        setSentEmail(data.email);
        setEmailSent(true);
        toast.success("Account created successfully!", {
          description: "Please check your email to confirm your account.",
        });
        form.reset();
      }
    } catch {
      toast.error("An unexpected error occurred", {
        description: "Please try again later.",
      });
    } finally {
      setLoading(null);
    }
  };

  const handleResendVerification = async (email: string) => {
    if (resendCooldown > 0) {
      toast.error("Please wait", {
        description: `You can request another email in ${resendCooldown} seconds.`,
      });
      return;
    }

    setResendLoading(true);
    try {
      const result = await resendEmailVerification(email);

      if (result.success) {
        toast.success("Verification email sent!", {
          description: result.message,
        });

        // Start cooldown
        setResendCooldown(60);
        const interval = setInterval(() => {
          setResendCooldown((prev) => {
            if (prev <= 1) {
              clearInterval(interval);
              return 0;
            }
            return prev - 1;
          });
        }, 1000);
      } else {
        toast.error("Failed to resend verification", {
          description: result.error,
        });
      }
    } catch {
      toast.error("An unexpected error occurred", {
        description: "Please try again later.",
      });
    } finally {
      setResendLoading(false);
    }
  };

  // Show email confirmation screen
  if (emailSent) {
    return (
      <div className="min-h-screen flex items-center justify-center p-4 bg-white dark:bg-black">
        <div className="w-full max-w-md">
          <Card className="border-border/50 shadow-lg">
            <CardHeader className="text-center space-y-4">
              <div className="mx-auto w-16 h-16 bg-green-100 dark:bg-green-900/20 rounded-full flex items-center justify-center">
                <Mail className="w-8 h-8 text-green-600 dark:text-green-400" />
              </div>
              <div>
                <CardTitle className="text-2xl">Check your email</CardTitle>
                <CardDescription className="mt-2">
                  We&apos;ve sent a confirmation link to{" "}
                  <span className="font-medium text-foreground">
                    {sentEmail}
                  </span>
                </CardDescription>
              </div>
            </CardHeader>
            <CardContent className="space-y-4 text-center">
              <div className="p-4 bg-muted/50 rounded-lg space-y-2">
                <CheckCircle className="w-5 h-5 text-green-600 dark:text-green-400 mx-auto" />
                <p className="text-sm font-medium">
                  Account created successfully
                </p>
                <p className="text-xs text-muted-foreground">
                  Click the confirmation link in your email to activate your
                  account
                </p>
              </div>

              <div className="space-y-3">
                <p className="text-sm text-muted-foreground">
                  Didn&apos;t receive the email? Check your spam folder.
                </p>

                <Button
                  variant="outline"
                  onClick={() => handleResendVerification(sentEmail)}
                  disabled={resendLoading || resendCooldown > 0}
                  className="w-full"
                >
                  {resendLoading ? (
                    <>
                      <Loader2 className="w-4 h-4 mr-2 animate-spin" />
                      Sending...
                    </>
                  ) : resendCooldown > 0 ? (
                    `Resend in ${resendCooldown}s`
                  ) : (
                    <>
                      <Mail className="w-4 h-4 mr-2" />
                      Resend verification email
                    </>
                  )}
                </Button>

                <Button
                  variant="ghost"
                  onClick={() => {
                    setEmailSent(false);
                    setSentEmail("");
                    setResendCooldown(0);
                  }}
                  className="w-full"
                >
                  <ArrowLeft className="w-4 h-4 mr-2" />
                  Back to sign up
                </Button>
              </div>
            </CardContent>
          </Card>
        </div>
      </div>
    );
  }

  return (
    <div className="min-h-screen flex items-center justify-center p-4 bg-gradient-to-br from-background via-background to-muted/20">
      <div className="w-full max-w-md">
        <div className="text-center mb-8">
          <h1 className="text-3xl font-bold tracking-tight">Get started</h1>
          <p className="text-muted-foreground mt-2">
            Create your Orion account to begin
          </p>
        </div>

        <Card className="border-border/50 shadow-lg">
          <CardHeader className="space-y-1 text-center">
            <CardTitle className="text-2xl">Create account</CardTitle>
            <CardDescription>
              Choose your preferred sign-up method
            </CardDescription>
          </CardHeader>
          <CardContent className="space-y-6">
            {/* OAuth Providers */}
            <div className="space-y-3">
              <Button
                variant="outline"
                className="w-full h-11 font-medium"
                onClick={handleGitHubSignUp}
                disabled={loading !== null}
              >
                {loading === "github" ? (
                  <Loader2 className="w-5 h-5 animate-spin" />
                ) : (
                  <SiGithub className="w-5 h-5" />
                )}
                Continue with GitHub
              </Button>

              <Button
                variant="outline"
                className="w-full h-11 font-medium"
                onClick={handleGoogleSignUp}
                disabled={loading !== null}
              >
                {loading === "google" ? (
                  <Loader2 className="w-5 h-5 animate-spin" />
                ) : (
                  <svg className="w-5 h-5" viewBox="0 0 24 24">
                    <path
                      fill="currentColor"
                      d="M22.56 12.25c0-.78-.07-1.53-.2-2.25H12v4.26h5.92c-.26 1.37-1.04 2.53-2.21 3.31v2.77h3.57c2.08-1.92 3.28-4.74 3.28-8.09z"
                    />
                    <path
                      fill="currentColor"
                      d="M12 23c2.97 0 5.46-.98 7.28-2.66l-3.57-2.77c-.98.66-2.23 1.06-3.71 1.06-2.86 0-5.29-1.93-6.16-4.53H2.18v2.84C3.99 20.53 7.7 23 12 23z"
                    />
                    <path
                      fill="currentColor"
                      d="M5.84 14.09c-.22-.66-.35-1.36-.35-2.09s.13-1.43.35-2.09V7.07H2.18C1.43 8.55 1 10.22 1 12s.43 3.45 1.18 4.93l2.85-2.22.81-.62z"
                    />
                    <path
                      fill="currentColor"
                      d="M12 5.38c1.62 0 3.06.56 4.21 1.64l3.15-3.15C17.45 2.09 14.97 1 12 1 7.7 1 3.99 3.47 2.18 7.07l3.66 2.84c.87-2.6 3.3-4.53 6.16-4.53z"
                    />
                  </svg>
                )}
                Continue with Google
              </Button>
            </div>

            <div className="relative">
              <div className="absolute inset-0 flex items-center">
                <Separator />
              </div>
              <div className="relative flex justify-center text-xs uppercase">
                <span className="bg-white dark:bg-neutral-900 px-2 text-muted-foreground">
                  Or continue with email
                </span>
              </div>
            </div>

            {/* Email/Password Form */}
            <form
              onSubmit={form.handleSubmit(handleEmailSignUp)}
              className="space-y-4"
            >
              <div className="space-y-2">
                <Label htmlFor="fullName">Full name</Label>
                <Input
                  id="fullName"
                  type="text"
                  placeholder="Enter your full name"
                  {...form.register("fullName")}
                  className={
                    form.formState.errors.fullName ? "border-destructive" : ""
                  }
                />
                {form.formState.errors.fullName && (
                  <p className="text-sm text-destructive flex items-center gap-1">
                    <AlertCircle className="w-4 h-4 flex-shrink-0" />
                    {form.formState.errors.fullName.message}
                  </p>
                )}
              </div>

              <div className="space-y-2">
                <Label htmlFor="email">Email address</Label>
                <Input
                  id="email"
                  type="email"
                  placeholder="Enter your email"
                  {...form.register("email")}
                  className={
                    form.formState.errors.email ? "border-destructive" : ""
                  }
                />
                {form.formState.errors.email && (
                  <p className="text-sm text-destructive flex items-center gap-1">
                    <AlertCircle className="w-4 h-4 flex-shrink-0" />
                    {form.formState.errors.email.message}
                  </p>
                )}
              </div>

              <div className="space-y-2">
                <Label htmlFor="password">Password</Label>
                <div className="relative">
                  <Input
                    id="password"
                    type={showPassword ? "text" : "password"}
                    placeholder="Create a password"
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
                    <AlertCircle className="w-4 h-4 flex-shrink-0" />
                    {form.formState.errors.password.message}
                  </p>
                )}
                <p className="text-xs text-muted-foreground">
                  Must be at least 8 characters with uppercase, lowercase, and
                  numbers
                </p>
              </div>

              <div className="space-y-2">
                <Label htmlFor="confirmPassword">Confirm password</Label>
                <div className="relative">
                  <Input
                    id="confirmPassword"
                    type={showConfirmPassword ? "text" : "password"}
                    placeholder="Confirm your password"
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
                    <AlertCircle className="w-4 h-4 flex-shrink-0" />
                    {form.formState.errors.confirmPassword.message}
                  </p>
                )}
              </div>

              <Button
                type="submit"
                className="w-full h-11 font-medium"
                disabled={loading !== null}
              >
                {loading === "email" ? (
                  <>
                    <Loader2 className="w-5 h-5 animate-spin mr-2" />
                    Creating account...
                  </>
                ) : (
                  <>
                    <User className="w-5 h-5 mr-2" />
                    Create account
                  </>
                )}
              </Button>
            </form>

            <div className="text-center text-sm text-muted-foreground">
              Already have an account?{" "}
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
          By creating an account, you agree to our{" "}
          <Link href="/terms" className="hover:underline">
            Terms of Service
          </Link>{" "}
          and{" "}
          <Link href="/privacy" className="hover:underline">
            Privacy Policy
          </Link>
        </div>
      </div>
    </div>
  );
}

export default function SignUpPage() {
  return (
    <Suspense fallback={<div>Loading...</div>}>
      <SignUpPageContent />
    </Suspense>
  );
}
