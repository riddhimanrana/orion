"use client";

import { useState, useEffect, Suspense } from "react";
import { useSearchParams, useRouter } from "next/navigation";
import { Button } from "@/components/ui/button";
// Card components removed as they're not used in this page
import {
  CheckCircle,
  XCircle,
  Mail,
  ArrowRight,
  RefreshCw,
  Clock,
  Shield,
} from "lucide-react";
import Link from "next/link";
import { createClient } from "@/utils/supabase/client";

interface ConfirmationState {
  type: "loading" | "success" | "error" | "info";
  title: string;
  description: string;
  message?: string;
  showActions: boolean;
  email?: string;
}

function EmailChangeConfirmContent() {
  const [state, setState] = useState<ConfirmationState>({
    type: "loading",
    title: "Loading...",
    description: "Please wait",
    showActions: false,
  });
  const [isLoggedIn, setIsLoggedIn] = useState<boolean | null>(null);
  const searchParams = useSearchParams();
  const router = useRouter();

  const success = searchParams.get("success");
  const error = searchParams.get("error");
  const type = searchParams.get("type");
  const email = searchParams.get("email");

  useEffect(() => {
    // Check if user is logged in and handle confirmations
    const checkAuthAndHandleConfirmation = async () => {
      const supabase = createClient();
      const {
        data: { user },
      } = await supabase.auth.getUser();
      setIsLoggedIn(!!user);

      // Parse URL fragment for Supabase messages
      const parseFragment = () => {
        if (typeof window !== "undefined") {
          const fragment = window.location.hash.substring(1);
          const params = new URLSearchParams(fragment);
          return {
            message: params.get("message"),
            error_description: params.get("error_description"),
            error: params.get("error"),
            type: params.get("type"),
          };
        }
        return {
          message: null,
          error_description: null,
          error: null,
          type: null,
        };
      };

      const fragment = parseFragment();

      // Handle different states based on URL parameters and fragments
      if (fragment.message) {
        // Handle Supabase success messages from URL fragment
        if (fragment.message.includes("Confirmation link accepted")) {
          if (fragment.message.includes("other email")) {
            // First confirmation done, need to check other email
            setState({
              type: "success",
              title: "First Email Confirmed!",
              description:
                "You've confirmed one part of the email change process.",
              message:
                "Great! Now please check your OTHER email address and click the confirmation link there to complete the email change process.",
              showActions: true,
            });
          } else {
            // Email change completed
            setState({
              type: "success",
              title: "Email Change Complete! 🎉",
              description: "Your email address has been successfully updated.",
              message: `Your account now uses your new email address. You can continue using your account normally.`,
              showActions: true,
              email: user?.email || undefined,
            });
          }
        } else {
          setState({
            type: "info",
            title: "Email Confirmation",
            description: "Email confirmation processed.",
            message: fragment.message,
            showActions: true,
          });
        }
      } else if (fragment.error || fragment.error_description) {
        // Handle Supabase error messages from URL fragment
        const errorMsg =
          fragment.error_description ||
          fragment.error ||
          "An error occurred during confirmation.";

        setState({
          type: "error",
          title: "Confirmation Failed",
          description: "There was an issue with the email confirmation.",
          message: errorMsg,
          showActions: true,
        });
      } else if (success) {
        handleSuccessState(success, email);
      } else if (error) {
        handleErrorState(error, type);
      } else {
        // Default state - email change initiated
        setState({
          type: "info",
          title: "Confirm Your Email Change",
          description:
            "We&apos;ve sent confirmation links to both your old and new email addresses.",
          message:
            "You must click both links to complete the email change. This is a security measure to protect your account.",
          showActions: true,
        });
      }
    };

    checkAuthAndHandleConfirmation();
  }, [success, error, type, email]);

  const handleSuccessState = (successType: string, email: string | null) => {
    switch (successType) {
      case "old_email_confirmed":
        setState({
          type: "success",
          title: "Old Email Confirmed",
          description:
            "You&apos;ve successfully confirmed your previous email address.",
          message:
            "Now check your NEW email address and click the confirmation link to complete the email change.",
          showActions: true,
        });
        break;
      case "step_completed":
        setState({
          type: "success",
          title: "Email Confirmation Step Complete",
          description:
            "One part of the email change process has been completed.",
          message:
            "Great! Now please check your other email address (either your old or new email) and click the confirmation link there to complete the email change process.",
          showActions: true,
          email: email || undefined,
        });
        break;
      case "confirmation_processed":
        setState({
          type: "success",
          title: "Email Confirmation Processed",
          description:
            "Your email confirmation has been successfully processed.",
          message:
            "The confirmation link has been processed. If this was part of an email change, you may need to check for additional confirmation emails.",
          showActions: true,
        });
        break;
      case "email_confirmed":
        setState({
          type: "success",
          title: "Email Confirmation Successful!",
          description:
            "Your email confirmation has been processed successfully.",
          message: email
            ? `Your email address has been confirmed. Your account now uses: ${email}`
            : "Your email confirmation link has been processed. You may now be able to access your account with your new email address.",
          showActions: true,
          email: email || undefined,
        });
        break;
      case "email_changed":
        setState({
          type: "success",
          title: "Email Successfully Changed! 🎉",
          description: `Your email address has been updated${email ? ` to ${email}` : ""}.`,
          message:
            "Your account is now using the new email address. You can continue using your account normally.",
          showActions: true,
          email: email || undefined,
        });
        break;
      default:
        setState({
          type: "success",
          title: "Email Confirmation",
          description: "Email confirmation processed successfully.",
          showActions: true,
        });
    }
  };

  const handleErrorState = (
    errorType: string,
    confirmationType: string | null,
  ) => {
    switch (errorType) {
      case "invalid_link":
        setState({
          type: "error",
          title: "Invalid Confirmation Link",
          description:
            "This confirmation link appears to be invalid or malformed.",
          message:
            "This may happen if the link was corrupted during email transmission. Please check your email for the correct confirmation link, or request a new email change from your account settings.",
          showActions: true,
        });
        break;
      case "link_expired":
        setState({
          type: "error",
          title: "Link Expired",
          description: "This confirmation link has expired.",
          message:
            "Confirmation links expire for security reasons. Please start the email change process again.",
          showActions: true,
        });
        break;
      case "invalid_token":
        setState({
          type: "error",
          title: "Invalid Token",
          description: "The confirmation token is invalid.",
          message:
            "This link may have been corrupted or is not valid. Please try the link from your email again.",
          showActions: true,
        });
        break;
      case "already_confirmed":
        setState({
          type: "info",
          title: "Already Confirmed",
          description: `This ${confirmationType === "email_change_confirm_old" ? "old" : "new"} email has already been confirmed.`,
          message:
            confirmationType === "email_change_confirm_old"
              ? "Please check your NEW email address for the second confirmation link."
              : "Your email change has already been completed.",
          showActions: true,
        });
        break;
      case "confirmation_failed":
        setState({
          type: "error",
          title: "Confirmation Failed",
          description: "We couldn&apos;t confirm your email address.",
          message:
            "There was a problem processing your confirmation. Please try again or start a new email change.",
          showActions: true,
        });
        break;
      case "unexpected_error":
        setState({
          type: "error",
          title: "Something Went Wrong",
          description: "An unexpected error occurred.",
          message:
            "Please try again or contact support if the problem persists.",
          showActions: true,
        });
        break;
      default:
        setState({
          type: "error",
          title: "Error",
          description: "An error occurred during email confirmation.",
          showActions: true,
        });
    }
  };

  const getIcon = () => {
    switch (state.type) {
      case "success":
        return (
          <CheckCircle className="w-8 h-8 text-green-600 dark:text-green-400" />
        );
      case "error":
        return <XCircle className="w-8 h-8 text-red-600 dark:text-red-400" />;
      case "info":
        return <Mail className="w-8 h-8 text-blue-600 dark:text-blue-400" />;
      default:
        return <Mail className="w-8 h-8 text-primary" />;
    }
  };

  const getBackgroundColor = () => {
    switch (state.type) {
      case "success":
        return "bg-green-100 dark:bg-green-900/20";
      case "error":
        return "bg-red-100 dark:bg-red-900/20";
      case "info":
        return "bg-blue-100 dark:bg-blue-900/20";
      default:
        return "bg-primary/10";
    }
  };

  const getMessageStyle = () => {
    switch (state.type) {
      case "success":
        return "bg-green-50 dark:bg-green-900/10 border-green-200 dark:border-green-800 text-green-800 dark:text-green-200";
      case "error":
        return "bg-red-50 dark:bg-red-900/10 border-red-200 dark:border-red-800 text-red-800 dark:text-red-200";
      case "info":
        return "bg-blue-50 dark:bg-blue-900/10 border-blue-200 dark:border-blue-800 text-blue-800 dark:text-blue-200";
      default:
        return "bg-primary/5 border-primary/20 text-foreground";
    }
  };

  const renderActions = () => {
    if (!state.showActions) return null;

    const baseActions = (
      <>
        {isLoggedIn && (
          <Button onClick={() => router.push("/account")} className="w-full">
            <ArrowRight className="w-4 h-4 mr-2" />
            Go to Account Settings
          </Button>
        )}

        {!isLoggedIn && (
          <Button onClick={() => router.push("/login")} className="w-full">
            <ArrowRight className="w-4 h-4 mr-2" />
            Sign In to Your Account
          </Button>
        )}
      </>
    );

    if (state.type === "error") {
      return (
        <div className="space-y-3">
          {error === "link_expired" && (
            <Button
              onClick={() => router.push("/account")}
              className="w-full"
              variant="outline"
            >
              <RefreshCw className="w-4 h-4 mr-2" />
              Start New Email Change
            </Button>
          )}

          {error === "invalid_link" && (
            <Button
              onClick={() => router.push("/account")}
              className="w-full"
              variant="outline"
            >
              <Mail className="w-4 h-4 mr-2" />
              Check Account Settings
            </Button>
          )}

          {baseActions}

          <div className="text-xs text-muted-foreground text-center">
            Need help?{" "}
            <Link href="/contact" className="text-primary hover:underline">
              Contact support
            </Link>
          </div>
        </div>
      );
    }

    // if (success === "step_completed") {
    //   return (
    //     <div className="space-y-3">
    //       <div className="p-3 bg-blue-50 dark:bg-blue-900/10 border border-blue-200 dark:border-blue-800 rounded-lg text-center">
    //         <p className="text-sm text-blue-700 dark:text-blue-300">
    //           One more step! Check your other email inbox for the second
    //           confirmation link.
    //         </p>
    //       </div>
    //       {baseActions}
    //       <div className="text-xs text-muted-foreground text-center">
    //         Complete the process by confirming your other email
    //       </div>
    //     </div>
    //   );
    // }

    // if (success === "email_confirmed" || success === "confirmation_processed") {
    //   return (
    //     <div className="space-y-3">
    //       <div className="p-4 bg-green-50 dark:bg-green-900/10 border border-green-200 dark:border-green-800 rounded-lg">
    //         <div className="flex items-center justify-center space-x-2 mb-2">
    //           <CheckCircle className="w-5 h-5 text-green-600 dark:text-green-400" />
    //           <span className="font-medium text-green-800 dark:text-green-200">
    //             Email Confirmed Successfully
    //           </span>
    //         </div>
    //         {state.email && (
    //           <p className="text-sm text-green-600 dark:text-green-400 text-center">
    //             Confirmed for: <span className="font-mono">{state.email}</span>
    //           </p>
    //         )}
    //       </div>
    //       {baseActions}
    //       <div className="text-xs text-muted-foreground text-center">
    //         Your email confirmation has been processed
    //       </div>
    //     </div>
    //   );
    // }

    if (success === "email_changed" || success === "email_confirmed") {
      return (
        <div className="space-y-3">
          {baseActions}
          <div className="text-xs text-muted-foreground text-center">
            Your email change is now complete
          </div>
        </div>
      );
    }

    if (
      state.type === "success" &&
      (state.title.includes("First Email Confirmed") ||
        state.title.includes("Confirmation Successful"))
    ) {
      return (
        <div className="space-y-3">
          {state.message && state.message.includes("OTHER email") && (
            <div className="p-3 bg-blue-50 dark:bg-blue-900/10 border border-blue-200 dark:border-blue-800 rounded-lg text-center">
              <p className="text-sm text-blue-700 dark:text-blue-300">
                📧 One more step! Check your other email inbox for the second
                confirmation link.
              </p>
            </div>
          )}
          {baseActions}
          <div className="text-xs text-muted-foreground text-center">
            {state.message && state.message.includes("OTHER email")
              ? "Complete the process by confirming your other email"
              : "Email confirmation processed successfully"}
          </div>
        </div>
      );
    }

    if (
      state.type === "success" &&
      state.title.includes("Email Change Complete")
    ) {
      return (
        <div className="space-y-3">
          {state.email && (
            <div className="p-4 bg-green-50 dark:bg-green-900/10 border border-green-200 dark:border-green-800 rounded-lg space-y-2">
              <div className="flex items-center justify-center">
                <CheckCircle className="w-5 h-5 text-green-600 dark:text-green-400 mr-2" />
                <span className="font-medium text-green-800 dark:text-green-200">
                  Email Successfully Updated
                </span>
              </div>
              <p className="text-sm text-green-600 dark:text-green-400 text-center">
                Your account now uses:{" "}
                <span className="font-mono font-medium">{state.email}</span>
              </p>
            </div>
          )}
          {baseActions}
          <div className="text-xs text-muted-foreground text-center">
            Your email change is now complete
          </div>
        </div>
      );
    }

    return <div className="space-y-3">{baseActions}</div>;
  };

  if (state.type === "loading") {
    return (
      <div className="min-h-screen flex items-center justify-center bg-gradient-to-br from-background via-background to-muted/20">
        <div className="w-full max-w-md p-8 space-y-6 bg-card text-card-foreground rounded-lg shadow-lg">
          <div className="text-center">
            <div className="mx-auto w-16 h-16 bg-primary/10 rounded-full flex items-center justify-center">
              <Mail className="w-8 h-8 text-primary animate-pulse" />
            </div>
            <h1 className="text-3xl font-bold mt-4">Loading...</h1>
            <p className="text-muted-foreground mt-2">
              Processing your request...
            </p>
          </div>
        </div>
      </div>
    );
  }

  return (
    <div className="min-h-screen flex items-center justify-center bg-gradient-to-br from-background via-background to-muted/20">
      <div className="w-full max-w-md p-8 space-y-6 bg-card text-card-foreground rounded-lg shadow-lg">
        <div className="text-center">
          <div
            className={`mx-auto w-16 h-16 ${getBackgroundColor()} rounded-full flex items-center justify-center`}
          >
            {getIcon()}
          </div>
          <h1 className="text-3xl font-bold mt-4">{state.title}</h1>
          <p className="text-muted-foreground mt-2">{state.description}</p>
        </div>

        {state.message && (
          <div className={`p-4 border rounded-lg ${getMessageStyle()}`}>
            <p className="text-sm">{state.message}</p>
          </div>
        )}

        {state.type === "success" &&
          state.title.includes("First Email Confirmed") && (
            <div className="space-y-4">
              <div className="p-4 bg-blue-50 dark:bg-blue-900/10 border border-blue-200 dark:border-blue-800 rounded-lg space-y-4">
                <div className="flex items-start space-x-3">
                  <CheckCircle className="w-5 h-5 text-green-600 dark:text-green-400 mt-1 flex-shrink-0" />
                  <div>
                    <h2 className="font-semibold text-green-800 dark:text-green-200">
                      First Email Confirmed ✓
                    </h2>
                    <p className="text-sm text-green-600 dark:text-green-400">
                      You&apos;ve successfully confirmed one part of the email
                      change.
                    </p>
                  </div>
                </div>
                <div className="flex items-start space-x-3">
                  <Clock className="w-5 h-5 text-blue-600 dark:text-blue-400 mt-1 flex-shrink-0" />
                  <div>
                    <h2 className="font-semibold text-blue-800 dark:text-blue-200">
                      Next Step: Check Your Other Email
                    </h2>
                    <p className="text-sm text-blue-600 dark:text-blue-400">
                      Click the confirmation link in your OTHER email address to
                      complete the email change.
                    </p>
                  </div>
                </div>
              </div>
              <div className="text-center text-sm text-muted-foreground">
                <Shield className="w-4 h-4 inline mr-1" />
                This two-step process ensures your account security.
              </div>
            </div>
          )}

        {state.type === "success" &&
          state.title.includes("Email Change Complete") &&
          state.email && (
            <div className="p-4 bg-green-50 dark:bg-green-900/10 border border-green-200 dark:border-green-800 rounded-lg space-y-2">
              <div className="flex items-center justify-center">
                <CheckCircle className="w-5 h-5 text-green-600 dark:text-green-400 mr-2" />
                <span className="font-medium text-green-800 dark:text-green-200">
                  Email Successfully Updated
                </span>
              </div>
              <p className="text-sm text-green-600 dark:text-green-400 text-center">
                Your account now uses:{" "}
                <span className="font-mono font-medium">{state.email}</span>
              </p>
            </div>
          )}

        {!success && !error && (
          <div className="p-4 bg-primary/5 border border-primary/20 rounded-lg space-y-4">
            <div className="flex items-start space-x-3">
              <CheckCircle className="w-5 h-5 text-primary mt-1 flex-shrink-0" />
              <div>
                <h2 className="font-semibold">Check Your Old Email</h2>
                <p className="text-sm text-muted-foreground">
                  Click the link we sent to your previous email address to
                  confirm that you authorized this change.
                </p>
              </div>
            </div>
            <div className="flex items-start space-x-3">
              <CheckCircle className="w-5 h-5 text-primary mt-1 flex-shrink-0" />
              <div>
                <h2 className="font-semibold">Check Your New Email</h2>
                <p className="text-sm text-muted-foreground">
                  Click the link we sent to your new email address to verify it.
                </p>
              </div>
            </div>
          </div>
        )}

        {renderActions()}

        {!success && !error && (
          <div className="text-center text-sm text-muted-foreground">
            <p>You must click both links to complete the email change.</p>
            <p className="mt-1">
              This is a security measure to protect your account.
            </p>
          </div>
        )}
      </div>
    </div>
  );
}

export default function ChangeEmailConfirmPage() {
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
      <EmailChangeConfirmContent />
    </Suspense>
  );
}
