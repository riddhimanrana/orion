import { createClient } from "@/utils/supabase/server";
import { NextRequest, NextResponse } from "next/server";

export async function GET(request: NextRequest) {
  const { searchParams, origin } = new URL(request.url);
  const code = searchParams.get("code");
  const token_hash = searchParams.get("token_hash");
  const type = searchParams.get("type");
  // const redirectTo = searchParams.get("redirectTo"); // Currently unused
  const error = searchParams.get("error");

  // Handle error cases first
  if (error) {
    return NextResponse.redirect(
      `${origin}/account/change-email-confirm?error=confirmation_failed&message=${encodeURIComponent(error)}`,
    );
  }

  // Validate required parameters - either code or token_hash should be present
  if (!code && !token_hash) {
    return NextResponse.redirect(
      `${origin}/account/change-email-confirm?error=invalid_link`,
    );
  }

  // For email changes, we'll be more lenient with type checking
  // since Supabase might send different type values or no type for different steps
  // We'll let Supabase handle the validation internally

  const supabase = await createClient();

  try {
    let data, error;

    if (code) {
      // Handle code-based confirmation (most common for email changes)
      const result = await supabase.auth.exchangeCodeForSession(code);
      data = result.data;
      error = result.error;
    } else if (token_hash) {
      // Handle token-based confirmation
      const result = await supabase.auth.verifyOtp({
        token_hash,
        type: (type as "email") || "email",
      });
      data = result.data;
      error = result.error;
    }

    if (error) {
      console.error("Email change confirmation error:", error);

      let errorParam = "confirmation_failed";
      if (error.message.includes("expired")) {
        errorParam = "link_expired";
      } else if (error.message.includes("invalid")) {
        errorParam = "invalid_token";
      } else if (error.message.includes("already")) {
        errorParam = "already_confirmed";
      }

      return NextResponse.redirect(
        `${origin}/account/change-email-confirm?error=${errorParam}&type=${type}`,
      );
    }

    // Success - determine the type of confirmation and redirect appropriately
    if (data?.user) {
      const userEmail = data.user.email || "";
      const encodedEmail = encodeURIComponent(userEmail);

      // For email changes, we'll show a success message
      // The confirmation page will handle displaying the appropriate next steps
      return NextResponse.redirect(
        `${origin}/account/change-email-confirm?success=email_confirmed&email=${encodedEmail}`,
      );
    } else {
      // No user data, but no error - show generic success
      return NextResponse.redirect(
        `${origin}/account/change-email-confirm?success=confirmation_processed`,
      );
    }
  } catch (error) {
    console.error("Unexpected error during email change confirmation:", error);
    return NextResponse.redirect(
      `${origin}/account/change-email-confirm?error=unexpected_error`,
    );
  }
}
