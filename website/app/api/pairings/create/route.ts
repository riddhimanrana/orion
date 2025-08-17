import { createClient } from "@supabase/supabase-js";
import { NextResponse } from "next/server";
import crypto from "crypto";

// Helper to generate a random 6-digit code
const generateCode = () =>
  Math.floor(100000 + Math.random() * 900000).toString();

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

  const { device_id } = await request.json();

  if (!device_id) {
    return new NextResponse(
      JSON.stringify({ error: "device_id is required" }),
      {
        status: 400,
        headers: { "Content-Type": "application/json" },
      },
    );
  }

  // Invalidate any old, unused codes for this device
  const { error: updateError } = await supabase
    .from("device_pairing_codes")
    .update({ used: true })
    .eq("device_id", device_id)
    .eq("used", false);

  if (updateError) {
    console.error("Error invalidating old pairing codes:", updateError);
    // Non-fatal, so we continue
  }

  // Generate a new code
  const code = generateCode();
  const salt = crypto.randomBytes(16).toString("hex");
  const hashed_code = await hashWithSalt(code, salt);
  const expires_at = new Date(Date.now() + 5 * 60 * 1000).toISOString(); // 5 minutes from now

  const { error } = await supabase.from("device_pairing_codes").insert({
    device_id,
    hashed_code,
    salt,
    expires_at,
  });

  if (error) {
    console.error("Error creating pairing code:", error);
    return new NextResponse(JSON.stringify({ error: error.message }), {
      status: 500,
      headers: { "Content-Type": "application/json" },
    });
  }

  return NextResponse.json({ code: code, expires_at: expires_at });
}
