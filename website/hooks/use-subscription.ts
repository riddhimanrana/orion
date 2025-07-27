"use client";

import { useState, useEffect, useCallback } from "react";
import { useUser } from "@/hooks/use-user";

export type SubscriptionTier = "free" | "pro";

interface UseSubscriptionReturn {
  subscriptionTier: SubscriptionTier;
  loading: boolean;
  error: string | null;
  refreshSubscription: () => void;
}

export function useSubscription(): UseSubscriptionReturn {
  const { user, loading: userLoading } = useUser();
  const [subscriptionTier, setSubscriptionTier] =
    useState<SubscriptionTier>("free");
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const refreshSubscription = useCallback(() => {
    if (!user) {
      setSubscriptionTier("free");
      setLoading(false);
      setError(null);
      return;
    }

    try {
      setLoading(true);
      setError(null);

      // Get subscription tier from user metadata
      const tier = user.user_metadata?.subscription_tier as SubscriptionTier;
      setSubscriptionTier(tier || "free");
    } catch (err) {
      setError(
        err instanceof Error ? err.message : "Failed to load subscription",
      );
      setSubscriptionTier("free"); // Default to free on error
    } finally {
      setLoading(false);
    }
  }, [user]);

  useEffect(() => {
    if (!userLoading) {
      refreshSubscription();
    }
  }, [user, userLoading, refreshSubscription]);

  return {
    subscriptionTier,
    loading: userLoading || loading,
    error,
    refreshSubscription,
  };
}
