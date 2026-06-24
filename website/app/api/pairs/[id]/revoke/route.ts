import { createClient } from "@supabase/supabase-js";
import { NextResponse } from "next/server";
import { trackApiRoute } from "@/utils/usage/track-api-route";

export async function POST(
  request: Request,
  context: { params: Promise<{ id: string }> },
) {
  const { id } = await context.params;
  const pairId = id;

  return trackApiRoute(request, { action: "pairs.revoke" }, async (usage) => {
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
      return new NextResponse(JSON.stringify({ error: "Unauthorized" }), {
        status: 401,
        headers: { "Content-Type": "application/json" },
      });
    }

    usage.setUserId(user.id);

    if (!pairId) {
      return new NextResponse(
        JSON.stringify({ error: "Pair ID is required" }),
        {
          status: 400,
          headers: { "Content-Type": "application/json" },
        },
      );
    }

    usage.addMetadata({ pairId });

    // Ensure the pair belongs to the user
    const { data: pairData, error: pairError } = await supabase
      .from("device_pairs")
      .select("id")
      .eq("id", pairId)
      .eq("user_id", user.id)
      .single();

    if (pairError || !pairData) {
      console.error("Error fetching pair or access denied:", pairError);
      return new NextResponse(
        JSON.stringify({ error: "Pair not found or access denied" }),
        {
          status: 404,
          headers: { "Content-Type": "application/json" },
        },
      );
    }

    // Mark as revoked
    const { error: revokeError } = await supabase
      .from("device_pairs")
      .update({ status: "revoked", revoked_at: new Date().toISOString() })
      .eq("id", pairId);

    if (revokeError) {
      console.error("Error revoking pair:", revokeError);
      return new NextResponse(
        JSON.stringify({ error: "Failed to revoke pair" }),
        {
          status: 500,
          headers: { "Content-Type": "application/json" },
        },
      );
    }

    return NextResponse.json({ success: true });
  });
}
