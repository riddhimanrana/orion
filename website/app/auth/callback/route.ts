import { createClient } from "@/utils/supabase/server";
import { NextRequest, NextResponse } from "next/server";

export async function GET(request: NextRequest) {
  const { searchParams, origin } = new URL(request.url);
  const code = searchParams.get("code");
  const error = searchParams.get("error");
  const errorCode = searchParams.get("error_code");
  const errorDescription = searchParams.get("error_description");
  const type = searchParams.get("type");
  const redirectTo = searchParams.get("redirectTo");
  const next = redirectTo ?? searchParams.get("next") ?? "/dashboard";

  // Handle errors by redirecting with error parameters
  if (error) {
    const errorParams = new URLSearchParams();
    if (error) errorParams.append("error", error);
    if (errorCode) errorParams.append("error_code", errorCode);
    if (errorDescription)
      errorParams.append("error_description", errorDescription);
    
    // Preserve redirectTo for mobile signup error handling
    if (redirectTo) errorParams.append("redirectTo", redirectTo);

    // For password reset errors, redirect to invalid reset page
    if (type === "recovery") {
      return NextResponse.redirect(
        `${origin}/reset-password/invalid?${errorParams.toString()}`,
      );
    }

    // For other auth errors, redirect to auth error page
    return NextResponse.redirect(
      `${origin}/auth/auth-code-error?${errorParams.toString()}`,
    );
  }

  if (!code) {
    return NextResponse.redirect(`${origin}/auth/auth-code-error`);
  }

  // Handle password reset flow - DO NOT auto-login
  if (type === "recovery") {
    // For password reset, redirect to the reset form with the code as token
    // The reset page will handle exchangeCodeForSession
    return NextResponse.redirect(
      `${origin}/reset-password/${code}?type=recovery`,
    );
  }

  // Handle email change confirmation flow
  if (type === "email_change") {
    // For email changes, we need to verify the token and redirect to confirmation page
    const supabase = await createClient();

    try {
      const { data, error: sessionError } =
        await supabase.auth.exchangeCodeForSession(code);

      if (sessionError) {
        console.error("Error during email change confirmation:", sessionError);
        return NextResponse.redirect(
          `${origin}/account/change-email-confirm?error=confirmation_failed`,
        );
      }

      // Check if this is an email change by looking at the user's email change status
      if (data?.user) {
        // Redirect to confirmation page with success
        const email = encodeURIComponent(data.user.email || "");
        return NextResponse.redirect(
          `${origin}/account/change-email-confirm?success=email_confirmed&email=${email}`,
        );
      }
    } catch (error) {
      console.error("Unexpected error during email change:", error);
      return NextResponse.redirect(
        `${origin}/account/change-email-confirm?error=unexpected_error`,
      );
    }
  }

  // Handle signup confirmation flow
  if (type === "signup") {
    // Check if this is a mobile redirect opened on desktop first
    const isMobileRedirect = next && next.startsWith("orionauth://");
    const userAgent = request.headers.get("user-agent") || "";
    const isMobileDevice = /Android|webOS|iPhone|iPad|iPod|BlackBerry|IEMobile|Opera Mini/i.test(userAgent);
    
    if (isMobileRedirect && !isMobileDevice) {
      // For mobile signup opened on desktop, show success without session exchange
      // This is a successful confirmation, just for the wrong device
      console.log("Mobile signup confirmed on desktop - showing success message");
      return NextResponse.redirect(
        `${origin}/auth/confirm?success=mobile_signup_confirmed&redirectTo=${encodeURIComponent(next)}`,
      );
    }

    // For mobile device or regular web signup, proceed with normal flow
    const supabase = await createClient();

    try {
      const { data, error: sessionError } =
        await supabase.auth.exchangeCodeForSession(code);

      if (sessionError) {
        console.error("Error during signup confirmation:", sessionError);
        
        // For mobile signups, provide specific guidance instead of generic errors
        if (isMobileRedirect) {
          console.log("Mobile signup session error - likely already confirmed or expired");
          return NextResponse.redirect(
            `${origin}/auth/confirm?success=mobile_signup_confirmed&note=already_confirmed&redirectTo=${encodeURIComponent(next)}`,
          );
        }
        
        return NextResponse.redirect(
          `${origin}/auth/confirm?error=confirmation_failed`,
        );
      }

      if (data?.user) {
        // Redirect to success confirmation page
        const email = encodeURIComponent(data.user.email || "");
        return NextResponse.redirect(
          `${origin}/auth/confirm?success=email_confirmed&email=${email}&redirectTo=${encodeURIComponent(next)}`,
        );
      }
    } catch (error) {
      console.error("Unexpected error during signup confirmation:", error);
      
      // Even for unexpected errors with mobile signups, show success since the account is likely confirmed
      if (isMobileRedirect) {
        console.log("Mobile signup unexpected error - treating as confirmed");
        return NextResponse.redirect(
          `${origin}/auth/confirm?success=mobile_signup_confirmed&note=session_error&redirectTo=${encodeURIComponent(next)}`,
        );
      }
      
      return NextResponse.redirect(
        `${origin}/auth/confirm?error=unexpected_error`,
      );
    }
  }

  // Handle regular authentication flow (login/signup) - if no specific type is set, assume it's email confirmation
  const supabase = await createClient();
  const { data, error: sessionError } =
    await supabase.auth.exchangeCodeForSession(code);

  if (sessionError) {
    console.error("Error exchanging code for session:", sessionError);
    return NextResponse.redirect(`${origin}/auth/auth-code-error`);
  }

  // Verify session was created successfully
  if (!data.session || !data.user) {
    console.error("Session or user not created after code exchange");
    return NextResponse.redirect(`${origin}/auth/auth-code-error`);
  }

  // Check if this is likely an email confirmation (new user with recent sign up)
  const isLikelyEmailConfirmation = data.user.email_confirmed_at && 
    new Date(data.user.email_confirmed_at).getTime() > Date.now() - 60000; // Confirmed in last minute

  if (isLikelyEmailConfirmation) {
    // Redirect to confirmation success page for email confirmations
    const email = encodeURIComponent(data.user.email || "");
    return NextResponse.redirect(
      `${origin}/auth/confirm?success=email_confirmed&email=${email}&redirectTo=${encodeURIComponent(next)}`,
    );
  }

  // Double-check by getting the current session
  const {
    data: { session: verifiedSession },
    error: sessionCheckError,
  } = await supabase.auth.getSession();

  if (sessionCheckError || !verifiedSession) {
    console.error("Session verification failed:", sessionCheckError);
    return NextResponse.redirect(`${origin}/auth/auth-code-error`);
  }

  console.log("Authentication successful for user:", data.user.email);

  // If a mobile redirect is specified, go to the bridge
  if (redirectTo && redirectTo.startsWith("orionauth://")) {
    const bridgeURL = new URL("/auth/mobile-bridge", origin);
    bridgeURL.searchParams.set("redirectTo", redirectTo);
    return NextResponse.redirect(bridgeURL);
  }

  // For regular auth, redirect to intended destination with cache busting
  const forwardedHost = request.headers.get("x-forwarded-host");
  const isLocalEnv = process.env.NODE_ENV === "development";

  // Add timestamp to force page refresh and ensure user context is updated
  const redirectUrl = new URL(next, origin);
  redirectUrl.searchParams.set("t", Date.now().toString());

  // Create redirect response with proper headers
  const response = isLocalEnv
    ? NextResponse.redirect(redirectUrl.toString())
    : forwardedHost
      ? NextResponse.redirect(
          `https://${forwardedHost}${redirectUrl.pathname}${redirectUrl.search}`,
        )
      : NextResponse.redirect(redirectUrl.toString());

  // Add headers to ensure fresh page load
  response.headers.set("Cache-Control", "no-cache, no-store, must-revalidate");
  response.headers.set("Pragma", "no-cache");
  response.headers.set("Expires", "0");

  return response;
}
