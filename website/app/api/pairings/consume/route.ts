import { createClient } from "@supabase/supabase-js";
import { NextResponse } from "next/server";
import crypto from "crypto";

// Helper to hash the code
const hashWithSalt = (code: string, salt: string): Promise<string> => {
  return new Promise((resolve, reject) => {
    crypto.pbkdf2(code, salt, 100000, 64, "sha512", (err, derivedKey) => {
      if (err) reject(err);
      resolve(derivedKey.toString("hex"));
    });
  });
};

export async function POST(request: Request) {
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
    data: { user: consumerUser },
    error: getUserError,
  } = await supabase.auth.getUser();

  if (getUserError || !consumerUser) {
    console.error("Error getting user for token:", getUserError);
    return new NextResponse(
      JSON.stringify({ error: "Unauthorized: Invalid token" }),
      {
        status: 401,
        headers: { "Content-Type": "application/json" },
      },
    );
  }

  const { code, device_id: consumer_device_id } = await request.json();

  if (!code || !consumer_device_id) {
    return new NextResponse(
      JSON.stringify({ error: "code and device_id are required" }),
      {
        status: 400,
        headers: { "Content-Type": "application/json" },
      },
    );
  }

  // Verify consumer owns the device they claim
  const { data: consumerDeviceData, error: consumerDeviceError } =
    await supabase
      .from("devices")
      .select("id, type")
      .eq("id", consumer_device_id)
      .eq("user_id", consumerUser.id)
      .single();

  if (consumerDeviceError || !consumerDeviceData) {
    return new NextResponse(
      JSON.stringify({ error: "Consumer device not found or access denied" }),
      {
        status: 403,
        headers: { "Content-Type": "application/json" },
      },
    );
  }

  // Fetch all valid (unexpired, unused) pairing codes
  const { data: codes, error: codesError } = await supabase
    .from("device_pairing_codes")
    .select("*")
    .eq("used", false)
    .gt("expires_at", new Date().toISOString());

  if (codesError) {
    console.error("Error fetching pairing codes:", codesError);
    return new NextResponse(
      JSON.stringify({ error: "Error fetching pairing codes" }),
      { status: 500 },
    );
  }

  let pairingCodeRecord = null;
  for (const record of codes) {
    const hashedCode = await hashWithSalt(code, record.salt);
    if (hashedCode === record.hashed_code) {
      pairingCodeRecord = record;
      break;
    }
  }

  if (!pairingCodeRecord) {
    return new NextResponse(
      JSON.stringify({ error: "Invalid or expired code" }),
      {
        status: 404,
        headers: { "Content-Type": "application/json" },
      },
    );
  }

  // Found the code, now verify the creator device and user
  const creator_device_id = pairingCodeRecord.device_id;
  const { data: creatorDeviceData, error: creatorDeviceError } = await supabase
    .from("devices")
    .select("user_id, type")
    .eq("id", creator_device_id)
    .single();

  if (creatorDeviceError || !creatorDeviceData) {
    return new NextResponse(
      JSON.stringify({ error: "Creator device not found" }),
      { status: 500 },
    );
  }

  // Check if both devices belong to the same user
  if (creatorDeviceData.user_id !== consumerUser.id) {
    return new NextResponse(
      JSON.stringify({ error: "Devices must belong to the same user" }),
      {
        status: 403,
        headers: { "Content-Type": "application/json" },
      },
    );
  }

  // Ensure one is 'ios' and the other is 'mac'
  const mobileDevice =
    creatorDeviceData.type === "ios" ? creatorDeviceData : consumerDeviceData;
  const serverDevice =
    creatorDeviceData.type === "mac" ? creatorDeviceData : consumerDeviceData;
  const mobile_device_id =
    creatorDeviceData.type === "ios" ? creator_device_id : consumer_device_id;
  const server_device_id =
    creatorDeviceData.type === "mac" ? creator_device_id : consumer_device_id;

  if (mobileDevice.type !== "ios" || serverDevice.type !== "mac") {
    return new NextResponse(
      JSON.stringify({
        error: "Pairing must be between an iOS and a macOS device",
      }),
      {
        status: 400,
        headers: { "Content-Type": "application/json" },
      },
    );
  }

  // Check if an active pair already exists
  const { data: existingPair, error: existingPairError } = await supabase
    .from("device_pairs")
    .select(
      "*, mobile_device:devices!mobile_device_id(*), server_device:devices!server_device_id(*)",
    )
    .eq("mobile_device_id", mobile_device_id)
    .eq("server_device_id", server_device_id)
    .eq("status", "active")
    .maybeSingle();

  if (existingPairError) {
    console.error("Error checking for existing pair:", existingPairError);
    // Decide if you want to proceed or return an error
  }

  if (existingPair) {
    console.log("Returning existing active pair:", existingPair.id);
    return NextResponse.json(existingPair);
  }

  // Create the device pair
  const { data: pairData, error: pairError } = await supabase
    .from("device_pairs")
    .insert({
      user_id: consumerUser.id,
      mobile_device_id: mobile_device_id,
      server_device_id: server_device_id,
    })
    .select(
      "*, mobile_device:devices!mobile_device_id(*), server_device:devices!server_device_id(*)",
    )
    .single();

  if (pairError) {
    console.error("Error creating device pair:", pairError);
    // Check for unique constraint violation
    if (pairError.code === "23505") {
      // unique_violation
      return new NextResponse(
        JSON.stringify({ error: "A pair for these devices already exists." }),
        { status: 409 },
      ); // 409 Conflict
    }
    return new NextResponse(
      JSON.stringify({ error: "Could not create device pair" }),
      { status: 500 },
    );
  }

  // Mark the code as used
  const { error: updateCodeError } = await supabase
    .from("device_pairing_codes")
    .update({ used: true })
    .eq("id", pairingCodeRecord.id);

  if (updateCodeError) {
    // This is not ideal, the pair is created but the code is not marked as used.
    // In a real app, this would need a transaction.
    console.error(
      "CRITICAL: Failed to mark pairing code as used:",
      updateCodeError,
    );
  }

  return NextResponse.json(pairData);
}
