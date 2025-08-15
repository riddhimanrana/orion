
import { createClient } from "@/utils/supabase/server";
import { NextResponse } from "next/server";
import jwt from "jsonwebtoken";

export async function POST(request: Request) {
  try {
    const supabase = await createClient();
    const {
      data: { user },
    } = await supabase.auth.getUser();

    if (!user) {
      return new NextResponse(JSON.stringify({ error: "Unauthorized" }), {
        status: 401,
        headers: { "Content-Type": "application/json" },
      });
    }

    const { deviceId } = await request.json();
    if (!deviceId) {
      return new NextResponse(
        JSON.stringify({ error: "deviceId is required" }),
        { status: 400, headers: { "Content-Type": "application/json" } },
      );
    }

    // Find the active pair for the user's device
    const { data: pair, error: pairError } = await supabase
      .from("device_pairs")
      .select("id")
      .or(`mobile_device_id.eq.${deviceId},server_device_id.eq.${deviceId}`)
      .eq("user_id", user.id)
      .eq("status", "active")
      .single();

    if (pairError || !pair) {
      console.error("Error finding active pair for device:", deviceId, pairError);
      return new NextResponse(
        JSON.stringify({ error: "No active pair found for this device." }),
        { status: 404, headers: { "Content-Type": "application/json" } },
      );
    }

    const jwtSecret = process.env.P2P_SIGNAL_JWT_SECRET;
    if (!jwtSecret) {
      console.error("P2P_SIGNAL_JWT_SECRET is not set in environment variables.");
      return new NextResponse(
        JSON.stringify({ error: "Server configuration error" }),
        { status: 500, headers: { "Content-Type": "application/json" } },
      );
    }

    // Create a JWT with a 5-minute expiry
    const token = jwt.sign(
      {
        deviceId,
        pairId: pair.id,
        userId: user.id,
      },
      jwtSecret,
      { expiresIn: "5m" },
    );

    return NextResponse.json({ token });
  } catch (error) {
    console.error("Error in /api/auth/webrtc-token:", error);
    return new NextResponse(
      JSON.stringify({ error: "An unexpected error occurred." }),
      { status: 500, headers: { "Content-Type": "application/json" } },
    );
  }
}
