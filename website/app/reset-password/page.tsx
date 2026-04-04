"use client";

import { useState } from "react";
import { useForm } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import {
  Loader2,
  Mail,
  CheckCircle,
  ArrowLeft,
} from "lucide-react";
import Link from "next/link";
import Image from "next/image";
import { toast } from "sonner";
import {
  passwordResetRequestSchema,
  type PasswordResetRequestFormData,
} from "@/lib/auth-schemas";
import { requestPasswordReset } from "./actions";
import { ShootingStars } from "@/components/ui/shooting-stars";
import { StarsBackground } from "@/components/ui/stars-background";

export default function ResetPasswordPage() {
  const [loading, setLoading] = useState(false);
  const [emailSent, setEmailSent] = useState(false);

  const form = useForm<PasswordResetRequestFormData>({
    resolver: zodResolver(passwordResetRequestSchema),
    defaultValues: {
      email: "",
    },
  });

  const handleResetRequest = async (data: PasswordResetRequestFormData) => {
    setLoading(true);
    try {
      const result = await requestPasswordReset(data);

      if (result?.error) {
        if (result.error.server) {
          toast.error(result.error.server[0]);
        }
      } else if (result?.success) {
        setEmailSent(true);
        toast.success("Reset link sent!", {
          description:
            "If an account exists with that email, we've sent reset instructions.",
        });
        form.reset();
      }
    } catch {
      toast.error("An unexpected error occurred", {
        description: "Please try again later.",
      });
    } finally {
      setLoading(false);
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
              <div className="w-16 h-16 mx-auto bg-blue-500 rounded-full flex items-center justify-center mb-4">
                <Mail className="w-8 h-8 text-white" />
              </div>
              <h1 className="text-2xl font-bold mb-2 text-foreground dark:text-white">Check your email</h1>
              <p className="text-muted-foreground dark:text-neutral-400">
                If an account exists with that email address, we&apos;ve sent password reset instructions.
              </p>
            </div>

            <div className="space-y-4">
                <div className="p-4 bg-muted/50 dark:bg-neutral-800/50 rounded-lg space-y-2">
                <CheckCircle className="w-5 h-5 text-blue-500 mx-auto" />
                <p className="text-sm font-medium text-foreground dark:text-white">Reset link sent</p>
                <p className="text-xs text-muted-foreground dark:text-neutral-400">
                  The email should arrive within a few minutes. Please check your spam folder if you don&apos;t see it.
                </p>
              </div>              <div className="space-y-3">
                <p className="text-sm text-muted-foreground dark:text-neutral-400">
                  Didn&apos;t receive the email?{" "}
                  <button
                    onClick={() => setEmailSent(false)}
                    className="text-primary hover:underline dark:text-blue-400 dark:hover:text-blue-300 font-medium"
                  >
                    Try again
                  </button>
                </p>

                <div className="space-y-2">
                  <Button
                    variant="outline"
                    onClick={() => setEmailSent(false)}
                    className="w-full"
                  >
                    <ArrowLeft className="w-4 h-4 mr-2" />
                    Try different email
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
            <h1 className="text-3xl font-bold mb-2 text-foreground dark:text-white">Reset password</h1>
            <p className="text-muted-foreground dark:text-neutral-400">
              Enter your email to receive reset instructions
            </p>
          </div>

          {/* Reset Form */}
          <div className="space-y-6">
            <form
              onSubmit={form.handleSubmit(handleResetRequest)}
              className="space-y-4"
            >
              <div className="space-y-2">
                <Label htmlFor="email" className="text-foreground dark:text-white">Email address</Label>
                <Input
                  id="email"
                  type="email"
                  placeholder="name@example.com"
                  {...form.register("email")}
                  className={`bg-background border-border text-foreground placeholder:text-muted-foreground focus:border-ring dark:bg-white/10 dark:border-white/20 dark:text-white dark:placeholder:text-white/40 dark:focus:border-white/40 dark:focus:bg-white/15 ${form.formState.errors.email ? "border-destructive dark:border-red-400" : ""}`}
                />
                {form.formState.errors.email && (
                  <p className="text-destructive dark:text-red-400 text-sm">
                    {form.formState.errors.email.message}
                  </p>
                )}
              </div>

              <Button
                type="submit"
                className="w-full h-11 bg-primary text-primary-foreground hover:bg-primary/90 dark:bg-white dark:text-black dark:hover:bg-white/90"
                disabled={loading}
              >
                {loading ? (
                  <Loader2 className="w-5 h-5 animate-spin" />
                ) : (
                  <Mail className="w-5 h-5 mr-2" />
                )}
                {loading ? "Sending Reset Link..." : "Send Reset Link"}
              </Button>
            </form>

            <div className="text-center text-sm text-muted-foreground dark:text-neutral-400 space-y-2">
              <div>
                Remember your password?{" "}
                <Link
                  href="/login"
                  className="font-medium text-primary hover:underline dark:text-blue-400 dark:hover:text-blue-300"
                >
                  Sign in
                </Link>
              </div>
              <div>
                Don&apos;t have an account?{" "}
                <Link
                  href="/signup"
                  className="font-medium text-primary hover:underline dark:text-blue-400 dark:hover:text-blue-300"
                >
                  Sign up
                </Link>
              </div>
            </div>
          </div>

          {/* Support */}
          <div className="mt-8 text-center text-xs text-muted-foreground dark:text-neutral-500">
            Having trouble? Contact our{" "}
            <Link href="/contact" className="hover:text-primary dark:hover:text-blue-400">
              support team
            </Link>{" "}
            for assistance.
          </div>
        </div>
      </div>
    </div>
  );
}
