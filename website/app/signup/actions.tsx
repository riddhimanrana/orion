"use server";
// New: Check account existence and confirmation status by querying auth.users
export async function checkAccount(email: string): Promise<EmailStatusResponse> {
  const supabase = await createClient();
  try {
    // Use listUsers with email filter
    const { data, error } = await supabase.auth.admin.listUsers({
      page: 1,
      perPage: 100,
    });
    if (error) {
      if (error.message && error.message.includes("User not found")) {
        return { exists: false, confirmed: false };
      }
      console.error("Error querying users table:", error);
      return { exists: false, confirmed: false, error: error.message };
    }
    if (!data || !data.users || data.users.length === 0) {
      return { exists: false, confirmed: false };
    }
    // Find user by email (case-insensitive)
    const user = data.users.find(
      (u: { email?: string }) =>
        typeof u.email === "string" &&
        u.email.toLowerCase() === email.toLowerCase()
    );
    if (!user) {
      return { exists: false, confirmed: false };
    }
    const confirmed = !!user.email_confirmed_at;
    return { exists: true, confirmed };
  } catch (error: unknown) {
    let message = "Failed to check account status";
    if (
      error &&
      typeof error === "object" &&
      "message" in error &&
      typeof (error as Record<string, unknown>)["message"] === "string"
    ) {
      message = (error as { message: string }).message;
    }
    console.error("Error in checkAccount:", error);
    return { exists: false, confirmed: false, error: message };
  }
}
import { createClient } from "@/utils/supabase/server";
import type {
  SignUpFormData,
  OAuthAuthResponse,
  EmailSignUpResponse,
} from "@/lib/auth-schemas";

export interface EmailStatusResponse {
  exists: boolean;
  confirmed: boolean;
  error?: string;
}

export interface ResendVerificationResponse {
  success: boolean;
  error?: string;
  message?: string;
}

export async function signUpWithGoogle(
  redirectTo?: string,
): Promise<OAuthAuthResponse> {
  const supabase = await createClient();

  const callbackUrl = new URL(
    `${process.env.NEXT_PUBLIC_SITE_URL}/auth/callback`,
  );
  if (redirectTo) {
    callbackUrl.searchParams.set("redirectTo", redirectTo);
  }

  const { data, error } = await supabase.auth.signInWithOAuth({
    provider: "google",
    options: {
      redirectTo: callbackUrl.toString(),
    },
  });

  if (error) {
    console.error("Error signing up with Google:", error);
    return { error: error.message };
  }

  if (data.url) {
    return { success: true, url: data.url };
  }

  return { error: "Failed to initiate Google sign up" };
}

export async function signUpWithGitHub(
  redirectTo?: string,
): Promise<OAuthAuthResponse> {
  const supabase = await createClient();

  const callbackUrl = new URL(
    `${process.env.NEXT_PUBLIC_SITE_URL}/auth/callback`,
  );
  if (redirectTo) {
    callbackUrl.searchParams.set("redirectTo", redirectTo);
  }

  const { data, error } = await supabase.auth.signInWithOAuth({
    provider: "github",
    options: {
      redirectTo: callbackUrl.toString(),
    },
  });

  if (error) {
    console.error("Error signing up with GitHub:", error);
    return { error: error.message };
  }

  if (data.url) {
    return { success: true, url: data.url };
  }

  return { error: "Failed to initiate GitHub sign up" };
}

export async function signUpWithApple(
  redirectTo?: string,
): Promise<OAuthAuthResponse> {
  const supabase = await createClient();

  const callbackUrl = new URL(
    `${process.env.NEXT_PUBLIC_SITE_URL}/auth/callback`,
  );
  if (redirectTo) {
    callbackUrl.searchParams.set("redirectTo", redirectTo);
  }

  const { data, error } = await supabase.auth.signInWithOAuth({
    provider: "apple",
    options: {
      redirectTo: callbackUrl.toString(),
    },
  });

  if (error) {
    console.error("Error signing up with Apple:", error);
    return { error: error.message };
  }

  if (data.url) {
    return { success: true, url: data.url };
  }

  return { error: "Failed to initiate Apple sign up" };
}

