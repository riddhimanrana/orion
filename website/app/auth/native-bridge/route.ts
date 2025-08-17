import { createClient } from "@/utils/supabase/server";
import { NextRequest, NextResponse } from "next/server";

export async function GET(request: NextRequest) {
  const { searchParams, origin } = new URL(request.url);
  const finalRedirectTo = searchParams.get("redirectTo");

  if (!finalRedirectTo || !finalRedirectTo.startsWith("orion://")) {
    return NextResponse.redirect(
      `${origin}/auth/auth-code-error?error=invalid_request`,
    );
  }

  const supabase = await createClient();
  const { data, error } = await supabase.auth.getSession();

  if (error || !data.session) {
    // Not logged in, send them to the login page, but keep the mobile redirect info
    const loginUrl = new URL("/login", origin);
    loginUrl.searchParams.set("redirectTo", finalRedirectTo);
    return NextResponse.redirect(loginUrl);
  }

  // User is logged in, construct the final callback URL with tokens
  const callbackUrl = new URL(finalRedirectTo);

  // Add tokens to both hash and query params for maximum compatibility
  const tokenParams = `access_token=${encodeURIComponent(data.session.access_token)}&refresh_token=${encodeURIComponent(data.session.refresh_token)}&expires_in=${data.session.expires_in}&token_type=bearer`;

  // Set the hash (fragment) - this is the primary method
  callbackUrl.hash = tokenParams;

  // Also add as query parameters as backup (for apps that might not handle fragments well)
  callbackUrl.searchParams.set("access_token", data.session.access_token);
  callbackUrl.searchParams.set("refresh_token", data.session.refresh_token);
  callbackUrl.searchParams.set(
    "expires_in",
    data.session.expires_in.toString(),
  );
  callbackUrl.searchParams.set("token_type", "bearer");

  console.log("Mobile bridge - Final redirect URL:", callbackUrl.toString());
  console.log(
    "Mobile bridge - Session access token (first 20 chars):",
    data.session.access_token.substring(0, 20),
  );

  // Create a response that redirects to the mobile app and then closes the window
  const response = NextResponse.redirect(callbackUrl);

  // Add headers to indicate this should close the window
  response.headers.set("X-Close-Window", "true");

  return response;
}
