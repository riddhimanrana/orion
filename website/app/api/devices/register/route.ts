import { createClient } from "@supabase/supabase-js";
import { NextResponse } from "next/server";
import { trackApiRoute } from "@/utils/usage/track-api-route";

export async function POST(request: Request) {
  return trackApiRoute(request, { action: "devices.register" }, async (usage) => {
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

    // Create a new Supabase client with the user's token
    const supabase = createClient(
      process.env.NEXT_PUBLIC_SUPABASE_URL!,
      (process.env.NEXT_PUBLIC_SUPABASE_PUBLISHABLE_KEY ?? process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY)!,
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

    usage.setUserId(user.id);
    console.log("Register Device API: User authenticated:", user.id);

    const { type, name } = await request.json();

    if (!type || !name || !["ios", "mac"].includes(type)) {
      return new NextResponse(
        JSON.stringify({ error: "Invalid request body" }),
        {
          status: 400,
          headers: { "Content-Type": "application/json" },
        },
      );
    }

    usage.addMetadata({ deviceType: type });

    const { data, error } = await supabase
      .from("devices")
      .insert({
        user_id: user.id,
        type,
        name,
        last_seen: new Date().toISOString(),
      })
      .select("id")
      .single();

    if (error) {
      console.error("Error registering device:", error);
      return new NextResponse(JSON.stringify({ error: error.message }), {
        status: 500,
        headers: { "Content-Type": "application/json" },
      });
    }

    usage.addMetadata({ deviceId: data.id });
    return NextResponse.json({ device_id: data.id });
  });
}
