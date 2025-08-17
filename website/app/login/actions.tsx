"use server";

import { createClient } from "@/utils/supabase/server";
import type {
  SignInFormData,
  OAuthAuthResponse,
  EmailSignInResponse,
} from "@/lib/auth-schemas";

export async function signInWithGoogle(
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
    console.error("Error signing in with Google:", error);
    return { error: error.message };
  }

  if (data.url) {
    return { success: true, url: data.url };
  }

  return { error: "Failed to initiate Google sign in" };
}

export async function signInWithGitHub(
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
    console.error("Error signing in with GitHub:", error);
    return { error: error.message };
  }

  if (data.url) {
    return { success: true, url: data.url };
  }

  return { error: "Failed to initiate GitHub sign in" };
}

export async function signInWithApple(
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
    console.error("Error signing in with Apple:", error);
    return { error: error.message };
  }

  if (data.url) {
    return { success: true, url: data.url };
  }

  return { error: "Failed to initiate Apple sign in" };
}

export async function signInWithEmail(
  formData: SignInFormData,
  redirectTo?: string,
): Promise<EmailSignInResponse> {
  const supabase = await createClient();

  const { email, password } = formData;

  const { data, error } = await supabase.auth.signInWithPassword({
    email,
    password,
  });

  if (error) {
    console.error("Error signing in with email:", error);

    // Handle specific error cases
    if (
      error.message.includes("Invalid login credentials") ||
      error.message.includes("invalid credentials") ||
      error.message.includes("incorrect email or password")
    ) {
      return {
        error:
          "Invalid email or password. Please check your credentials and try again.",
      };
    } else if (
      error.message.includes("Email not confirmed") ||
      error.message.includes("signup_disabled")
    ) {
      return {
        error:
          "Please confirm your email address before signing in. Check your inbox for a confirmation link.",
      };
    } else if (error.message.includes("Too many requests")) {
      return {
        error:
          "Too many login attempts. Please wait a moment before trying again.",
      };
    } else if (error.message.includes("User not found")) {
      return {
        error:
          "No account found with this email address. Please check your email or sign up for a new account.",
      };
    } else if (error.message.includes("rate limit")) {
      return {
        error: "Too many attempts. Please try again later.",
      };
    }

    return { error: error.message };
  }

  // Check if sign in was successful
  if (data.user && data.session) {
    // Verify session is properly established by getting current session
    const { data: sessionData, error: sessionError } =
      await supabase.auth.getSession();

    if (sessionError) {
      console.error("Session verification failed:", sessionError);
      return {
        error:
          "Authentication succeeded but session verification failed. Please try again.",
      };
    }

    if (!sessionData.session) {
      console.error("Session not established after sign in");
      return {
        error:
          "Authentication succeeded but session not established. Please try again.",
      };
    }

    console.log("Authentication successful for user:", data.user.email);

    // If a mobile redirect is specified, return the bridge URL
    if (redirectTo && redirectTo.startsWith("orion://")) {
      const bridgeURL = new URL(
        "/auth/native-bridge",
        process.env.NEXT_PUBLIC_SITE_URL,
      );
      bridgeURL.searchParams.set("redirectTo", redirectTo);
      return {
        success: true,
        redirectTo: bridgeURL.toString(),
      };
    }

    // For regular web flow, return the dashboard URL
    return {
      success: true,
      redirectTo: "/dashboard",
    };
  }

  return { error: "Sign in failed. Please try again." };
}

export async function getMobileSession() {
  const supabase = await createClient();
  const { data, error } = await supabase.auth.getSession();

  if (error || !data.session) {
    return { error: "Failed to get session" };
  }

  return {
    success: true,
    accessToken: data.session.access_token,
    refreshToken: data.session.refresh_token,
    expiresIn: data.session.expires_in,
  };
}
