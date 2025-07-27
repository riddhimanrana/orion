"use client";

import { useState, useEffect, useCallback, useRef } from "react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
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
  AlertCircle,
} from "lucide-react";
import { toast } from "sonner";
import { changeUserEmail } from "@/app/account/actions";
import { useRouter } from "next/navigation";

interface EmailChangeFormProps {
  currentEmail: string;
}

type ValidationState = {
  isValid: boolean;
  isChecking: boolean;
  isAvailable: boolean | null;
  error: string | null;
};

export default function EmailChangeForm({
  currentEmail,
}: EmailChangeFormProps) {
  const [newEmail, setNewEmail] = useState("");
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [validation, setValidation] = useState<ValidationState>({
    isValid: false,
    isChecking: false,
    isAvailable: null,
    error: null,
  });
  const checkTimeoutRef = useRef<NodeJS.Timeout | null>(null);
  const router = useRouter();

  // Validate email format
  const validateEmailFormat = (email: string): boolean => {
    const emailRegex = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;
    return emailRegex.test(email);
  };

  // Check email availability with debouncing
  const checkAvailability = useCallback(async (email: string) => {
    if (!email || !validateEmailFormat(email)) {
      setValidation({
        isValid: false,
        isChecking: false,
        isAvailable: null,
        error:
          email && !validateEmailFormat(email) ? "Invalid email format" : null,
      });
      return;
    }

    setValidation((prev) => ({ ...prev, isChecking: true, error: null }));

    try {
      const response = await fetch("/api/check-email", {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
        },
        body: JSON.stringify({ email }),
      });

      if (!response.ok) {
        throw new Error("Failed to check email availability");
      }

      const result = await response.json();

      setValidation({
        isValid: result.available === true,
        isChecking: false,
        isAvailable: result.available,
        error: result.error,
      });
    } catch (error) {
      setValidation({
        isValid: false,
        isChecking: false,
        isAvailable: null,
        error:
          error instanceof Error
            ? error.message
            : "Failed to check email availability",
      });
    }
  }, []);

  // Handle email input changes with debouncing
  useEffect(() => {
    if (newEmail.trim() === "") {
      setValidation({
        isValid: false,
        isChecking: false,
        isAvailable: null,
        error: null,
      });
      if (checkTimeoutRef.current) {
        clearTimeout(checkTimeoutRef.current);
        checkTimeoutRef.current = null;
      }
      return;
    }

    // Clear existing timeout
    if (checkTimeoutRef.current) {
      clearTimeout(checkTimeoutRef.current);
    }

    const timeout = setTimeout(() => {
      checkAvailability(newEmail.trim());
    }, 500);

    checkTimeoutRef.current = timeout;

    return () => {
      clearTimeout(timeout);
    };
  }, [newEmail, checkAvailability]);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();

    if (!validation.isValid || validation.isAvailable !== true) {
      toast.error("Please enter a valid and available email address");
      return;
    }

    setIsSubmitting(true);

    try {
      const result = await changeUserEmail(newEmail.trim());

      if (result.success) {
        toast.success("Email change initiated!", {
          description: result.message,
        });

        // Redirect to confirmation page
        router.push("/account/change-email-confirm");
      }
    } catch (error) {
      const errorMessage =
        error instanceof Error ? error.message : "Failed to change email";
      toast.error("Email change failed", {
        description: errorMessage,
      });
    } finally {
      setIsSubmitting(false);
    }
  };

  const getValidationIcon = () => {
    if (validation.isChecking) {
      return <Loader2 className="w-4 h-4 text-muted-foreground animate-spin" />;
    }

    if (validation.error) {
      return <XCircle className="w-4 h-4 text-red-500" />;
    }

    if (validation.isAvailable === true) {
      return <CheckCircle className="w-4 h-4 text-green-500" />;
    }

    return null;
  };

  const getValidationMessage = () => {
    if (validation.isChecking) {
      return "Checking availability...";
    }

    if (validation.error) {
      return validation.error;
    }

    if (validation.isAvailable === true) {
      return "Email is available";
    }

    if (validation.isAvailable === false) {
      return "Email is not available";
    }

    return null;
  };

  const getValidationColor = () => {
    if (validation.isChecking) {
      return "text-muted-foreground";
    }

    if (validation.error || validation.isAvailable === false) {
      return "text-red-600 dark:text-red-400";
    }

    if (validation.isAvailable === true) {
      return "text-green-600 dark:text-green-400";
    }

    return "text-muted-foreground";
  };

  return (
    <Card>
      <CardHeader>
        <CardTitle className="flex items-center space-x-2">
          <Mail className="w-5 h-5" />
          <span>Change Email Address</span>
        </CardTitle>
        <CardDescription>
          Update your account email address. You&apos;ll need to confirm both
          your old and new email addresses.
        </CardDescription>
      </CardHeader>
      <CardContent className="space-y-6">
        <div className="space-y-2">
          <Label htmlFor="current-email">Current Email</Label>
          <Input
            id="current-email"
            type="email"
            value={currentEmail}
            disabled
            className="bg-muted"
          />
        </div>

        <form onSubmit={handleSubmit} className="space-y-4">
          <div className="space-y-2">
            <Label htmlFor="new-email">New Email Address</Label>
            <div className="relative">
              <Input
                id="new-email"
                type="email"
                placeholder="Enter your new email address"
                value={newEmail}
                onChange={(e) => setNewEmail(e.target.value)}
                className={`pr-10 ${
                  validation.error || validation.isAvailable === false
                    ? "border-red-500 focus:border-red-500"
                    : validation.isAvailable === true
                      ? "border-green-500 focus:border-green-500"
                      : ""
                }`}
                disabled={isSubmitting}
              />
              <div className="absolute right-3 top-1/2 transform -translate-y-1/2">
                {getValidationIcon()}
              </div>
            </div>
            {getValidationMessage() && (
              <p className={`text-sm ${getValidationColor()}`}>
                {getValidationMessage()}
              </p>
            )}
          </div>

          {/* <div className="p-4 bg-blue-50 dark:bg-blue-900/10 border border-blue-200 dark:border-blue-800 rounded-lg">
            <div className="flex items-start space-x-3">
              <Shield className="w-5 h-5 text-blue-600 dark:text-blue-400 mt-0.5 flex-shrink-0" />
              <div className="space-y-1">
                <h4 className="text-sm font-medium text-blue-900 dark:text-blue-100">
                  Email Change Process
                </h4>
                <div className="text-sm text-blue-700 dark:text-blue-300 space-y-1">
                  <p>
                    1. We&apos;ll send confirmation links to both your old and
                    new email addresses
                  </p>
                  <p>
                    2. Click the link in your old email to verify the change was
                    authorized
                  </p>
                  <p>
                    3. Click the link in your new email to complete the change
                  </p>
                  <p className="font-medium">
                    Both confirmations are required for security
                  </p>
                </div>
              </div>
            </div>
          </div> */}

          <Button
            type="submit"
            disabled={
              !validation.isValid ||
              validation.isAvailable !== true ||
              isSubmitting
            }
            className="w-full"
          >
            {isSubmitting ? (
              <>
                <Loader2 className="w-4 h-4 mr-2 animate-spin" />
                Initiating Email Change...
              </>
            ) : (
              <>
                <Mail className="w-4 h-4 mr-2" />
                Change Email Address
              </>
            )}
          </Button>
        </form>

        <div className="flex items-center text-xs text-muted-foreground">
          <AlertCircle className="w-4 h-4 inline mr-2 flex-shrink-0" />
          Make sure you have access to both email addresses before proceeding.
        </div>
      </CardContent>
    </Card>
  );
}
