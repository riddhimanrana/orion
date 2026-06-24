import { createClient } from "@supabase/supabase-js";
import { createClient as createServerClient } from "@/utils/supabase/server";
import { trackApiRoute } from "@/utils/usage/track-api-route";
import { NextResponse } from "next/server";

function clampInt(
  raw: string | null,
  { min, max, fallback }: { min: number; max: number; fallback: number },
): number {
  if (!raw) return fallback;
  const parsed = Number(raw);
  if (!Number.isFinite(parsed)) return fallback;
  const asInt = Math.floor(parsed);
  if (asInt < min) return min;
  if (asInt > max) return max;
  return asInt;
}

function toNumber(value: unknown): number {
  if (typeof value === "number") return value;
  if (typeof value === "string") {
    const parsed = Number(value);
    if (Number.isFinite(parsed)) return parsed;
  }
  return 0;
}

export interface UsageSummaryResponse {
  period: {
    timezone: "UTC";
    now: string;
    start: string;
    end: string;
    resetDate: string;
  };
  usage: {
    requestsToday: number;
    requestsThisMonth: number;
  };
  daily: Array<{
    day: string;
    requests: number;
  }>;
}

export async function GET(request: Request) {
  return trackApiRoute(request, { action: "usage.summary" }, async (usage) => {
    const url = new URL(request.url);
    const days = clampInt(url.searchParams.get("days"), {
      min: 1,
      max: 90,
      fallback: 30,
    });

    // Prefer explicit bearer token (useful for external clients); otherwise fall back
    // to cookie-based auth for the website.
    const authHeader = request.headers.get("Authorization");
    const hasBearer = !!authHeader && authHeader.startsWith("Bearer ");

    const supabase = hasBearer
      ? createClient(
          process.env.NEXT_PUBLIC_SUPABASE_URL!,
          (process.env.NEXT_PUBLIC_SUPABASE_PUBLISHABLE_KEY ?? process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY)!,
          {
            global: { headers: { Authorization: authHeader } },
          },
        )
      : await createServerClient();

    const {
      data: { user },
      error: getUserError,
    } = await supabase.auth.getUser();

    if (getUserError || !user) {
      return NextResponse.json(
        { error: "Unauthorized" },
        {
          status: 401,
          headers: { "Content-Type": "application/json" },
        },
      );
    }

    usage.setUserId(user.id);

    const now = new Date();
    const monthStart = new Date(
      Date.UTC(now.getUTCFullYear(), now.getUTCMonth(), 1, 0, 0, 0, 0),
    );
    const nextMonthStart = new Date(
      Date.UTC(now.getUTCFullYear(), now.getUTCMonth() + 1, 1, 0, 0, 0, 0),
    );

    const todayStart = new Date(
      Date.UTC(
        now.getUTCFullYear(),
        now.getUTCMonth(),
        now.getUTCDate(),
        0,
        0,
        0,
        0,
      ),
    );
    const tomorrowStart = new Date(todayStart);
    tomorrowStart.setUTCDate(tomorrowStart.getUTCDate() + 1);

    const dailyFrom = new Date(todayStart);
    dailyFrom.setUTCDate(dailyFrom.getUTCDate() - (days - 1));

    const [{ count: monthCount, error: monthError }, { count: todayCount, error: todayError }] =
      await Promise.all([
        supabase
          .from("api_usage_events")
          .select("id", { head: true, count: "exact" })
          .eq("user_id", user.id)
          .gte("created_at", monthStart.toISOString())
          .lt("created_at", nextMonthStart.toISOString()),
        supabase
          .from("api_usage_events")
          .select("id", { head: true, count: "exact" })
          .eq("user_id", user.id)
          .gte("created_at", todayStart.toISOString())
          .lt("created_at", tomorrowStart.toISOString()),
      ]);

    if (monthError || todayError) {
      console.error("Usage summary count error:", monthError ?? todayError);
      return NextResponse.json(
        { error: "Failed to compute usage summary" },
        {
          status: 500,
          headers: { "Content-Type": "application/json" },
        },
      );
    }

    const { data: dailyRows, error: dailyError } = await supabase
      .from("api_usage_daily")
      .select("day, requests")
      .eq("user_id", user.id)
      .gte("day", dailyFrom.toISOString())
      .lt("day", tomorrowStart.toISOString())
      .order("day", { ascending: true });

    if (dailyError) {
      console.error("Usage summary daily error:", dailyError);
      return NextResponse.json(
        { error: "Failed to load daily usage" },
        {
          status: 500,
          headers: { "Content-Type": "application/json" },
        },
      );
    }

    const response: UsageSummaryResponse = {
      period: {
        timezone: "UTC",
        now: now.toISOString(),
        start: monthStart.toISOString(),
        end: nextMonthStart.toISOString(),
        resetDate: nextMonthStart.toISOString(),
      },
      usage: {
        requestsToday: todayCount ?? 0,
        requestsThisMonth: monthCount ?? 0,
      },
      daily:
        dailyRows?.map((row: { day: string; requests: unknown }) => ({
          day: row.day,
          requests: toNumber(row.requests),
        })) ?? [],
    };

    usage.addMetadata({
      days,
      requestsToday: response.usage.requestsToday,
      requestsThisMonth: response.usage.requestsThisMonth,
    });

    return NextResponse.json(response);
  });
}
