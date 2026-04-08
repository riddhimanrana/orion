import { createClient } from "@supabase/supabase-js";

type JsonObject = Record<string, unknown>;

export interface ApiUsageOptions {
  /**
   * Stable, dot-delimited name for grouping in analytics.
   * Example: "devices.register" or "pairings.consume".
   */
  action: string;
}

export interface ApiUsageTracker {
  setUserId: (userId: string) => void;
  addMetadata: (partial: JsonObject) => void;
  setMetadata: (metadata: JsonObject) => void;
}

let cachedAdminClient: ReturnType<typeof createClient> | null = null;

function getSupabaseAdminClient() {
  if (cachedAdminClient) return cachedAdminClient;

  const url = process.env.NEXT_PUBLIC_SUPABASE_URL;
  const serviceRoleKey = process.env.SUPABASE_SERVICE_ROLE_KEY;
  if (!url || !serviceRoleKey) return null;

  cachedAdminClient = createClient(url, serviceRoleKey, {
    auth: {
      autoRefreshToken: false,
      persistSession: false,
    },
  });
  return cachedAdminClient;
}

function getHeader(headers: Headers, key: string): string | null {
  // Headers are case-insensitive, but normalize anyway.
  return headers.get(key) ?? headers.get(key.toLowerCase());
}

function extractClientIp(headers: Headers): string | null {
  const xForwardedFor = getHeader(headers, "x-forwarded-for");
  if (xForwardedFor) {
    const first = xForwardedFor.split(",")[0]?.trim();
    if (first) return first;
  }

  const candidates = [
    "x-real-ip",
    "cf-connecting-ip",
    "x-client-ip",
    "x-vercel-forwarded-for",
  ];

  for (const key of candidates) {
    const val = getHeader(headers, key);
    if (val) return val.trim();
  }

  return null;
}

async function writeApiUsageEvent(event: {
  requestId: string;
  action: string;
  method: string;
  path: string;
  statusCode: number;
  durationMs: number;
  userId: string | null;
  ip: string | null;
  userAgent: string | null;
  referer: string | null;
  metadata: JsonObject;
}) {
  const supabase = getSupabaseAdminClient();
  if (!supabase) return;

  try {
    await supabase.from("api_usage_events").insert({
      request_id: event.requestId,
      user_id: event.userId,
      action: event.action,
      method: event.method,
      path: event.path,
      status_code: event.statusCode,
      duration_ms: event.durationMs,
      ip: event.ip,
      user_agent: event.userAgent,
      referer: event.referer,
      metadata: event.metadata,
    });
  } catch (err) {
    // Non-fatal: usage logging must never break API functionality.
    console.error("Failed to write api_usage_events row:", err);
  }
}

export async function trackApiRoute(
  request: Request,
  options: ApiUsageOptions,
  handler: (usage: ApiUsageTracker) => Promise<Response>,
): Promise<Response> {
  const startMs = Date.now();
  const requestId = globalThis.crypto?.randomUUID
    ? globalThis.crypto.randomUUID()
    : `${Date.now()}-${Math.random().toString(16).slice(2)}`;

  const url = new URL(request.url);
  const path = url.pathname;
  const method = request.method;

  const baseMetadata: JsonObject = {
    hasAuthHeader: Boolean(getHeader(request.headers, "authorization")),
    contentLength: (() => {
      const raw = getHeader(request.headers, "content-length");
      if (!raw) return null;
      const parsed = Number(raw);
      return Number.isFinite(parsed) ? parsed : null;
    })(),
  };

  const state = {
    userId: null as string | null,
    metadata: { ...baseMetadata } as JsonObject,
  };

  const tracker: ApiUsageTracker = {
    setUserId: (userId: string) => {
      state.userId = userId;
    },
    addMetadata: (partial: JsonObject) => {
      state.metadata = { ...state.metadata, ...partial };
    },
    setMetadata: (metadata: JsonObject) => {
      state.metadata = { ...metadata };
    },
  };

  let response: Response | null = null;
  let thrown: unknown = null;
  try {
    response = await handler(tracker);
    return response;
  } catch (err) {
    thrown = err;
    throw err;
  } finally {
    const durationMs = Math.max(0, Date.now() - startMs);

    if (thrown) {
      tracker.addMetadata({
        handlerErrorName: thrown instanceof Error ? thrown.name : "UnknownError",
      });
    }

    // Best-effort logging.
    await writeApiUsageEvent({
      requestId,
      action: options.action,
      method,
      path,
      statusCode: response?.status ?? 500,
      durationMs,
      userId: state.userId,
      ip: extractClientIp(request.headers),
      userAgent: getHeader(request.headers, "user-agent"),
      referer: getHeader(request.headers, "referer"),
      metadata: state.metadata,
    });
  }
}
