"use client";

import { createContext, useContext, useEffect, useState } from "react";
import { useRouter, usePathname } from "next/navigation";
import { createClient } from "@/utils/supabase/client";
import { User, Session } from "@supabase/supabase-js";
import { toast } from "sonner";

interface UserContextType {
  user: User | null;
  session: Session | null;
  loading: boolean;
  signOut: () => Promise<void>;
  refreshUser: () => Promise<void>;
  setLoginRedirect: (url: string) => void;
}

const UserContext = createContext<UserContextType | undefined>(undefined);

export function UserProvider({ children }: { children: React.ReactNode }) {
  const [user, setUser] = useState<User | null>(null);
  const [session, setSession] = useState<Session | null>(null);
  const [loading, setLoading] = useState(true);
  const [pendingRedirect, setPendingRedirect] = useState<string | null>(null);
  const router = useRouter();
  const pathname = usePathname();
  const supabase = createClient();

  useEffect(() => {
    let isMounted = true;
    let timeoutId: NodeJS.Timeout;

    // Get initial session and set up auth listener
    const initializeAuth = async () => {
      try {
        const {
          data: { session: initialSession },
          error: sessionError,
        } = await supabase.auth.getSession();

        if (!isMounted) return;

        if (sessionError) {
          console.error("Error getting initial session:", sessionError);
          setSession(null);
          setUser(null);
          setLoading(false);
          return;
        }

        // If we have a session, verify the user still exists
        if (initialSession) {
          try {
            const { data: userData, error: userError } =
              await supabase.auth.getUser();

            if (userError) {
              // Handle deleted user with orphaned session
              if (
                userError.message?.includes(
                  "User from sub claim in JWT does not exist",
                ) ||
                userError.code === "user_not_found"
              ) {
                console.log("User was deleted, clearing orphaned session");
                await supabase.auth.signOut();
                setSession(null);
                setUser(null);
                setLoading(false);
                return;
              }
              throw userError;
            }

            setSession(initialSession);
            setUser(userData.user);
          } catch (error) {
            console.error("Error verifying user:", error);
            setSession(null);
            setUser(null);
          }
        } else {
          setSession(null);
          setUser(null);
        }

        setLoading(false);
      } catch (error) {
        if (!isMounted) return;
        console.error("Error initializing auth:", error);
        setSession(null);
        setUser(null);
        setLoading(false);
      }
    };

    initializeAuth();

    // Listen for auth changes with debouncing
    const {
      data: { subscription },
    } = supabase.auth.onAuthStateChange(async (event, session) => {
      console.log("Auth state changed:", event, session?.user?.email);

      if (!isMounted) return;

      // Clear any pending state updates
      if (timeoutId) {
        clearTimeout(timeoutId);
      }

      // Debounce rapid state changes
      timeoutId = setTimeout(async () => {
        if (!isMounted) return;

        // If we have a session, verify the user still exists
        if (session) {
          try {
            const { data: userData, error: userError } =
              await supabase.auth.getUser();

            if (userError) {
              // Handle deleted user with orphaned session
              if (
                userError.message?.includes(
                  "User from sub claim in JWT does not exist",
                ) ||
                userError.code === "user_not_found"
              ) {
                console.log(
                  "User was deleted during auth state change, clearing session",
                );
                await supabase.auth.signOut();
                setSession(null);
                setUser(null);
                setLoading(false);
                return;
              }
              console.error(
                "Error getting user during auth state change:",
                userError,
              );
              setSession(null);
              setUser(null);
              setLoading(false);
              return;
            }

            // Update session and user atomically
            setSession(session);
            setUser(userData.user);
          } catch (error) {
            console.error("Unexpected error verifying user:", error);
            setSession(null);
            setUser(null);
            setLoading(false);
            return;
          }
        } else {
          // No session, clear user
          setSession(null);
          setUser(null);
        }

        setLoading(false);

        // Handle specific auth events
        if (event === "SIGNED_IN" && session) {
          // console.log("🎉 SIGNED_IN event triggered");

          // toast.success("Welcome back!", {
          //   description: `Signed in as ${session.user?.email || "user"}`,
          // });

          // Handle redirect after successful sign in
          if (pathname === "/login" || pathname === "/signup") {
            const redirectUrl = pendingRedirect || "/dashboard";
            console.log("🚀 Redirecting from login page to:", redirectUrl);

            // Clear pending redirect
            setPendingRedirect(null);

            // Use router for navigation
            router.push(redirectUrl);
          }
        } else if (event === "SIGNED_OUT") {
          toast.success("Signed out successfully", {
            description: "You have been signed out of your account.",
          });
          // Clear any pending redirects
          setPendingRedirect(null);
          // Only redirect if not already on home page
          if (pathname !== "/") {
            router.push("/");
          }
        }
      }, 50); // 50ms debounce
    });

    return () => {
      isMounted = false;
      if (timeoutId) {
        clearTimeout(timeoutId);
      }
      subscription.unsubscribe();
    };
  }, [supabase, router, pathname, pendingRedirect]);

  const signOut = async () => {
    try {
      // Don't set loading to prevent flickering
      const { error } = await supabase.auth.signOut();

      if (error) {
        console.error("Error signing out:", error);
        toast.error("Sign out failed", {
          description: "There was an error signing you out. Please try again.",
        });
        return;
      }
      window.location.href = "/"; // Redirect to home page after sign out

      // State will be updated by the auth state change listener
    } catch (error) {
      console.error("Unexpected error during sign out:", error);
      toast.error("Sign out failed", {
        description: "An unexpected error occurred. Please try again.",
      });
    }
  };

  const refreshUser = async () => {
    try {
      console.log("Refreshing user session...");

      // Get current session
      const { data: sessionData, error: sessionError } =
        await supabase.auth.getSession();

      if (sessionError) {
        console.error("Error getting session:", sessionError);
        setSession(null);
        setUser(null);
        return;
      }

      // If we have a session, verify the user still exists
      if (sessionData.session) {
        try {
          const { data: userData, error: userError } =
            await supabase.auth.getUser();

          if (userError) {
            // Handle deleted user with orphaned session
            if (
              userError.message?.includes(
                "User from sub claim in JWT does not exist",
              ) ||
              userError.code === "user_not_found"
            ) {
              console.log(
                "User was deleted, clearing orphaned session during refresh",
              );
              await supabase.auth.signOut();
              setSession(null);
              setUser(null);
              return;
            }
            throw userError;
          }

          // Update both session and user atomically
          setSession(sessionData.session);
          setUser(userData.user);

          console.log("Session refreshed:", userData.user?.email || "no user");
        } catch (error) {
          console.error("Error verifying user during refresh:", error);
          setSession(null);
          setUser(null);
        }
      } else {
        // No session
        setSession(null);
        setUser(null);
        console.log("No session found during refresh");
      }
    } catch (error) {
      console.error("Unexpected error refreshing user:", error);
      setSession(null);
      setUser(null);
    }
  };

  const setLoginRedirect = (url: string) => {
    console.log("📍 Setting login redirect URL:", url);
    setPendingRedirect(url);
  };

  const value = {
    user,
    session,
    loading,
    signOut,
    refreshUser,
    setLoginRedirect,
  };

  return <UserContext.Provider value={value}>{children}</UserContext.Provider>;
}

export function useUser() {
  const context = useContext(UserContext);
  if (context === undefined) {
    throw new Error("useUser must be used within a UserProvider");
  }
  return context;
}
