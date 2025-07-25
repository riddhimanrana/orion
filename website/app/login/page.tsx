"use client";

import { useState, useEffect, Suspense } from "react";
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
import { Loader2, AlertCircle, Eye, EyeOff, LogIn } from "lucide-react";
import Link from "next/link";
import { toast } from "sonner";
import { signInSchema, type SignInFormData } from "@/lib/auth-schemas";
import { signInWithGoogle, signInWithGitHub, signInWithEmail } from "./actions";
import { resendEmailVerification } from "../signup/actions";
import { useUser } from "@/hooks/use-user";

function LoginPageContent() {
  const [loading, setLoading] = useState<string | null>(null);
  const [showPassword, setShowPassword] = useState(false);
  const searchParams = useSearchParams();
  const routerRedirectTo = searchParams.get("redirectTo");
  const { user, session } = useUser();

  const form = useForm<SignInFormData>({
    resolver: zodResolver(signInSchema),
    defaultValues: {
      email: "",
      password: "",
    },
  });

  // Redirect if user is already logged in
  useEffect(() => {
    if (user && session) {
      if (routerRedirectTo) {
        // If mobile redirect is present, go to the bridge to transfer session
        const bridgeUrl = new URL(routerRedirectTo);
        bridgeUrl.searchParams.set("redirectTo", routerRedirectTo);
        window.location.href = bridgeUrl.toString();
      } else {
        // Otherwise, go to the dashboard for web flow
        window.location.href = "/dashboard";
      }
    }
  }, [user, session, routerRedirectTo]);
  type OauthResult = {
    error?: string;
    url?: string;
  };

  const handleOauthLogin = async (
    provider: "google" | "github",
    action: (redirectTo?: string) => Promise<OauthResult>,
  ) => {
    setLoading(provider);
    try {
      const result = await action(routerRedirectTo || undefined);
      if (result?.error) {
        toast.error(`Sign in with ${provider} failed`, {
          description: result.error,
        });
      } else if (result?.url) {
        window.location.href = result.url;
      }
    } catch {
      toast.error("An unexpected error occurred.");
    } finally {
      setLoading(null);
    }
  };

  const handleEmailLogin = async (data: SignInFormData) => {
    setLoading("email");
    try {
      const result = await signInWithEmail(data, routerRedirectTo || undefined);

      if ("error" in result) {
        if (result.error.includes("Email not confirmed")) {
          toast.error("Email not confirmed", {
            description: "Please check your email for a confirmation link.",
            action: {
              label: "Resend Email",
              onClick: () => handleResendVerification(data.email),
            },
          });
        } else {
          toast.error("Sign in failed", {
            description: result.error,
          });
        }
      } else if (result.success && result.redirectTo) {
        window.location.href = result.redirectTo;
      }
    } catch {
      toast.error("An unexpected error occurred.");
    } finally {
      setLoading(null);
    }
  };

  const handleResendVerification = async (email: string) => {
    // Basic implementation, you can add cooldown logic if needed
    setLoading("resend");
    try {
      const result = await resendEmailVerification(email);
      if (result.success) {
        toast.success("Verification email sent!", {
          description: result.message,
        });
      } else {
        toast.error("Failed to resend verification", {
          description: result.error,
        });
      }
    } catch {
      toast.error("An unexpected error occurred.");
    } finally {
      setLoading(null);
    }
  };

  return (
    <div className="min-h-screen flex items-center justify-center p-4 bg-gradient-to-br from-background via-background to-muted/20">
      <div className="w-full max-w-md">
        <div className="text-center mb-8">
          <h1 className="text-3xl font-bold tracking-tight">Welcome back</h1>
          <p className="text-muted-foreground mt-2">
            Sign in to your Orion account
          </p>
        </div>

        <Card className="border-border/50 shadow-lg">
          <CardHeader className="space-y-1 text-center">
            <CardTitle className="text-2xl">Sign in</CardTitle>
            <CardDescription>
              Choose your preferred sign-in method
            </CardDescription>
          </CardHeader>
          <CardContent className="space-y-6">
            {/* OAuth Providers */}
            <div className="space-y-3">
              <Button
                variant="outline"
                className="w-full h-11 font-medium"
                onClick={() => handleOauthLogin("github", signInWithGitHub)}
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
                onClick={() => handleOauthLogin("google", signInWithGoogle)}
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
              onSubmit={form.handleSubmit(handleEmailLogin)}
              className="space-y-4"
            >
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
                    <AlertCircle className="w-4 h-4" />
                    {form.formState.errors.email.message}
                  </p>
                )}
              </div>

              <div className="space-y-2">
                <div className="flex items-center justify-between">
                  <Label htmlFor="password">Password</Label>
                  <Link
                    href="/reset-password"
                    className="text-sm text-primary hover:underline"
                  >
                    Forgot password?
                  </Link>
                </div>
                <div className="relative">
                  <Input
                    id="password"
                    type={showPassword ? "text" : "password"}
                    placeholder="Enter your password"
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
              </div>

              <Button
                type="submit"
                className="w-full h-11 font-medium"
                disabled={loading !== null}
              >
                {loading === "email" ? (
                  <>
                    <Loader2 className="w-5 h-5 animate-spin mr-2" />
                    Signing in...
                  </>
                ) : (
                  <>
                    <LogIn className="w-5 h-5 mr-2" />
                    Sign in
                  </>
                )}
              </Button>
            </form>

            <div className="text-center text-sm text-muted-foreground">
              Don&apos;t have an account?{" "}
              <Link
                href="/signup"
                className="font-medium text-primary hover:underline"
              >
                Sign up
              </Link>
            </div>
          </CardContent>
        </Card>

        <div className="mt-8 text-center text-xs text-muted-foreground">
          By continuing, you agree to our{" "}
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

export default function LoginPage() {
  return (
    <Suspense fallback={<div>Loading...</div>}>
      <LoginPageContent />
    </Suspense>
  );
}
