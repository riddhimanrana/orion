"use client";

import { useState, Suspense } from "react";
import { useSearchParams } from "next/navigation";
import { useForm } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { SiGithub } from "react-icons/si";
import { Loader2, Eye, EyeOff } from "lucide-react";
import Link from "next/link";
import Image from "next/image";
import { toast } from "sonner";
import { signInSchema, type SignInFormData } from "@/lib/auth-schemas";
import { signInWithGoogle, signInWithGitHub, signInWithEmail } from "./actions";
import { ShootingStars } from "@/components/ui/shooting-stars";
import { StarsBackground } from "@/components/ui/stars-background";

function LoginPageContent() {
  const [loading, setLoading] = useState<string | null>(null);
  const [showPassword, setShowPassword] = useState(false);
  const searchParams = useSearchParams();
  const redirectTo = searchParams.get("redirectTo");

  const form = useForm<SignInFormData>({
    resolver: zodResolver(signInSchema),
    defaultValues: {
      email: "",
      password: "",
    },
  });

  const handleOauthLogin = async (
    provider: string,
    loginFunction: (redirectTo?: string) => Promise<{ success: true; url: string } | { error: string }>
  ) => {
    setLoading(provider);
    try {
      const result = await loginFunction(redirectTo || undefined);
      if (result && "error" in result) {
        toast.error(`${provider} login failed`, {
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

  const handleEmailLogin = async (data: SignInFormData) => {
    setLoading("email");
    try {
      const result = await signInWithEmail(data, redirectTo || undefined);

      if (result && "error" in result) {
        if (result.error.includes("invalid email")) {
          toast.error("Invalid email address", {
            description: "Please enter a valid email address.",
          });
        } else if (result.error.includes("wrong password") || result.error.includes("Invalid login credentials")) {
          toast.error("Incorrect email or password", {
            description: "Please check your credentials and try again.",
          });
        } else if (result.error.includes("email not confirmed")) {
          toast.error("Email not confirmed", {
            description: "Please check your email and confirm your account before signing in.",
          });
        } else {
          toast.error("Sign in failed", {
            description: result.error,
          });
        }
      } else if (result && "success" in result) {
        if (result.redirectTo) {
          window.location.href = result.redirectTo;
        } else {
          window.location.href = redirectTo || "/dashboard";
        }
      }
    } catch {
      toast.error("An unexpected error occurred", {
        description: "Please try again later.",
      });
    } finally {
      setLoading(null);
    }
  };

  return (
    <div className="min-h-screen bg-background text-foreground flex flex-col relative overflow-hidden dark:bg-neutral-950 dark:text-white">
      {/* Star Background Effects */}
      <ShootingStars />
      <StarsBackground />

      {/* Go Home Button */}
      <div className="absolute top-6 left-6 z-30">
        <Link
          href="/"
          className="flex items-center gap-2 text-muted-foreground hover:text-foreground dark:text-neutral-400 dark:hover:text-white transition-colors pointer-events-auto"
        >
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
            <h1 className="text-3xl font-semibold mb-2 text-foreground dark:text-white">Log in to Orion</h1>
            <p className="text-muted-foreground dark:text-neutral-400">
              Don&apos;t have an account?{" "}
              <Link href="/signup" className="text-primary hover:text-primary/80 dark:text-white dark:hover:text-white/60 ease-in-out duration-200 font-medium">
                Sign up
              </Link>
            </p>
          </div>

          {/* Auth Form */}
          <div className="space-y-6">
            {/* OAuth Providers */}
            <div className="space-y-3">
              <Button
                variant="outline"
                className="w-full h-11 bg-background/50 border-border text-foreground hover:bg-muted dark:bg-white/10 dark:border-white/20 dark:text-white dark:hover:bg-white/20"
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

              <Button
                variant="outline"
                className="w-full h-11 bg-background/50 border-border text-foreground hover:bg-muted dark:bg-white/10 dark:border-white/20 dark:text-white dark:hover:bg-white/20"
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
            </div>

            <div className="relative">
              <div className="absolute inset-0 flex items-center">
                <div className="w-full border-t border-border dark:border-white/20"></div>
              </div>
              <div className="relative flex justify-center text-sm">
                <span className="bg-background dark:bg-neutral-950 px-4 text-muted-foreground dark:text-neutral-400">or</span>
              </div>
            </div>

            {/* Email/Password Form */}
            <form
              onSubmit={form.handleSubmit(handleEmailLogin)}
              className="space-y-4"
            >
              <div className="space-y-2">
                <Label htmlFor="email" className="text-foreground dark:text-white">Email</Label>
                <Input
                  id="email"
                  type="email"
                  placeholder="name@example.com"
                  {...form.register("email")}
                  className="bg-background border-border text-foreground placeholder:text-muted-foreground focus:border-ring dark:bg-white/10 dark:border-white/20 dark:text-white dark:placeholder:text-white/40 dark:focus:border-white/40 dark:focus:bg-white/15"
                />
                {form.formState.errors.email && (
                  <p className="text-destructive dark:text-red-400 text-sm">
                    {form.formState.errors.email.message}
                  </p>
                )}
              </div>

              <div className="space-y-2">
                <div className="flex items-center justify-between">
                  <Label htmlFor="password" className="text-foreground dark:text-white">Password</Label>
                  <Link
                    href="/reset-password"
                    className="text-sm text-muted-foreground hover:text-foreground dark:text-neutral-400 dark:hover:text-white"
                  >
                    Forgot password?
                  </Link>
                </div>
                <div className="relative">
                  <Input
                    id="password"
                    type={showPassword ? "text" : "password"}
                    placeholder="••••••••"
                    {...form.register("password")}
                    className="bg-background border-border text-foreground placeholder:text-muted-foreground focus:border-ring dark:bg-white/10 dark:border-white/20 dark:text-white dark:placeholder:text-white/40 dark:focus:border-white/40 dark:focus:bg-white/15 pr-10"
                  />
                  <button
                    type="button"
                    onClick={() => setShowPassword(!showPassword)}
                    className="absolute inset-y-0 right-0 pr-3 flex items-center text-muted-foreground hover:text-foreground dark:text-white/60 dark:hover:text-white"
                  >
                    {showPassword ? (
                      <EyeOff className="h-4 w-4" />
                    ) : (
                      <Eye className="h-4 w-4" />
                    )}
                  </button>
                </div>
                {form.formState.errors.password && (
                  <p className="text-destructive dark:text-red-400 text-sm">
                    {form.formState.errors.password.message}
                  </p>
                )}
              </div>

              <Button
                type="submit"
                className="w-full h-11 bg-primary text-primary-foreground hover:bg-primary/90 dark:bg-white dark:text-black dark:hover:bg-white/90 font-medium"
                disabled={loading !== null}
              >
                {loading === "email" ? (
                  <Loader2 className="w-5 h-5 animate-spin" />
                ) : (
                  "Sign in"
                )}
              </Button>
            </form>
          </div>

          {/* Terms */}
          <div className="mt-8 text-center text-xs text-muted-foreground dark:text-neutral-500">
            By signing in, you agree to our{" "}
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

export default function LoginPage() {
  return (
    <Suspense fallback={<div>Loading...</div>}>
      <LoginPageContent />
    </Suspense>
  );
}
