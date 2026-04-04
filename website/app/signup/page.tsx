"use client";

import { useState, Suspense } from "react";
import { useSearchParams } from "next/navigation";
import { useForm } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { SiGithub } from "react-icons/si";
import { Loader2, Eye, EyeOff, Mail, ArrowLeft } from "lucide-react";
import Link from "next/link";
import Image from "next/image";
import { toast } from "sonner";
import { signUpSchema, type SignUpFormData } from "@/lib/auth-schemas";
import {
  signUpWithGoogle,
  signUpWithGitHub,
  signUpWithEmail,
  resendEmailVerification,
} from "./actions";
import { checkUserEmailStatus } from "@/utils/supabase/checkUserEmailStatus";
import { ShootingStars } from "@/components/ui/shooting-stars";
import { StarsBackground } from "@/components/ui/stars-background";

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
      // Check account status
      try {
        const { user_exists, email_confirmed } = await checkUserEmailStatus(data.email);
        if (user_exists) {
          if (email_confirmed) {
            toast.error("Email already registered", {
              description: "This email is already registered and confirmed.",
              action: {
                label: "Sign In",
                onClick: () => (window.location.href = "/login"),
              },
            });
          } else {
            toast.warning("Email not confirmed", {
              description: "This email is already registered but not confirmed.",
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

      const result = await signUpWithEmail(data, redirectTo || undefined);

      if (result && "error" in result) {
        if (result.error.includes("invalid email")) {
          toast.error("Invalid email address", {
            description: "Please enter a valid email address.",
          });
        } else if (result.error.includes("weak password")) {
          toast.error("Password too weak", {
            description: "Please choose a stronger password with at least 8 characters.",
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
      <div className="min-h-screen bg-background text-foreground flex flex-col relative overflow-hidden dark:bg-neutral-950 dark:text-white">
        {/* Star Background Effects */}
        <ShootingStars />
        <StarsBackground />

        <div className="absolute top-6 left-6 z-10">
          <button
            onClick={() => setEmailSent(false)}
            className="flex items-center gap-2 text-muted-foreground hover:text-foreground dark:text-neutral-400 dark:hover:text-white transition-colors"
          >
            <ArrowLeft className="w-4 h-4" />
            Back
          </button>
        </div>

        <div className="relative z-10 flex items-center justify-center min-h-screen p-6">
          <div className="w-full max-w-md text-center">
            <div className="mb-8">
              <div className="w-16 h-16 mx-auto bg-green-500 rounded-full flex items-center justify-center mb-4">
                <Mail className="w-8 h-8 text-white" />
              </div>
              <h1 className="text-2xl font-bold mb-2 text-foreground dark:text-white">Check your email</h1>
              <p className="text-muted-foreground dark:text-neutral-400">
                We&apos;ve sent a verification link to{" "}
                <span className="text-foreground dark:text-white font-medium">{sentEmail}</span>
              </p>
            </div>

            <div className="space-y-4">
              <Button
                onClick={() => handleResendVerification(sentEmail)}
                disabled={resendLoading || resendCooldown > 0}
                variant="outline"
                className="w-full"
              >
                {resendLoading ? (
                  <Loader2 className="w-4 h-4 animate-spin mr-2" />
                ) : (
                  <Mail className="w-4 h-4 mr-2" />
                )}
                {resendCooldown > 0
                  ? `Resend in ${resendCooldown}s`
                  : "Resend verification email"}
              </Button>

              <Link href="/login">
                <Button variant="ghost" className="w-full">
                  Back to sign in
                </Button>
              </Link>
            </div>
          </div>
        </div>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-background text-foreground flex flex-col relative overflow-hidden dark:bg-neutral-950 dark:text-white">
      {/* Star Background Effects */}
      <ShootingStars />
      <StarsBackground />

      {/* Go Home Button */}
      <div className="absolute top-6 left-6 z-30">
        <Link href="/" className="flex items-center gap-2 text-muted-foreground hover:text-foreground dark:text-neutral-400 dark:hover:text-white transition-colors pointer-events-auto">
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
            <h1 className="text-3xl font-semibold mb-2 text-foreground dark:text-white">Create an Orion account</h1>
            <p className="text-muted-foreground dark:text-neutral-400">
              Already have an account?{" "}
              <Link href="/login" className="font-medium text-primary hover:text-primary/80 dark:text-white dark:hover:text-white/60 ease-in-out duration-200">
                Log in
              </Link>
            </p>
          </div>

          {/* Auth Form */}
          <div className="space-y-6">
            {/* OAuth Providers */}
            <div className="space-y-3">
              <Button
                variant="outline"
                className="w-full h-11 bg-background/50 border-border text-foreground hover:bg-muted dark:bg-neutral-800/50 dark:border-neutral-700 dark:text-white dark:hover:bg-neutral-700/50"
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

              <Button
                variant="outline"
                className="w-full h-11 bg-background/50 border-border text-foreground hover:bg-muted dark:bg-neutral-800/50 dark:border-neutral-700 dark:text-white dark:hover:bg-neutral-700/50"
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
            </div>

            <div className="relative">
              <div className="absolute inset-0 flex items-center">
                <div className="w-full border-t border-border dark:border-neutral-700"></div>
              </div>
              <div className="relative flex justify-center text-sm">
                <span className="bg-background dark:bg-neutral-950 px-4 text-muted-foreground dark:text-neutral-400">or</span>
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
                  className={` ${form.formState.errors.fullName ? "border-red-500" : ""}`}
                />
                {form.formState.errors.fullName && (
                  <p className="text-red-400 text-sm">
                    {form.formState.errors.fullName.message}
                  </p>
                )}
              </div>

              <div className="space-y-2">
                <Label htmlFor="email">Email</Label>
                <Input
                  id="email"
                  type="email"
                  placeholder="name@example.com"
                  {...form.register("email")}
                  className={`${form.formState.errors.email ? "border-red-500" : ""}`}
                />
                {form.formState.errors.email && (
                  <p className="text-red-400 text-sm">
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
                    placeholder="••••••••"
                    {...form.register("password")}
                    className={` ${form.formState.errors.password ? "border-red-500" : ""}`}
                  />
                  <button
                    type="button"
                    onClick={() => setShowPassword(!showPassword)}
                    className="absolute inset-y-0 right-0 pr-3 flex items-center text-neutral-400 hover:text-white"
                  >
                    {showPassword ? (
                      <EyeOff className="h-4 w-4" />
                    ) : (
                      <Eye className="h-4 w-4" />
                    )}
                  </button>
                </div>
                {form.formState.errors.password && (
                  <p className="text-red-400 text-sm">
                    {form.formState.errors.password.message}
                  </p>
                )}
              </div>

              <div className="space-y-2">
                <Label htmlFor="confirmPassword" className="">Confirm password</Label>
                <div className="relative">
                  <Input
                    id="confirmPassword"
                    type={showConfirmPassword ? "text" : "password"}
                    placeholder="••••••••"
                    {...form.register("confirmPassword")}
                    className={` ${form.formState.errors.confirmPassword ? "border-red-500" : ""}`}
                  />
                  <button
                    type="button"
                    onClick={() => setShowConfirmPassword(!showConfirmPassword)}
                    className="absolute inset-y-0 right-0 pr-3 flex items-center text-neutral-400 hover:text-white"
                  >
                    {showConfirmPassword ? (
                      <EyeOff className="h-4 w-4" />
                    ) : (
                      <Eye className="h-4 w-4" />
                    )}
                  </button>
                </div>
                {form.formState.errors.confirmPassword && (
                  <p className="text-red-400 text-sm">
                    {form.formState.errors.confirmPassword.message}
                  </p>
                )}
              </div>

              <Button
                type="submit"
                className="w-full h-11 "
                disabled={loading !== null}
              >
                {loading === "email" ? (
                  <Loader2 className="w-5 h-5 animate-spin" />
                ) : (
                  "Create account"
                )}
              </Button>
            </form>
          </div>

          {/* Terms */}
          <div className="mt-8 text-center text-xs text-muted-foreground dark:text-neutral-400">
            By creating an account, you agree to our{" "}
            <Link href="/terms" className="hover:text-primary dark:hover:text-blue-400">
              Terms of Service
            </Link>{" "}
            and{" "}
            <Link href="/privacy" className="hover:text-primary dark:hover:text-blue-400">
              Privacy Policy
            </Link>
          </div>
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
