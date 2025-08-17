import { createClient } from "@supabase/supabase-js";
import { NextResponse } from "next/server";
import jwt from "jsonwebtoken";

export async function POST(request: Request) {
  console.log("Received request for /api/auth/webrtc-token");

  const authHeader = request.headers.get("Authorization");

  if (!authHeader || !authHeader.startsWith("Bearer ")) {
    console.log("Auth Error: Missing or invalid Authorization header.");
    return new NextResponse(
      JSON.stringify({ error: "Unauthorized: Missing or invalid token" }),
      {
        status: 401,
        headers: { "Content-Type": "application/json" },
      },
    );
  }

  const token = authHeader.substring(7);

  // Create a Supabase client authenticated with the user's token
  const supabase = createClient(
    process.env.NEXT_PUBLIC_SUPABASE_URL!,
    process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY!,
    {
      global: { headers: { Authorization: `Bearer ${token}` } },
    },
  );

  // Validate the user token
  const {
    data: { user },
    error: getUserError,
  } = await supabase.auth.getUser();

  if (getUserError || !user) {
    console.error("Auth Error: Invalid user token.", getUserError?.message);
    return new NextResponse(
      JSON.stringify({ error: "Unauthorized: Invalid token" }),
      {
        status: 401,
        headers: { "Content-Type": "application/json" },
      },
    );
  }

  console.log(`Authenticated user ${user.id}`);

  try {
    const { deviceId } = await request.json();
    if (!deviceId) {
      console.log("Validation Error: deviceId is required.");
      return new NextResponse(
        JSON.stringify({ error: "deviceId is required" }),
        { status: 400, headers: { "Content-Type": "application/json" } },
      );
    }
    console.log(`Requesting token for deviceId: ${deviceId}`);

    // Find the active pair for the user's device
    // This query now uses the service_role key for elevated privilege, which is safer for backend queries.
    const supabaseAdmin = createClient(
      process.env.NEXT_PUBLIC_SUPABASE_URL!,
      process.env.SUPABASE_SERVICE_ROLE_KEY!,
    );
    const { data: pair, error: pairError } = await supabaseAdmin
      .from("device_pairs")
      .select("id")
      .or(`mobile_device_id.eq.${deviceId},server_device_id.eq.${deviceId}`)
      .eq("user_id", user.id)
      .eq("status", "active")
      .single();

    if (pairError || !pair) {
      console.error(
        `Pairing Error: No active pair found for device ${deviceId}.`,
        pairError,
      );
      return new NextResponse(
        JSON.stringify({ error: "No active pair found for this device." }),
        { status: 404, headers: { "Content-Type": "application/json" } },
      );
    }
    console.log(`Found active pairId: ${pair.id}`);

    const jwtSecret = process.env.P2P_SIGNAL_JWT_SECRET;
    if (!jwtSecret) {
      console.error("Config Error: P2P_SIGNAL_JWT_SECRET is not set.");
      return new NextResponse(
        JSON.stringify({ error: "Server configuration error" }),
        { status: 500, headers: { "Content-Type": "application/json" } },
      );
    }

    // Create a JWT with a 5-minute expiry for the signaling server
    const p2pToken = jwt.sign(
      {
        deviceId,
        pairId: pair.id,
        userId: user.id,
      },
      jwtSecret,
      { expiresIn: "5m" },
    );
    console.log("Successfully generated P2P signaling token.");

    return NextResponse.json({ token: p2pToken });
  } catch (error) {
    console.error("Unexpected Error in /api/auth/webrtc-token:", error);
    return new NextResponse(
      JSON.stringify({ error: "An unexpected error occurred." }),
      { status: 500, headers: { "Content-Type": "application/json" } },
    );
  }
}
