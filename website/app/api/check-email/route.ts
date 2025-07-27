import { createClient } from "@supabase/supabase-js";
import { createClient as createServerClient } from "@/utils/supabase/server";
import { NextRequest, NextResponse } from "next/server";

export async function POST(request: NextRequest) {
  try {
    // Parse request body
    const { email } = await request.json();

    if (!email) {
      return NextResponse.json({ error: "Email is required" }, { status: 400 });
    }

    // Validate email format
    const emailRegex = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;
    if (!emailRegex.test(email)) {
      return NextResponse.json(
        {
          available: false,
          error: "Invalid email format",
        },
        { status: 200 },
      );
    }

    // Normalize email
    const normalizedEmail = email.toLowerCase().trim();

    // Get current user to exclude from check
    const supabase = await createServerClient();
    const {
      data: { user: currentUser },
    } = await supabase.auth.getUser();

    if (!currentUser) {
      return NextResponse.json(
        { error: "User not authenticated" },
        { status: 401 },
      );
    }

    // Check if it's the same as current email
    if (currentUser.email?.toLowerCase() === normalizedEmail) {
      return NextResponse.json(
        {
          available: false,
          error: "This is already your current email address",
        },
        { status: 200 },
      );
    }

    // Create admin client with service role key
    const supabaseAdmin = createClient(
      process.env.NEXT_PUBLIC_SUPABASE_URL!,
      process.env.SUPABASE_SERVICE_ROLE_KEY!,
      {
        auth: {
          autoRefreshToken: false,
          persistSession: false,
        },
      },
    );

    // Check if email exists in auth.users
    const { data: existingUsers, error } =
      await supabaseAdmin.auth.admin.listUsers();

    if (error) {
      console.error("Error checking email availability:", error);
      return NextResponse.json(
        {
          available: null,
          error: "Unable to verify email availability. You can try proceeding.",
        },
        { status: 200 },
      );
    }

    // Check if any user (other than current user) has this email
    const emailExists = existingUsers.users.some(
      (user) =>
        user.email?.toLowerCase() === normalizedEmail &&
        user.id !== currentUser.id,
    );

    return NextResponse.json({
      available: !emailExists,
      error: emailExists
        ? "An account with this email address already exists"
        : null,
    });
  } catch (error) {
    console.error("Unexpected error in email availability check:", error);
    return NextResponse.json(
      {
        available: null,
        error: "Unable to verify email availability. You can try proceeding.",
      },
      { status: 200 },
    );
  }
}

// Handle CORS for preflight requests
export async function OPTIONS() {
  return new NextResponse(null, {
    status: 200,
    headers: {
      "Access-Control-Allow-Origin": "*",
      "Access-Control-Allow-Methods": "POST, OPTIONS",
      "Access-Control-Allow-Headers": "Content-Type, Authorization",
    },
  });
}