export async function checkEmailStatus(
  email: string,
): Promise<EmailStatusResponse> {
  const supabase = await createClient();

  try {
    // Try to sign in with a dummy password to check if email exists
    const { error } = await supabase.auth.signInWithPassword({
      email,
      password: "dummy-password-for-checking",
    });

    if (error) {
      // If error mentions "Invalid login credentials", email exists but password is wrong
      if (
        error.message.includes("Invalid login credentials") ||
        error.message.includes("invalid credentials")
      ) {
        return { exists: true, confirmed: true };
      }

      // If error mentions email not confirmed
      if (
        error.message.includes("Email not confirmed") ||
        error.message.includes("signup_disabled")
      ) {
        return { exists: true, confirmed: false };
      }

      // If user not found, email doesn't exist
      if (error.message.includes("User not found")) {
        return { exists: false, confirmed: false };
      }

      // For other errors, assume email doesn't exist
      return { exists: false, confirmed: false };
    }

    // If no error, user exists and is confirmed
    return { exists: true, confirmed: true };
  } catch (error) {
    console.error("Error checking email status:", error);
    return {
      exists: false,
      confirmed: false,
      error: "Failed to check email status",
    };
  }
}

export async function resendEmailVerification(
  email: string,
): Promise<ResendVerificationResponse> {
  const supabase = await createClient();

  try {
    const { error } = await supabase.auth.resend({
      type: "signup",
      email,
      options: {
        emailRedirectTo: `${process.env.NEXT_PUBLIC_SITE_URL}/auth/callback?type=signup`,
      },
    });

    if (error) {
      console.error("Error resending verification email:", error);

      if (error.message.includes("rate limit")) {
        return {
          success: false,
          error: "Please wait before requesting another verification email.",
        };
      }

      if (error.message.includes("already confirmed")) {
        return {
          success: false,
          error: "This email is already confirmed. You can sign in normally.",
        };
      }

      return { success: false, error: error.message };
    }

    return {
      success: true,
      message: "Verification email sent successfully! Please check your inbox.",
    };
  } catch (error) {
    console.error("Unexpected error resending verification:", error);
    return {
      success: false,
      error: "An unexpected error occurred. Please try again.",
    };
  }
}

export async function signUpWithEmail(
  formData: SignUpFormData,
  redirectTo?: string,
): Promise<EmailSignUpResponse> {
  const supabase = await createClient();

  const { email, password, fullName } = formData;

  try {
    const { data, error } = await supabase.auth.signUp({
      email,
      password,
      options: {
        emailRedirectTo: redirectTo
          ? `${process.env.NEXT_PUBLIC_SITE_URL}/auth/callback?type=signup&redirectTo=${encodeURIComponent(redirectTo)}`
          : `${process.env.NEXT_PUBLIC_SITE_URL}/auth/callback?type=signup`,
        data: {
          full_name: fullName,
        },
      },
    });

    if (error) {
      console.error("Error signing up with email:", error);

      // Handle specific error cases
      if (
        error.message.includes("already registered") ||
        error.message.includes("already exists")
      ) {
        return {
          error:
            "This email is already registered. Please try signing in instead.",
        };
      } else if (error.message.includes("invalid email")) {
        return { error: "Please enter a valid email address." };
      } else if (
        error.message.includes("weak password") ||
        error.message.includes("Password should be")
      ) {
        return {
          error:
            "Password is too weak. Please choose a stronger password with at least 8 characters, including uppercase, lowercase, and numbers.",
        };
      } else if (error.message.includes("rate limit")) {
        return { error: "Too many signup attempts. Please try again later." };
      }

      return { error: error.message };
    }

    // Check if user was created successfully
    if (data.user && !data.user.email_confirmed_at) {
      return {
        success: true,
        message:
          "Account created successfully! Please check your email to confirm your account.",
        needsConfirmation: true,
      };
    }

    return { success: true };
  } catch (error) {
    console.error("Unexpected error during signup:", error);
    return { error: "An unexpected error occurred. Please try again." };
  }
}
