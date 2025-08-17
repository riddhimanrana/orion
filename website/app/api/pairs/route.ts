import { createClient } from "@supabase/supabase-js";
import { NextResponse } from "next/server";

export async function GET(request: Request) {
  const authHeader = request.headers.get("Authorization");

  if (!authHeader || !authHeader.startsWith("Bearer ")) {
    return new NextResponse(
      JSON.stringify({ error: "Unauthorized: Missing or invalid token" }),
      {
        status: 401,
        headers: { "Content-Type": "application/json" },
      },
    );
  }

  const token = authHeader.substring(7);

  const supabase = createClient(
    process.env.NEXT_PUBLIC_SUPABASE_URL!,
    process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY!,
    {
      global: { headers: { Authorization: `Bearer ${token}` } },
    },
  );

  const {
    data: { user },
    error: getUserError,
  } = await supabase.auth.getUser();

  if (getUserError || !user) {
    console.error("Error getting user for token:", getUserError);
    return new NextResponse(
      JSON.stringify({ error: "Unauthorized: Invalid token" }),
      {
        status: 401,
        headers: { "Content-Type": "application/json" },
      },
    );
  }

  console.log("Fetch Pairs API: User authenticated:", user.id);

  const { data, error } = await supabase
    .from("device_pairs")
    .select(
      `
      id,
      status,
      created_at,
      revoked_at,
      mobile_device:devices!mobile_device_id(*),
      server_device:devices!server_device_id(*)
    `,
    )
    .eq("user_id", user.id)
    .eq("status", "active");

  if (error) {
    console.error("Error fetching pairs:", error);
    return new NextResponse(JSON.stringify({ error: error.message }), {
      status: 500,
    });
  }

  return NextResponse.json(data);
}
