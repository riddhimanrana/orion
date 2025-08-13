import { createServerClient } from "@supabase/ssr";
import { NextResponse, type NextRequest } from "next/server";

/**
 * Middleware for handling authentication and route protection
 *
 * Updated Rules:
 * - Not logged in: can access public, auth, and any other route EXCEPT protected routes
 * - Logged in: can access protected and any other route EXCEPT public and auth routes
 */
export async function updateSession(request: NextRequest) {
  let supabaseResponse = NextResponse.next({
    request,
  });

  const supabase = createServerClient(
    process.env.NEXT_PUBLIC_SUPABASE_URL!,
    process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY!,
    {
      cookies: {
        getAll() {
          return request.cookies.getAll();
        },
        setAll(cookiesToSet) {
          cookiesToSet.forEach(({ name, value }) =>
            request.cookies.set(name, value),
          );
          supabaseResponse = NextResponse.next({
            request,
          });
          cookiesToSet.forEach(({ name, value, options }) =>
            supabaseResponse.cookies.set(name, value, options),
          );
        },
      },
    },
  );

  let user = null;

  try {
    const { data: sessionData, error: sessionError } =
      await supabase.auth.getSession();

    if (!sessionError && sessionData.session) {
      const { data: userData, error: getUserError } =
        await supabase.auth.getUser();

      if (getUserError) {
        import { createServerClient } from "@supabase/ssr";
import { NextResponse, type NextRequest } from "next/server";

export async function updateSession(request: NextRequest) {
  let supabaseResponse = NextResponse.next({
    request,
  });

  const supabase = createServerClient(
    process.env.NEXT_PUBLIC_SUPABASE_URL!,
    process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY!,
    {
      cookies: {
        getAll() {
          return request.cookies.getAll();
        },
        setAll(cookiesToSet) {
          cookiesToSet.forEach(({ name, value }) =>
            request.cookies.set(name, value),
          );
          supabaseResponse = NextResponse.next({
            request,
          });
          cookiesToSet.forEach(({ name, value, options }) =>
            supabaseResponse.cookies.set(name, value, options),
          );
        },
      },
    },
  );

  let user = null;

  try {
    const { data: sessionData, error: sessionError } =
      await supabase.auth.getSession();

    if (!sessionError && sessionData.session) {
      const { data: userData, error: getUserError } =
        await supabase.auth.getUser();

      if (getUserError) {
        if (
          getUserError.message?.includes(
            "User from sub claim in JWT does not exist",
          ) ||
          getUserError.code === "user_not_found"
        ) {
          await supabase.auth.signOut();
          user = null;
        } else {
          console.error("Get user error in middleware:", getUserError);
          user = null;
        }
      } else {
        user = userData.user;
      }
    } else if (
      sessionError &&
      !sessionError.message.includes("session_not_found")
    ) {
      console.error("Session error in middleware:", sessionError);
    }
  } catch (error) {
    console.error("Unexpected error in middleware auth check:", error);
  }

  const url = request.nextUrl.clone();
  let pathname = decodeURIComponent(url.pathname)
    .toLowerCase()
    .replace(/\/+$/, "")
    .split("#")[0]
    .split("?")[0];

  if (pathname === "") {
    pathname = "/";
  }

  const publicRoutes = ["/", "/pricing", "/features", "/get-started"];

  const authRoutes = ["/login", "/signup"];
  const protectedRoutes = ["/dashboard", "/account", "/activity"];

  const isExactMatch = (path: string, routes: string[]) => {
    return routes.includes(path);
  };

  const isProtectedRoute = (path: string) => {
    return protectedRoutes.some(
      (route) => path === route || path.startsWith(route + "/"),
    );
  };

  // Always allow auth callback and reset password routes
  if (pathname.startsWith("/auth/") || pathname.startsWith("/reset-password")) {
    return supabaseResponse;
  }

  // If user is logged in
  if (user) {
    const redirectTo = request.nextUrl.searchParams.get("redirectTo");

    // If a logged-in user lands on an auth/public page with a mobile redirect,
    // send them to the mobile auth bridge to transfer the session.
    if (redirectTo && redirectTo.startsWith("orionauth://")) {
      const bridgeURL = new URL("/auth/mobile-bridge", request.url);
      bridgeURL.searchParams.set("redirectTo", redirectTo);
      return NextResponse.redirect(bridgeURL);
    }

    // Otherwise, for regular web flow, redirect logged-in users from public/auth pages to the dashboard.
    if (
      isExactMatch(pathname, publicRoutes) ||
      isExactMatch(pathname, authRoutes)
    ) {
      const redirectUrl = new URL("/dashboard", url.origin);
      return NextResponse.redirect(redirectUrl);
    }

    // Allow access to protected and any other route
    return supabaseResponse;
  }

  // If user is not logged in
  if (!user) {
    // Block access to protected routes
    if (isProtectedRoute(pathname)) {
      const redirectUrl = new URL("/login", url.origin);
      redirectUrl.searchParams.set("redirectTo", request.nextUrl.pathname);
      return NextResponse.redirect(redirectUrl);
    }
    // Allow access to public, auth, and any other route
    return supabaseResponse;
  }

  return supabaseResponse;
}
          await supabase.auth.signOut();
          user = null;
        } else {
          console.error("Get user error in middleware:", getUserError);
          user = null;
        }
      } else {
        user = userData.user;
      }
    } else if (
      sessionError &&
      !sessionError.message.includes("session_not_found")
    ) {
      console.error("Session error in middleware:", sessionError);
    }
  } catch (error) {
    console.error("Unexpected error in middleware auth check:", error);
  }

  const url = request.nextUrl.clone();
  let pathname = decodeURIComponent(url.pathname)
    .toLowerCase()
    .replace(/\/+$/, "")
    .split("#")[0]
    .split("?")[0];

  if (pathname === "") {
    pathname = "/";
  }

  const publicRoutes = ["/", "/pricing", "/features", "/get-started"];

  const authRoutes = ["/login", "/signup"];
  const protectedRoutes = ["/dashboard", "/account", "/activity"];

  const isExactMatch = (path: string, routes: string[]) => {
    return routes.includes(path);
  };

  const isProtectedRoute = (path: string) => {
    return protectedRoutes.some(
      (route) => path === route || path.startsWith(route + "/"),
    );
  };

  // Always allow auth callback and reset password routes
  if (pathname.startsWith("/auth/") || pathname.startsWith("/reset-password")) {
    return supabaseResponse;
  }

  // If user is logged in
  if (user) {
    const redirectTo = request.nextUrl.searchParams.get("redirectTo");

    // If a logged-in user lands on an auth/public page with a mobile redirect,
    // send them to the mobile auth bridge to transfer the session.
    if (redirectTo && redirectTo.startsWith("orionauth://")) {
      const bridgeURL = new URL("/auth/mobile-bridge", request.url);
      bridgeURL.searchParams.set("redirectTo", redirectTo);
      return NextResponse.redirect(bridgeURL);
    }

    // Otherwise, for regular web flow, redirect logged-in users from public/auth pages to the dashboard.
    if (
      isExactMatch(pathname, publicRoutes) ||
      isExactMatch(pathname, authRoutes)
    ) {
      const redirectUrl = new URL("/dashboard", url.origin);
      return NextResponse.redirect(redirectUrl);
    }

    // Allow access to protected and any other route
    return supabaseResponse;
  }

  // If user is not logged in
  if (!user) {
    // Block access to protected routes
    if (isProtectedRoute(pathname)) {
      const redirectUrl = new URL("/login", url.origin);
      redirectUrl.searchParams.set("redirectTo", request.nextUrl.pathname);
      return NextResponse.redirect(redirectUrl);
    }
    // Allow access to public, auth, and any other route
    return supabaseResponse;
  }

  return supabaseResponse;
}
