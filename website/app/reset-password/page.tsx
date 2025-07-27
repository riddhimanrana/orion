"use client";

import { useState } from "react";
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
  Mail,
  CheckCircle,
  ArrowLeft,
} from "lucide-react";
import Link from "next/link";
import { toast } from "sonner";
import {
  passwordResetRequestSchema,
  type PasswordResetRequestFormData,
} from "@/lib/auth-schemas";
import { requestPasswordReset } from "./actions";

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
        if (result.error.email) {
          form.setError("email", {
            type: "server",
            message: result.error.email[0],
          });
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
      <div className="min-h-screen flex items-center justify-center p-4 bg-gradient-to-br from-background via-background to-muted/20">
        <div className="w-full max-w-md">
          <Card className="border-border/50 shadow-lg">
            <CardHeader className="text-center space-y-4">
              <div className="mx-auto w-16 h-16 bg-blue-100 dark:bg-blue-900/20 rounded-full flex items-center justify-center">
                <Mail className="w-8 h-8 text-blue-600 dark:text-blue-400" />
              </div>
              <div>
                <CardTitle className="text-2xl">Check your email</CardTitle>
                <CardDescription className="mt-2">
                  If an account exists with that email address, we&apos;ve sent
                  password reset instructions.
                </CardDescription>
              </div>
            </CardHeader>
            <CardContent className="space-y-4 text-center">
              <div className="p-4 bg-muted/50 rounded-lg space-y-2">
                <CheckCircle className="w-5 h-5 text-blue-600 dark:text-blue-400 mx-auto" />
                <p className="text-sm font-medium">Reset link sent</p>
                <p className="text-xs text-muted-foreground">
                  The email should arrive within a few minutes. Please check
                  your spam folder if you don&apos;t see it.
                </p>
              </div>

              <div className="space-y-3">
                <p className="text-sm text-muted-foreground">
                  Didn&apos;t receive the email? Check your spam folder or{" "}
                  <button
                    onClick={() => {
                      setEmailSent(false);
                      // setSentEmail("");
                    }}
                    className="text-primary hover:underline font-medium"
                  >
                    try again
                  </button>
                </p>

                <div className="space-y-2">
                  <Button
                    variant="outline"
                    onClick={() => {
                      setEmailSent(false);
                      // setSentEmail("");
                    }}
                    className="w-full"
                  >
                    <ArrowLeft className="w-4 h-4 mr-2" />
                    Try different email
                  </Button>

                  <Button asChild variant="ghost" className="w-full">
                    <Link href="/login">
                      <ArrowLeft className="w-4 h-4 mr-2" />
                      Back to sign in
                    </Link>
                  </Button>
                </div>
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
          <h1 className="text-3xl font-bold tracking-tight">Reset password</h1>
          <p className="text-muted-foreground mt-2">
            Enter your email to receive reset instructions
          </p>
        </div>

        <Card className="border-border/50 shadow-lg">
          <CardHeader className="space-y-1 text-center">
            <CardTitle className="text-2xl">Forgot your password?</CardTitle>
            <CardDescription>
              No worries! Enter your email and we&apos;ll send you reset
              instructions.
            </CardDescription>
          </CardHeader>
          <CardContent className="space-y-6">
            <form
              onSubmit={form.handleSubmit(handleResetRequest)}
              className="space-y-4"
            >
              <div className="space-y-2">
                <Label htmlFor="email">Email address</Label>
                <Input
                  id="email"
                  type="email"
                  placeholder="Enter your email address"
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

              <Button
                type="submit"
                className="w-full h-11 font-medium"
                disabled={loading}
              >
                {loading ? (
                  <>
                    <Loader2 className="w-5 h-5 animate-spin mr-2" />
                    Sending Reset Link...
                  </>
                ) : (
                  <>
                    <Mail className="w-5 h-5 mr-2" />
                    Send Reset Link
                  </>
                )}
              </Button>
            </form>

            <div className="text-center text-sm text-muted-foreground space-y-2">
              <div>
                Remember your password?{" "}
                <Link
                  href="/login"
                  className="font-medium text-primary hover:underline"
                >
                  Sign in
                </Link>
              </div>
              <div>
                Don&apos;t have an account?{" "}
                <Link
                  href="/signup"
                  className="font-medium text-primary hover:underline"
                >
                  Sign up
                </Link>
              </div>
            </div>
          </CardContent>
        </Card>

        <div className="mt-8 text-center text-xs text-muted-foreground">
          Having trouble? Contact our{" "}
          <Link href="/contact" className="hover:underline">
            support team
          </Link>{" "}
          for assistance.
        </div>
      </div>
    </div>
  );
}
